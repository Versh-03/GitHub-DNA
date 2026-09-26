"""
main.py — FastAPI application shell for Git DNA.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from backend.analyzers.dependency import build_dependency_edges
from backend.analyzers.git_history import analyze_git_history
from backend.analyzers.repository import walk_repository

app = FastAPI(title="Git DNA")


class AnalyzeRequest(BaseModel):
    repo_path: str


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    """Walk *repo_path*, classify files, extract dependency edges, and
    analyse git history.

    Returns::

        {
            "files": [...],        # from walk_repository
            "edges": [...],        # from build_dependency_edges
            "git_history": {...}   # from analyze_git_history
        }
    """
    files = walk_repository(request.repo_path)
    edges = build_dependency_edges(files, repo_path=request.repo_path)
    git_history = analyze_git_history(request.repo_path)
    return {"files": files, "edges": edges, "git_history": git_history}
