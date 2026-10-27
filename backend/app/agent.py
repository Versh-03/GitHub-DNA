"""
Planner + Investigator + Test Verifier agents coordinated by an orchestrator.
Produces real evidence, runs isolated Docker container tests, and handles bounded feedback.
Implements bounded exponential backoff with jitter and quota exhaustion detection for Groq.
"""
import json
import random
import time
from pathlib import Path
from typing import Callable, Literal

from openai import APIError, BadRequestError, RateLimitError
from pydantic import BaseModel, ValidationError

from app.llm import chat, get_model, llm_available
from app.ratelimit import (
    LLMQuotaExhausted,
    LLMRateLimitExceeded,
    calculate_backoff,
    parse_rate_limit_error,
    sanitize_message,
)
from app.sandbox import run_test_in_sandbox, validate_test_code, is_docker_available
from app.tools import TOOL_SCHEMAS, ToolBox

MAX_STEPS = 8                  # hard limit on investigator iterations
MAX_RATE_LIMIT_RETRIES = 2     # retries on temporary 429
MAX_SINGLE_WAIT_SEC = 10.0     # max wait for single retry during demo
MAX_TOTAL_WAIT_SEC = 16.0      # max accumulated wait budget for live demo
MAX_TEST_RETRIES = 2           # bounded feedback retries for test generator
MAX_FIX_RETRIES = 1            # bounded feedback retry for failed test execution


class Finding(BaseModel):
    issue_found: bool
    file: str
    explanation: str
    title: str = ""
    severity: Literal["low", "medium", "high"] = "low"
    start_line: int = 0
    end_line: int = 0
    evidence: str = ""
    proposed_fix: str = ""
    full_patched_file: str = ""
    confidence: Literal["low", "medium", "high"] = "low"
    evidence_verified: bool = False   # set deterministically by Python


SELECT_TOOL = {
    "type": "function",
    "function": {
        "name": "select_target",
        "description": "Choose the single file most worth investigating for bugs.",
        "parameters": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "exact path from the file list"},
                "reason": {"type": "string"},
                "focus": {"type": "string", "description": "what kind of problem to look for"},
            },
            "required": ["file", "reason", "focus"],
        },
    },
}

REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "report_finding",
        "description": "Submit the final result of the investigation. Call exactly once.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue_found": {"type": "boolean"},
                "file": {"type": "string"},
                "title": {"type": "string"},
                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
                "explanation": {"type": "string"},
                "evidence": {"type": "string", "description": "exact code lines copied from the file"},
                "proposed_fix": {"type": "string", "description": "minimal replacement code or diff"},
                "full_patched_file": {
                    "type": "string",
                    "description": "CRITICAL: The complete content of the file with the fix applied, so the sandbox can test it cleanly.",
                },
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["issue_found", "file", "explanation"],
        },
    },
}

SUBMIT_TEST_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_test",
        "description": "Submit focused pytest code that verifies the bug and proposed fix.",
        "parameters": {
            "type": "object",
            "properties": {
                "test_code": {
                    "type": "string",
                    "description": "Self-contained Python test script using pytest assertions. Do not import subprocess, socket, or network libraries.",
                },
                "test_description": {"type": "string", "description": "What this test verifies"},
            },
            "required": ["test_code", "test_description"],
        },
    },
}

REVISE_FIX_TOOL = {
    "type": "function",
    "function": {
        "name": "revise_fix",
        "description": "Revise the proposed fix and full_patched_file based on actual test execution failure output.",
        "parameters": {
            "type": "object",
            "properties": {
                "revised_explanation": {"type": "string", "description": "Why the previous patch failed the test"},
                "revised_fix": {"type": "string", "description": "Updated minimal replacement code"},
                "full_patched_file": {"type": "string", "description": "The complete updated source file with fix applied"},
            },
            "required": ["revised_fix", "full_patched_file"],
        },
    },
}

PLANNER_SYSTEM = (
    "You are the Planner of GitHub DNA. You get a summary of a Python repository. "
    "Pick ONE core source file where a real bug is most likely (complex logic, edge cases, "
    "mutable defaults, calculations, exception handling). Avoid docs, tests, and setup files. "
    "Respond only by calling select_target."
)

