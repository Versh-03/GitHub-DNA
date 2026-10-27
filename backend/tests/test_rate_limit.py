"""
Tests for Groq rate-limit handling, quota exhaustion, bounded retries, and preserved partial results.
"""
import pytest
from unittest.mock import MagicMock, patch
import httpx
from openai import RateLimitError

from app.ratelimit import (
    parse_rate_limit_error,
    calculate_backoff,
    sanitize_message,
    RateLimitInfo,
    LLMRateLimitExceeded,
    LLMQuotaExhausted,
)
from app.agent import run_agent
from app.analyzer import analyze_repo
from app.main import app
from fastapi.testclient import TestClient
from pathlib import Path


def make_rate_limit_error(message: str, headers: dict | None = None, body: dict | None = None) -> RateLimitError:
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    resp_headers = headers or {}
    resp_body = body or {"error": {"message": message, "type": "tokens", "code": "rate_limit_exceeded"}}
    resp = httpx.Response(status_code=429, headers=resp_headers, json=resp_body, request=req)
    return RateLimitError(message=message, response=resp, body=resp_body)


def test_sanitize_message():
    raw = "Failed request with key gsk_abc123456789xyz in header Bearer gsk_secretkey12345"
    sanitized = sanitize_message(raw)
    assert "gsk_abc123456789xyz" not in sanitized
    assert "gsk_***" in sanitized
    assert "Bearer ***" in sanitized


def test_parse_retry_after_header():
    err = make_rate_limit_error("Rate limit reached", headers={"retry-after": "4.2"})
    info = parse_rate_limit_error(err)
    assert info.retry_after == 4.2
    assert not info.is_quota_exhausted


def test_parse_groq_custom_headers():
    err = make_rate_limit_error("Rate limit reached", headers={"x-ratelimit-reset-tokens": "2.5s"})
    info = parse_rate_limit_error(err)
    assert info.retry_after == 2.5


def test_parse_retry_after_from_message_text():
    err = make_rate_limit_error("Rate limit reached on TPM. Please try again in 3.42s.")
    info = parse_rate_limit_error(err)
    assert info.retry_after == 3.42
    assert not info.is_quota_exhausted


def test_parse_quota_exhaustion():
    body = {
        "error": {
            "message": "You exceeded your current quota, please check your plan and billing details.",
            "code": "insufficient_quota",
            "type": "insufficient_quota",
        }
    }
    err = make_rate_limit_error("Quota exceeded", body=body)
    info = parse_rate_limit_error(err)
    assert info.is_quota_exhausted is True
    assert info.error_code == "insufficient_quota"


def test_calculate_backoff():
    # Attempt 1 should be between 2.1s and 2.9s with base 2.0
    d1 = calculate_backoff(1, base_delay=2.0, max_delay=8.0)
    assert 2.0 <= d1 <= 3.0
    # Attempt 2 should be between 4.0s and 5.0s
    d2 = calculate_backoff(2, base_delay=2.0, max_delay=8.0)
    assert 4.0 <= d2 <= 5.0
    # Max delay ceiling
    d_large = calculate_backoff(5, base_delay=2.0, max_delay=8.0)
    assert d_large <= 8.0


@patch("app.agent.chat")
@patch("app.agent.time.sleep")
def test_successful_retry_after_temporary_429(mock_sleep, mock_chat):
    # First call raises temporary 429 with retry-after=0.1; second call returns assistant message
    err_429 = make_rate_limit_error("Rate limit reached", headers={"retry-after": "0.1"})
    
    success_msg = MagicMock()
    success_msg.content = None
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "select_target"
    tc.function.arguments = '{"file": "retail_core/pricing.py", "reason": "Complex logic", "focus": "boundary bugs"}'
    success_msg.tool_calls = [tc]

    report_msg = MagicMock()
    report_msg.content = None
    tc_rep = MagicMock()
    tc_rep.id = "call_2"
    tc_rep.function.name = "report_finding"
    tc_rep.function.arguments = '{"issue_found": false, "file": "retail_core/pricing.py", "explanation": "No defect"}'
    report_msg.tool_calls = [tc_rep]

    mock_chat.side_effect = [err_429, success_msg, report_msg]

    analysis = analyze_repo(Path("sample_repo"))
    events = []
    result = run_agent(analysis, Path("sample_repo"), on_event=lambda e: events.append(e))

    assert mock_sleep.called
    assert result["plan"]["file"] == "retail_core/pricing.py"
    assert any(e["action"] == "rate_limited" for e in events)


