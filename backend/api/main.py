"""
main.py — FastAPI application shell for Git DNA.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.analyzers.dependency import build_dependency_edges
from backend.analyzers.git_history import analyze_git_history
from backend.analyzers.metrics import compute_metrics
from backend.analyzers.repository import walk_repository
from backend.github_loader import CloneError, InvalidGitHubURLError, cloned_repo
from backend.models.graph import build_graph, graph_to_json

app = FastAPI(title="Git DNA")

# Allow the Vite dev server (and any localhost origin) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173","https://github-dna-three.vercel.app"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type"],
)

_CACHE_DIR = Path("cache")


class AnalyzeRequest(BaseModel):
    repo_path: str


class AnalyzeGitHubRequest(BaseModel):
    github_url: str


def _run_pipeline(repo_path: str) -> dict:
    """Run the full Git DNA pipeline on a local *repo_path* and return the result dict."""
    files       = walk_repository(repo_path)
    edges       = build_dependency_edges(files, repo_path=repo_path)
    git_history = analyze_git_history(repo_path)
    graph       = build_graph(files, edges)
    graph_json  = graph_to_json(graph, git_history)
    metrics     = compute_metrics(files, edges, git_history, graph)
    return {"graph": graph_json, "metrics": metrics}


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    """Run the full Git DNA pipeline on *repo_path*.

    Pipeline::

        walk_repository
            → build_dependency_edges
            → analyze_git_history
            → build_graph / graph_to_json
            → compute_metrics

    Returns::

        {
            "graph":   {"nodes": [...], "edges": [...]},
            "metrics": {...}
        }

    The result is cached as ``cache/<sha256_of_repo_path>.json`` after a
    successful analysis. The analysis runs independently of the cache —
    the cache is only written afterward and is never read back on this
    endpoint.
    """
    repo_path = request.repo_path
    result = _run_pipeline(repo_path)

    # --- cache (best-effort; never blocks the response) ---
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        key = hashlib.sha256(repo_path.encode()).hexdigest()
        (_CACHE_DIR / f"{key}.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
    except OSError:
        pass  # cache write failure is non-fatal

    return result


@app.post("/analyze-github")
def analyze_github(request: AnalyzeGitHubRequest) -> dict:
    """Clone a public GitHub repository and run the full Git DNA pipeline on it.

    The repository is cloned into a temporary directory with ``git clone
    --depth 1``, analyzed, and the temporary directory is deleted afterwards.
    No code from the cloned repository is executed.

    Raises
    ------
    422
        If *github_url* is not a valid public GitHub HTTPS URL.
    502
        If ``git clone`` fails (repo not found, network error, timeout …).
    """
    try:
        with cloned_repo(request.github_url) as local_path:
            return _run_pipeline(local_path)
    except InvalidGitHubURLError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CloneError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