INVESTIGATOR_SYSTEM = (
    "You are a careful Code Investigator for GitHub DNA. Use get_outline first, then read_file in small ranges "
    "(max 60 lines), and search_code if needed. Look for REAL bugs: wrong conditions, off-by-one, "
    "unhandled None/empty input, mutable default arguments, bare except, resource leaks. "
    "Only report what you actually saw in code. In report_finding, provide: "
    "1. evidence: lines copied exactly from the file. "
    "2. proposed_fix: concise replacement code. "
    "3. full_patched_file: the entire file content with your proposed fix applied, ready for testing in Docker. "
    "Finish within 5 tool calls."
)

TEST_VERIFIER_SYSTEM = (
    "You are the Test & Verification Agent for GitHub DNA. Given a Python file, a confirmed issue, "
    "and a proposed fix, generate a single self-contained pytest test file named test_dna_verification.py. "
    "Requirements:\n"
    "1. Import the target module directly (e.g. from mypkg.mod import func), assuming the repo root is on PYTHONPATH.\n"
    "2. Write 1 or 2 clear test functions that assert the expected correct behavior.\n"
    "3. Do NOT import subprocess, socket, urllib, or network modules.\n"
    "4. Return the test code by calling submit_test."
)


def build_overview(analysis: dict) -> str:
    files = [f for f in analysis["files"]
             if not f["path"].startswith(("docs/", "doc/", "examples/", "tests/", "test/")) and not f.get("parse_error")]
    files.sort(key=lambda f: f.get("lines", 0), reverse=True)
    out = [f"Repository stats: {analysis['stats']}",
           "Files (path | lines | functions | classes | imports):"]
    for f in files[:30]:
        mods = sorted({i.get("module") for i in f.get("imports", []) if i.get("module")})[:8]
        out.append(f"{f['path']} | {f.get('lines', 0)} | {len(f.get('functions', []))} | {len(f.get('classes', []))} | {', '.join(mods)}")
    return "\n".join(out)


def _fallback_target(analysis: dict) -> str:
    cands = [f for f in analysis["files"]
             if not f["path"].startswith(("docs/", "doc/", "examples/", "tests/", "test/")) and not f.get("parse_error")]
    cands = cands or analysis["files"]
    return max(cands, key=lambda f: len(f.get("functions", [])))["path"]


def _assistant_dict(msg) -> dict:
    d = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        d["tool_calls"] = [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                           for tc in msg.tool_calls]
    return d


def _args(tc) -> dict:
    try:
        a = json.loads(tc.function.arguments or "{}")
        return a if isinstance(a, dict) else {}
    except json.JSONDecodeError:
        return {}


def _apply_patch_in_memory(original_text: str, finding: Finding) -> str:
    """Construct full patched file content if not provided directly."""
    if finding.full_patched_file and finding.full_patched_file.strip():
        return finding.full_patched_file

    lines = original_text.splitlines()
    if finding.start_line > 0 and finding.end_line >= finding.start_line and finding.proposed_fix:
        before = lines[:finding.start_line - 1]
        after = lines[finding.end_line:]
        fix_lines = finding.proposed_fix.splitlines()
        return "\n".join(before + fix_lines + after) + "\n"

    # If evidence is found verbatim, replace it with proposed_fix
    if finding.evidence and finding.evidence.strip() in original_text and finding.proposed_fix:
        return original_text.replace(finding.evidence.strip(), finding.proposed_fix.strip(), 1)

    return original_text