@patch("app.agent.chat")
@patch("app.agent.time.sleep")
def test_persistent_429_returns_structured_incomplete(mock_sleep, mock_chat):
    # Persistent 429 on all attempts
    err_429 = make_rate_limit_error("Rate limit reached", headers={"retry-after": "0.1"})
    mock_chat.side_effect = err_429

    analysis = analyze_repo(Path("sample_repo"))
    events = []
    result = run_agent(analysis, Path("sample_repo"), on_event=lambda e: events.append(e))

    # Must return structured status 'llm_unavailable' rather than unhandled exception
    assert result["status"] == "llm_unavailable"
    assert result["finding"] is None
    assert result["stages"]["potential_issue_detected"] is False
    assert result["rate_limit"]["stage"] == "planner"
    assert any(e["action"] == "rate_limited" for e in events)


@patch("app.agent.chat")
@patch("app.agent.time.sleep")
def test_quota_exhaustion_halts_immediately_without_repeated_retries(mock_sleep, mock_chat):
    body = {
        "error": {
            "message": "You exceeded your current quota",
            "code": "insufficient_quota",
        }
    }
    quota_err = make_rate_limit_error("Quota exceeded", body=body)
    mock_chat.side_effect = quota_err

    analysis = analyze_repo(Path("sample_repo"))
    events = []
    result = run_agent(analysis, Path("sample_repo"), on_event=lambda e: events.append(e))

    # Should not call time.sleep repeatedly for quota exhaustion
    assert mock_sleep.call_count == 0
    assert result["status"] == "llm_unavailable"
    assert result["rate_limit"]["is_quota"] is True
    assert any(e["action"] == "quota_exhausted" for e in events)


@patch("app.agent.chat")
def test_partial_finding_preserved_when_test_generator_rate_limited(mock_chat):
    # Planner succeeds
    planner_msg = MagicMock()
    planner_msg.content = None
    tc_plan = MagicMock()
    tc_plan.id = "plan_1"
    tc_plan.function.name = "select_target"
    tc_plan.function.arguments = '{"file": "retail_core/pricing.py", "reason": "Test target", "focus": "bugs"}'
    planner_msg.tool_calls = [tc_plan]

    # Investigator succeeds and reports finding
    inv_msg = MagicMock()
    inv_msg.content = None
    tc_inv = MagicMock()
    tc_inv.id = "rep_1"
    tc_inv.function.name = "report_finding"
    tc_inv.function.arguments = json_args = '''{
        "issue_found": true,
        "file": "retail_core/pricing.py",
        "title": "Mutable default argument",
        "severity": "medium",
        "start_line": 14,
        "end_line": 15,
        "explanation": "discounts=[] retains state",
        "evidence": "def calculate_bulk_total(items: list[dict], discounts: list = []) -> float:",
        "proposed_fix": "def calculate_bulk_total(items: list[dict], discounts: list | None = None) -> float:",
        "confidence": "medium"
    }'''
    inv_msg.tool_calls = [tc_inv]

    # Test generator hits rate limit
    err_429 = make_rate_limit_error("Rate limit reached on TPM")

    mock_chat.side_effect = [planner_msg, inv_msg, err_429, err_429, err_429]

    analysis = analyze_repo(Path("sample_repo"))
    events = []
    result = run_agent(analysis, Path("sample_repo"), on_event=lambda e: events.append(e))

    # Finding MUST be preserved
    assert result["finding"] is not None
    assert result["finding"]["title"] == "Mutable default argument"
    assert result["stages"]["potential_issue_detected"] is True
    assert result["stages"]["fix_proposed"] is True
    assert result["stages"]["tests_generated"] is False
    assert result["status"] == "fix_proposed"
    assert result["rate_limit"]["stage"] == "test_generator"


def test_api_investigate_handles_rate_limit_without_http_500():
    client = TestClient(app)
    # First analyze sample repo
    res = client.post("/analyze", json={"url": "sample://retail-core"})
    assert res.status_code == 200
    run_id = res.json()["run_id"]

    # Mock chat to always raise RateLimitError
    with patch("app.agent.chat") as mock_chat:
        mock_chat.side_effect = make_rate_limit_error("Rate limit reached on TPM")
        res_inv = client.post("/investigate", json={"run_id": run_id, "demo_mode": False})
        
        # Must be HTTP 200 with structured failure, NOT HTTP 500
        assert res_inv.status_code == 200
        data = res_inv.json()
        assert data["investigation"]["status"] == "llm_unavailable"
        assert data["repo"]["name"] == "retail-core-sample"
        # Repository AST data must still be accessible
        res_run = client.get(f"/runs/{run_id}")
        assert res_run.status_code == 200
        assert res_run.json()["analysis"]["stats"]["python_files"] == 4
