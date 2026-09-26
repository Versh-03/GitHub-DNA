"""
dependency.py — AST-based import parser and dependency edge builder.
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path


def extract_imports(file_path: str) -> list[str]:
    """Parse *file_path* with ``ast`` and return the top-level module names imported.

    Handles both ``import x.y.z`` (returns ``"x"``) and
    ``from x.y import z`` (returns ``"x"``).

    Returns an empty list and emits a ``SyntaxWarning`` on parse errors.
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        warnings.warn(
            f"SyntaxError while parsing {file_path}: {exc}",
            SyntaxWarning,
            stacklevel=2,
        )
        return []

    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # "import a.b.c" → top-level name is "a"
                names.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # "from a.b import c" → top-level name is "a"
                names.append(node.module.split(".")[0])
            # "from . import x" (relative, no module) — skip
    return names


def build_dependency_edges(file_list: list[dict], repo_path: str = ".") -> list[dict]:
    """Return a list of intra-repo dependency edges for all source files.

    Only files with ``file_type == "source"`` are analysed as importers.
    Each file's ``path`` entry is relative to *repo_path*; the function
    resolves it to an absolute path before calling ``extract_imports``.

    For each imported module name the function checks whether a matching
    file exists anywhere in *file_list* by converting the dotted module
    path to a file path (``a.b.c`` → ``a/b/c.py``).

    Each edge has the shape::

        {"source": <importer_path>, "target": <imported_path>, "type": "import"}

    External imports (``os``, ``fastapi``, etc.) that don't resolve to a
    file in the list are silently skipped.
    """
    root = Path(repo_path).resolve()

    # Build a fast lookup: posix path → file dict
    path_set: set[str] = {f["path"] for f in file_list}

    edges: list[dict] = []

    for file_dict in file_list:
        if file_dict.get("file_type") != "source":
            continue

        abs_path = str(root / file_dict["path"])
        imports = extract_imports(abs_path)
        seen: set[str] = set()  # deduplicate edges per source file

        for module_name in imports:
            # Convert dotted module name to a relative .py path
            candidate = module_name.replace(".", "/") + ".py"
            if candidate in path_set and candidate not in seen:
                seen.add(candidate)
                edges.append(
                    {
                        "source": file_dict["path"],
                        "target": candidate,
                        "type": "import",
                    }
                )

    return edges