def run_agent(
    analysis: dict,
    repo_dir,
    on_event: Callable[[dict], None] | None = None,
    demo_mode: bool = False
) -> dict:
    """
    Coordinates Planner, Investigator, Grounding Verifier, and Test Sandbox with Bounded Feedback.
    Safely handles Groq rate limits and quota exhaustion without unhandled crashes.
    """
    events: list[dict] = []

    def log(agent: str, action: str, detail: str = ""):
        clean_detail = sanitize_message(detail[:600])
        ev = {"time": time.strftime("%H:%M:%S"), "agent": agent, "action": action, "detail": clean_detail}
        events.append(ev)
        if on_event:
            on_event(ev)

    repo_path = Path(repo_dir).resolve()
    valid_paths = {f["path"] for f in analysis["files"]}
    box = ToolBox(repo_path, analysis)

    # 1. Deterministic Fallback or Demo Mode (only when explicit or no key)
    if not llm_available():
        log("system", "key_missing", "Groq API key is not configured. Preserving repository AST analysis.")
        target_file = _fallback_target(analysis)
        plan = {
            "file": target_file,
            "reason": "Deterministic selection: core file with highest function count",
            "focus": "Structural inspection (AI investigation unavailable: missing GROQ_API_KEY)"
        }
        return {
            "model": "deterministic-fallback",
            "plan": plan,
            "steps_used": 0,
            "status": "llm_unavailable",
            "finding": None,
            "stages": {
                "potential_issue_detected": False,
                "fix_proposed": False,
                "tests_generated": False,
                "tests_executed": False,
                "fix_verified": False,
            },
            "test_results": None,
            "note": "GROQ_API_KEY is not configured. Repository AST structure and file metrics are available, but AI bug investigation requires Groq credentials.",
            "events": events,
        }

    if demo_mode:
        log("system", "demo_mode", "Running in explicit deterministic demo mode fixture.")
        target_file = _fallback_target(analysis)
        plan = {
            "file": target_file,
            "reason": "Deterministic selection: core candidate file with highest function count",
            "focus": "Demonstration candidate inspection"
        }
        return {
            "model": "deterministic-demo-mode",
            "plan": plan,
            "steps_used": 0,
            "status": "investigation_incomplete",
            "finding": None,
            "stages": {
                "potential_issue_detected": False,
                "fix_proposed": False,
                "tests_generated": False,
                "tests_executed": False,
                "fix_verified": False,
            },
            "test_results": None,
            "note": "DEMO FIXTURE: Running in explicit offline demo mode without live LLM reasoning.",
            "events": events,
        }

    # Bounded wait tracking for live demo
    total_slept = 0.0

    def llm(messages, tools, tool_choice, max_tokens=2500):
        nonlocal total_slept
        for attempt in range(1, MAX_RATE_LIMIT_RETRIES + 1):
            try:
                return chat(messages, tools=tools, tool_choice=tool_choice, max_tokens=max_tokens)
            except RateLimitError as err:
                info = parse_rate_limit_error(err)
                if info.is_quota_exhausted:
                    log("system", "quota_exhausted", f"Groq quota exhausted: {info.safe_detail}. Halting immediately.")
                    raise LLMQuotaExhausted(info.safe_detail)

                # Determine delay
                if info.retry_after is not None and info.retry_after > 0:
                    delay = info.retry_after + random.uniform(0.1, 0.4)
                else:
                    delay = calculate_backoff(attempt)

                # Check budget constraints for live demo
                if delay > MAX_SINGLE_WAIT_SEC or (total_slept + delay) > MAX_TOTAL_WAIT_SEC or attempt >= MAX_RATE_LIMIT_RETRIES:
                    log("system", "rate_limit_exceeded", f"Rate limit delay ({delay:.1f}s) exceeds demo budget or retry cap. Halting.")
                    raise LLMRateLimitExceeded(info.safe_detail, retry_after=delay)

                log("system", "rate_limited", f"Rate limited by Groq API. Waiting {delay:.1f}s (attempt {attempt}/{MAX_RATE_LIMIT_RETRIES})...")
                time.sleep(delay)
                total_slept += delay
            except APIError as e:
                safe_err = sanitize_message(str(e))
                log("system", "llm_error", safe_err)
                raise
        raise LLMRateLimitExceeded("LLM rate limit not cleared after retries")

    # ---------- 1. Planner ----------
    log("planner", "start", "Reading repository overview to select investigation target")
    plan = None
    try:
        msg = llm([{"role": "system", "content": PLANNER_SYSTEM},
                   {"role": "user", "content": build_overview(analysis)}], [SELECT_TOOL], "required")
        for tc in (msg.tool_calls or []):
            if tc.function.name == "select_target":
                a = _args(tc)
                if a.get("file") in valid_paths:
                    plan = {"file": a["file"], "reason": str(a.get("reason", "")), "focus": str(a.get("focus", ""))}
    except (LLMRateLimitExceeded, LLMQuotaExhausted) as e:
        is_quota = isinstance(e, LLMQuotaExhausted)
        log("planner", "rate_limited", str(e))
        return {
            "model": get_model(),
            "plan": None,
            "steps_used": 0,
            "status": "llm_unavailable",
            "finding": None,
            "stages": {
                "potential_issue_detected": False,
                "fix_proposed": False,
                "tests_generated": False,
                "tests_executed": False,
                "fix_verified": False,
            },
            "test_results": None,
            "rate_limit": {
                "stage": "planner",
                "is_quota": is_quota,
                "message": str(e),
            },
            "note": f"Investigation halted at planning phase: Groq API {'quota exhausted' if is_quota else 'rate limit reached'} ({str(e)}). Structural AST analysis is preserved.",
            "events": events,
        }
    except Exception as e:
        log("planner", "error", f"Planner call failed: {sanitize_message(str(e))}")

    if plan is None:
        plan = {"file": _fallback_target(analysis), "reason": "fallback: file with most functions",
                "focus": "general bugs and unhandled conditions"}
        log("planner", "fallback", "Planner provided no valid target; using deterministic candidate")
    log("planner", "target_selected", f"{plan['file']} - {plan['reason']}")

    # ---------- 2. Investigator ----------
    messages = [
        {"role": "system", "content": INVESTIGATOR_SYSTEM},
        {"role": "user", "content": f"Target file: {plan['file']}\nFocus: {plan['focus']}\nPlanner's reason: {plan['reason']}"}
    ]
    finding: Finding | None = None
    steps_used = 0

    for step in range(1, MAX_STEPS + 1):
        steps_used = step
        left = MAX_STEPS - step
        if left == 1:
            messages.append({"role": "user", "content": "Only one step left after this one. Call report_finding on your next turn."})
        elif left == 0:
            messages.append({"role": "user", "content": "Final step. Call report_finding now with what you have seen. Do not call any other tool."})

        try:
            msg = llm(messages, TOOL_SCHEMAS + [REPORT_TOOL], "auto")
        except (LLMRateLimitExceeded, LLMQuotaExhausted) as e:
            is_quota = isinstance(e, LLMQuotaExhausted)
            log("investigator", "rate_limited", str(e))
            return {
                "model": get_model(),
                "plan": plan,
                "steps_used": steps_used,
                "status": "llm_unavailable",
                "finding": None,
                "stages": {
                    "potential_issue_detected": False,
                    "fix_proposed": False,
                    "tests_generated": False,
                    "tests_executed": False,
                    "fix_verified": False,
                },
                "test_results": None,
                "rate_limit": {
                    "stage": "investigator",
                    "is_quota": is_quota,
                    "message": str(e),
                },
                "note": f"Investigation halted during code inspection: Groq API {'quota exhausted' if is_quota else 'rate limit reached'} ({str(e)}). Completed tool events are preserved.",
                "events": events,
            }
        except BadRequestError as e:
            log("investigator", "llm_rejected", sanitize_message(str(e)[:200]))
            break

        if not msg.tool_calls:
            log("investigator", "no_tool_call", sanitize_message((msg.content or "")[:200]))
            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({"role": "user", "content": "Use a tool to inspect code, or call report_finding."})
            continue

        messages.append(_assistant_dict(msg))
        done = False
        for tc in msg.tool_calls:
            name, args = tc.function.name, _args(tc)
            if name == "report_finding":
                try:
                    finding = Finding(**{k: v for k, v in args.items() if k in Finding.model_fields and k != "evidence_verified"})
                    log("investigator", "report_finding", finding.title or finding.explanation[:120])
                except ValidationError as e:
                    log("investigator", "invalid_report", sanitize_message(str(e)[:300]))
                done = True
                break
            result = box.call(name, args)
            log("investigator", f"tool:{name}", f"{json.dumps(args)[:120]} -> {len(result)} chars")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        if done:
            break

    if finding is None:
        log("investigator", "forcing_report", "Step limit reached without report; soliciting final report")
        try:
            messages.append({"role": "user", "content": "Stop investigating. Call report_finding now."})
            msg = llm(messages, [REPORT_TOOL], {"type": "function", "function": {"name": "report_finding"}}, max_tokens=3000)
            for tc in (msg.tool_calls or []):
                if tc.function.name == "report_finding":
                    a = _args(tc)
                    finding = Finding(**{k: v for k, v in a.items() if k in Finding.model_fields and k != "evidence_verified"})
                    log("investigator", "report_finding", finding.title or finding.explanation[:120])
        except (LLMRateLimitExceeded, LLMQuotaExhausted) as e:
            log("investigator", "forced_report_rate_limited", str(e))
        except Exception as e:
            log("investigator", "forced_report_failed", sanitize_message(str(e)[:200]))

    # ---------- 3. Deterministic Grounding Check ----------
    if finding is not None:
        text = box.read_text(finding.file) or ""
        norm = lambda s: " ".join(s.split())
        finding.evidence_verified = bool(
            finding.issue_found and text and finding.evidence.strip() and norm(finding.evidence) in norm(text)
        )
        log("verifier", "evidence_check",
            "Quoted evidence found verbatim in source file" if finding.evidence_verified
            else "Evidence NOT found verbatim in source file")

    detected = bool(finding and finding.issue_found)
    has_fix = bool(detected and finding.proposed_fix.strip())

    # ---------- 4. Agent D: Test Generation & Isolated Verification ----------
    test_results = None
    tests_generated = False
    tests_executed = False
    fix_verified = False
    test_rate_limited = False
    test_rate_limit_msg = ""

    if detected and has_fix:
        log("test_agent", "start", f"Generating test for {finding.file} to verify issue and fix")
        test_prompt = [
            {"role": "system", "content": TEST_VERIFIER_SYSTEM},
            {"role": "user", "content": (
                f"File: {finding.file}\n"
                f"Issue Title: {finding.title}\n"
                f"Explanation: {finding.explanation}\n"
                f"Quoted Buggy Evidence:\n```python\n{finding.evidence}\n```\n"
                f"Proposed Fix:\n```python\n{finding.proposed_fix}\n```\n"
                "Write a pytest test verifying that the function/logic handles this case correctly."
            )}
        ]

        test_code = None
        test_desc = ""

        # Test generation with retry loop
        for attempt in range(1, MAX_TEST_RETRIES + 1):
            try:
                tmsg = llm(test_prompt, [SUBMIT_TEST_TOOL], {"type": "function", "function": {"name": "submit_test"}}, max_tokens=1500)
                for tc in (tmsg.tool_calls or []):
                    if tc.function.name == "submit_test":
                        a = _args(tc)
                        candidate_code = a.get("test_code", "")
                        validate_test_code(candidate_code)
                        test_code = candidate_code
                        test_desc = a.get("test_description", "")
                        tests_generated = True
                        log("test_agent", "test_generated", test_desc or "Test code validated successfully")
                        break
                if test_code:
                    break
            except (LLMRateLimitExceeded, LLMQuotaExhausted) as e:
                test_rate_limited = True
                test_rate_limit_msg = str(e)
                log("test_agent", "rate_limited", f"Test generation halted due to rate limit: {e}")
                break
            except Exception as e:
                log("test_agent", "test_validation_failed", f"Attempt {attempt}: {sanitize_message(str(e))}")
                test_prompt.append({"role": "user", "content": f"Test code validation failed: {sanitize_message(str(e))}. Generate valid self-contained Python test code."})

        # Run generated test in sandbox
        if test_code:
            if not is_docker_available():
                log("verifier", "docker_unavailable", "Docker sandbox is unavailable on this host")
                test_results = {
                    "status": "verification_unavailable",
                    "reason": "Docker daemon is unavailable to run untrusted tests securely",
                    "test_code": test_code,
                }
            else:
                log("verifier", "sandbox_run_baseline", "Running test against original unpatched repository code")
                baseline_res = run_test_in_sandbox(repo_path, test_code)
                log("verifier", "baseline_result", f"Status: {baseline_res['status']} | exit code: {baseline_res['exit_code']}")

                # Prepare patched source code
                orig_file_text = box.read_text(finding.file) or ""
                patched_file_text = _apply_patch_in_memory(orig_file_text, finding)

                log("verifier", "sandbox_run_patched", "Applying proposed fix in sandbox and running test again")
                patched_res = run_test_in_sandbox(
                    repo_path,
                    test_code,
                    patch_file=finding.file,
                    patch_content=patched_file_text
                )
                log("verifier", "patched_result", f"Status: {patched_res['status']} | exit code: {patched_res['exit_code']}")

                tests_executed = True

                # ---------- Bounded Feedback Loop: Retry if patched test failed ----------
                if patched_res["status"] == "failed" and MAX_FIX_RETRIES > 0:
                    log("verifier", "bounded_retry_started", "Test failed on patched code. Invoking bounded retry loop with test failure evidence.")
                    feedback_prompt = [
                        {"role": "system", "content": "You are the Code Investigator. The test you generated failed on the proposed fix. Analyze the test failure output and revise your fix so the test passes. Respond by calling revise_fix."},
                        {"role": "user", "content": (
                            f"Target File: {finding.file}\n"
                            f"Original Code:\n```python\n{orig_file_text}\n```\n"
                            f"Test Code:\n```python\n{test_code}\n```\n"
                            f"Test Execution Failure Output:\n"
                            f"STDOUT:\n{patched_res['stdout']}\n"
                            f"STDERR:\n{patched_res['stderr']}\n"
                            "Provide the corrected replacement code and the full_patched_file that passes the test."
                        )}
                    ]
                    try:
                        rmsg = llm(feedback_prompt, [REVISE_FIX_TOOL], {"type": "function", "function": {"name": "revise_fix"}}, max_tokens=3000)
                        for tc in (rmsg.tool_calls or []):
                            if tc.function.name == "revise_fix":
                                ra = _args(tc)
                                if ra.get("full_patched_file"):
                                    finding.full_patched_file = ra["full_patched_file"]
                                if ra.get("revised_fix"):
                                    finding.proposed_fix = ra["revised_fix"]
                                log("investigator", "fix_revised", "Revised fix produced from execution failure evidence")

                                # Re-run sandbox with revised patch
                                log("verifier", "sandbox_retest", "Retesting revised patch in Docker container")
                                patched_res = run_test_in_sandbox(
                                    repo_path,
                                    test_code,
                                    patch_file=finding.file,
                                    patch_content=finding.full_patched_file
                                )
                                log("verifier", "retest_result", f"Status: {patched_res['status']} | exit code: {patched_res['exit_code']}")
                                break
                    except (LLMRateLimitExceeded, LLMQuotaExhausted) as e:
                        log("verifier", "retry_rate_limited", f"Fix revision skipped due to rate limit: {e}")
                    except Exception as e:
                        log("verifier", "retry_error", f"Bounded retry failed: {sanitize_message(str(e))}")

                if patched_res["status"] == "passed":
                    fix_verified = True
                    log("verifier", "verification_success", "Proposed fix PASSED tests in isolated Docker sandbox!")
                else:
                    log("verifier", "verification_unresolved", f"Patched code status: {patched_res['status']}")

                test_results = {
                    "test_code": test_code,
                    "description": test_desc,
                    "baseline": baseline_res,
                    "patched": patched_res,
                    "fix_verified": fix_verified,
                }

    # Final overall status computation
    if fix_verified:
        final_status = "tests_passed"
    elif tests_executed and test_results and test_results.get("patched", {}).get("status") == "failed":
        final_status = "tests_failed"
    elif tests_generated and not tests_executed:
        final_status = "verification_unavailable"
    elif has_fix:
        final_status = "fix_proposed"
    elif detected:
        final_status = "potential_issue"
    elif finding and not finding.issue_found:
        final_status = "no_issue_found"
    else:
        final_status = "investigation_incomplete"

    note = (
        "Finding and fix verified through containerized test execution." if fix_verified
        else "Test generation halted due to rate limit; proposed fix remains unverified." if test_rate_limited
        else "Finding is an unverified suggestion until tests pass in isolation."
    )

    result = {
        "model": get_model(),
        "plan": plan,
        "steps_used": steps_used,
        "status": final_status,
        "finding": finding.model_dump() if finding else None,
        "stages": {
            "potential_issue_detected": detected,
            "fix_proposed": has_fix,
            "tests_generated": tests_generated,
            "tests_executed": tests_executed,
            "fix_verified": fix_verified,
        },
        "test_results": test_results,
        "note": note,
        "events": events,
    }

    if test_rate_limited:
        result["rate_limit"] = {
            "stage": "test_generator",
            "message": test_rate_limit_msg,
        }

    return result
