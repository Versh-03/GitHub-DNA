"""
main.py — FastAPI application shell for Git DNA.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from backend.analyzers.dependency import build_dependency_edges
from backend.analyzers.git_history import analyze_git_history
from backend.analyzers.metrics import compute_metrics
from backend.analyzers.repository import walk_repository
from backend.models.graph import build_graph, graph_to_json

app = FastAPI(title="Git DNA")

_CACHE_DIR = Path("cache")


class AnalyzeRequest(BaseModel):
    repo_path: str


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

    # --- pipeline ---
    files       = walk_repository(repo_path)
    edges       = build_dependency_edges(files, repo_path=repo_path)
    git_history = analyze_git_history(repo_path)
    graph       = build_graph(files, edges)
    graph_json  = graph_to_json(graph, git_history)
    metrics     = compute_metrics(files, edges, git_history, graph)

    result = {"graph": graph_json, "metrics": metrics}

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
