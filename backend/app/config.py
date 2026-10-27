from pathlib import Path

# Project root = github-dna/
ROOT_DIR = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = ROOT_DIR / "workspace"

# Limits (protect the server from huge or hostile repos)
MAX_REPO_SIZE_MB = 50
MAX_PY_FILES = 300
MAX_FILE_SIZE_KB = 300
CLONE_TIMEOUT_SEC = 60

# Directories we never analyze
SKIP_DIRS = {
    ".git", "venv", ".venv", "env", "node_modules", "__pycache__",
    "build", "dist", ".tox", ".mypy_cache", ".pytest_cache", "site-packages",
}
