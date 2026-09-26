"""
dependency.py — AST-based import parser and dependency edge builder.
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path


def extract_imports(file_path: str) -> list[str]:
    """Parse *file_path* with ``ast`` and return candidate module path strings.

    Each candidate is a dotted module name that can be converted to a
    ``a/b/c.py`` path for intra-repo edge resolution.  Multiple candidates
    are returned per import statement so the caller can try all of them:

    * ``import a.b.c``            → ["a.b.c", "a"]
    * ``from a.b import c``       → ["a.b.c", "a.b", "a"]
      ↑ "a.b.c" lets the resolver find ``a/b/c.py`` when *c* is a submodule
    * ``from a.b import c, d``    → ["a.b.c", "a.b.d", "a.b", "a"]

    Duplicates within the same file are preserved (deduplication happens in
    the caller).  Returns an empty list and emits a ``SyntaxWarning`` on
    parse errors.
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
                full = alias.name                 # e.g. "a.b.c"
                top  = full.split(".")[0]         # e.g. "a"
                names.append(full)
                if top != full:
                    names.append(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod  = node.module                # e.g. "a.b"
                top  = mod.split(".")[0]          # e.g. "a"
                # Emit "mod.name" for each imported name so that
                # "from a.b import c" also tries a/b/c.py (submodule form)
                for alias in node.names:
                    if alias.name != "*":
                        names.append(f"{mod}.{alias.name}")
                names.append(mod)
                if top != mod:
                    names.append(top)
            # "from . import x" (relative, no module) — skip
    return names


# File types that are analysed as importers when building dependency edges.
_IMPORTER_TYPES = {"source", "test"}


def build_dependency_edges(file_list: list[dict], repo_path: str = ".") -> list[dict]:
    """Return a list of intra-repo dependency edges for source and test files.

    Files with ``file_type`` in ``{"source", "test"}`` are analysed as
    importers so that test files such as ``test_repository.py`` produce edges
    to the modules they import.

    Each file's ``path`` entry is relative to *repo_path*; the function
    resolves it to an absolute path before calling ``extract_imports``.

    For each imported name the function tries every candidate path produced
    by ``extract_imports`` (see its docstring).  This covers all three forms:

    * ``import backend.analyzers.repository``
      → tries ``backend/analyzers/repository.py``          ✓
    * ``from backend.analyzers.repository import walk_repository``
      → tries ``backend/analyzers/repository/walk_repository.py`` (miss),
        then ``backend/analyzers/repository.py``            ✓
    * ``from backend.analyzers import repository``
      → tries ``backend/analyzers/repository.py``          ✓

    External imports (``os``, ``fastapi``, ``pytest``, etc.) that don't
    resolve to a file in the list are silently skipped.

    Each edge has the shape::

        {"source": <importer_path>, "target": <imported_path>, "type": "import"}
    """
    root = Path(repo_path).resolve()

    # Build a fast lookup: posix path → file dict
    path_set: set[str] = {f["path"] for f in file_list}

    edges: list[dict] = []

    for file_dict in file_list:
        if file_dict.get("file_type") not in _IMPORTER_TYPES:
            continue

        abs_path = str(root / file_dict["path"])
        imports = extract_imports(abs_path)
        seen: set[str] = set()  # deduplicate edges per source file

        for module_name in imports:
            # Convert dotted module name to a relative .py path and check
            candidate = module_name.replace(".", "/") + ".py"
            if candidate in path_set and candidate != file_dict["path"] and candidate not in seen:
                seen.add(candidate)
                edges.append(
                    {
                        "source": file_dict["path"],
                        "target": candidate,
                        "type": "import",
                    }
                )

    return edges
