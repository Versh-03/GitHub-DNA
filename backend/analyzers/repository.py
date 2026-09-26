"""
repository.py — file walker and classifier for a local Python repository.
"""

from __future__ import annotations

from pathlib import Path


_DOCS_EXTENSIONS = {".md", ".rst", ".txt"}
_CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}

# File extensions that are always excluded regardless of directory.
_IGNORED_EXTENSIONS = {".pyc", ".pyo"}

# Directory names that are always skipped during the walk.
# Checked against every path *component* so nested occurrences are also pruned.
_IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
}


def _classify(rel_path: Path) -> str:
    """Return the file_type for a single file path.

    Priority order (highest first):
      1. test  — any path component equals "test" or "tests",
                 OR the filename starts with "test_"
      2. source — extension is .py
      3. docs   — extension in {.md, .rst, .txt}
      4. config — extension in {.json, .yaml, .yml, .toml, .cfg, .ini}
      5. other
    """
    # Check test directories using path components (exact component match)
    parts_lower = [p.lower() for p in rel_path.parts]
    in_test_dir = any(p in ("test", "tests") for p in parts_lower[:-1])

    # Check filename prefix
    filename_is_test = rel_path.name.startswith("test_")

    if in_test_dir or filename_is_test:
        return "test"

    ext = rel_path.suffix.lower()

    if ext == ".py":
        return "source"

    if ext in _DOCS_EXTENSIONS:
        return "docs"

    if ext in _CONFIG_EXTENSIONS:
        return "config"

    return "other"


def walk_repository(repo_path: str) -> list[dict]:
    """Walk every file in *repo_path* and return a list of file descriptors.

    Each descriptor is a dict with:
      - ``path``       — POSIX-style path relative to *repo_path*
      - ``size_bytes`` — file size in bytes
      - ``file_type``  — one of "test", "source", "docs", "config", "other"

    The following directories are always excluded (at any depth):
    .git, .venv, venv, env, node_modules, __pycache__, .pytest_cache,
    .mypy_cache, dist, build.
    """
    root = Path(repo_path).resolve()
    results: list[dict] = []

    for abs_path in root.rglob("*"):
        # Skip directories themselves — only record files
        if not abs_path.is_file():
            continue

        rel = abs_path.relative_to(root)

        # Skip ignored directory components (e.g. __pycache__, node_modules)
        if _IGNORED_DIRS.intersection(rel.parts):
            continue

        # Skip compiled / bytecode files regardless of location
        if abs_path.suffix.lower() in _IGNORED_EXTENSIONS:
            continue

        results.append(
            {
                "path": rel.as_posix(),
                "size_bytes": abs_path.stat().st_size,
                "file_type": _classify(rel),
            }
        )

    return results
