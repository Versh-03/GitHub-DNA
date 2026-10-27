import re
import shutil
import subprocess
import uuid
from pathlib import Path

from .config import WORKSPACE_DIR, MAX_REPO_SIZE_MB, CLONE_TIMEOUT_SEC

# Strict: https://github.com/<owner>/<repo>[.git][/]
GITHUB_URL_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$"
)


class IngestError(Exception):
    """Raised for any user-facing ingestion problem."""


def validate_github_url(url: str) -> tuple[str, str]:
    """Return (owner, repo) or raise IngestError."""
    url = url.strip()
    m = GITHUB_URL_RE.match(url)
    if not m:
        raise IngestError(
            "Invalid URL. Use the form https://github.com/<owner>/<repo> "
            "(public GitHub repositories only)."
        )
    owner, repo = m.group(1), m.group(2)
    if repo in (".", "..") or repo.startswith("."):
        raise IngestError("Invalid repository name.")
    return owner, repo


def _dir_size_mb(path: Path) -> float:
    total = 0
    for p in path.rglob("*"):
        if p.is_file() and not p.is_symlink():
            total += p.stat().st_size
    return total / (1024 * 1024)


def clone_repo(url: str) -> tuple[str, Path, str, str]:
    """
    Shallow-clone a validated public repo.
    Returns (run_id, repo_path, owner, repo).
    """
    owner, repo = validate_github_url(url)
    run_id = uuid.uuid4().hex[:8]
    dest = WORKSPACE_DIR / run_id / repo
    dest.parent.mkdir(parents=True, exist_ok=True)

    clean_url = f"https://github.com/{owner}/{repo}.git"
    env = {
        "GIT_TERMINAL_PROMPT": "0",  # never ask for credentials
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": "/tmp",
    }
    cmd = [
        "git", "-c", "core.hooksPath=/dev/null",
        "clone", "--depth", "1", "--single-branch", "--no-tags",
        clean_url, str(dest),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=CLONE_TIMEOUT_SEC, env=env,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest.parent, ignore_errors=True)
        raise IngestError(f"Clone timed out after {CLONE_TIMEOUT_SEC}s. Repository may be too large.")

    if proc.returncode != 0:
        shutil.rmtree(dest.parent, ignore_errors=True)
        raise IngestError("Could not clone repository. Is it public and does it exist?")

    size = _dir_size_mb(dest)
    if size > MAX_REPO_SIZE_MB:
        shutil.rmtree(dest.parent, ignore_errors=True)
        raise IngestError(f"Repository is {size:.0f} MB; limit is {MAX_REPO_SIZE_MB} MB.")

    return run_id, dest, owner, repo
