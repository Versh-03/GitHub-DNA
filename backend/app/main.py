from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .analyzer import analyze_repo
from .agent import run_agent
from .ingest import IngestError, clone_repo
from .ratelimit import sanitize_message
from .sandbox import run_test_in_sandbox, is_docker_available

app = FastAPI(title="GitHub DNA", description="Agentic AI Engineering Platform for Python Repositories")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store: run_id -> data
RUNS: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    url: str


class InvestigateRequest(BaseModel):
    run_id: str
    demo_mode: bool = False


class VerifyRequest(BaseModel):
    run_id: str
    test_code: str
    patch_file: str | None = None
    patch_content: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "github-dna",
        "docker_available": is_docker_available()
    }


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    raw_url = req.url.strip()

    # Support special internal sample repo for instant local testing/demo
    if raw_url in ("sample://retail-core", "sample_repo", "demo://retail-core"):
        sample_path = (Path(__file__).resolve().parents[2] / "sample_repo").resolve()
        if not sample_path.exists():
            raise HTTPException(status_code=404, detail="Sample repository not found")
        run_id = "sample-retail-core"
        result = analyze_repo(sample_path)
        response = {
            "run_id": run_id,
            "repo": {
                "owner": "github-dna-demos",
                "name": "retail-core-sample",
                "url": "https://github.com/github-dna-demos/retail-core-sample",
                "language": "Python",
                "is_demo_sample": True,
            },
            "analysis": result,
        }
        RUNS[run_id] = {"repo_path": str(sample_path), **response}
        return response

    try:
        run_id, repo_path, owner, repo = clone_repo(raw_url)
    except IngestError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = analyze_repo(repo_path)
    if result["stats"]["python_files"] == 0:
        raise HTTPException(
            status_code=400,
            detail="No Python files found. GitHub DNA supports Python repositories only."
        )

    response = {
        "run_id": run_id,
        "repo": {
            "owner": owner,
            "name": repo,
            "url": raw_url,
            "language": "Python",
            "is_demo_sample": False,
        },
        "analysis": result,
    }
    RUNS[run_id] = {"repo_path": str(repo_path), **response}
    return response


@app.post("/investigate")
def investigate(req: InvestigateRequest):
    run_data = RUNS.get(req.run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found. Call /analyze first.")

    repo_path = Path(run_data["repo_path"])
    analysis = run_data["analysis"]

    agent_events: list[dict] = []

    def on_event(ev: dict):
        agent_events.append(ev)

    try:
        investigation_result = run_agent(
            analysis=analysis,
            repo_dir=repo_path,
            on_event=on_event,
            demo_mode=req.demo_mode,
        )
    except Exception as e:
        safe_err = sanitize_message(str(e))
        investigation_result = {
            "model": "openai/gpt-oss-20b",
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
                "stage": "orchestrator",
                "message": safe_err,
            },
            "note": f"Investigation halted: {safe_err}. Repository AST structure is preserved.",
            "events": agent_events,
        }

    # Merge events and update run state
    investigation_result["events"] = agent_events
    run_data["investigation"] = investigation_result
    run_data["status"] = investigation_result["status"]

    return {
        "run_id": req.run_id,
        "repo": run_data["repo"],
        "investigation": investigation_result,
    }


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    run_data = RUNS.get(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run_data


@app.post("/verify")
def verify(req: VerifyRequest):
    run_data = RUNS.get(req.run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found.")

    repo_path = Path(run_data["repo_path"])
    try:
        res = run_test_in_sandbox(
            repo_path=repo_path,
            test_code=req.test_code,
            patch_file=req.patch_file,
            patch_content=req.patch_content,
        )
        return {
            "run_id": req.run_id,
            "result": res,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=sanitize_message(str(e)))
