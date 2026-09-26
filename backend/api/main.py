"""
main.py — FastAPI application shell for Git DNA.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from backend.analyzers.repository import walk_repository

app = FastAPI(title="Git DNA")


class AnalyzeRequest(BaseModel):
    repo_path: str


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> list[dict]:
    """Walk *repo_path* and return a list of classified file descriptors."""
    return walk_repository(request.repo_path)
