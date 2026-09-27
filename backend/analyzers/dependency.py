"""
dependency.py — AST-based import parser and dependency edge builder.
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path


def extract_imports(file_path: str) -> list[tuple[str, int]]:
    """Parse *file_path* with ``ast`` and return (module_name, level) pairs.

    ``level`` is the relative-import level as reported by ``ast``:

    * ``0``  → absolute import (``import a.b.c`` or ``from a.b import c``)
    * ``1``  → single-dot relative import (``from . import x`` or
               ``from .a import b``) — resolved relative to the *importing
               file's own package directory*
    * ``2+`` → multi-dot relative import (``from .. import x``) — resolved
               one additional parent directory up per extra dot

    For ``ImportFrom`` nodes, one candidate is emitted per imported name in
    the form ``"<module>.<name>"`` (to catch submodule-style imports like
    ``from a.b import c`` where ``c`` is itself a file ``a/b/c.py``), plus
    the bare module name itself. For ``from . import x`` / ``from .. import
    x`` (where ``node.module`` is ``None``), each imported name is emitted
    on its own, since there is no module prefix to attach.

    Duplicates within the same file are preserved (deduplication happens in
    the caller). Returns an empty list and emits a ``SyntaxWarning`` on
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

    results: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                full = alias.name                 # e.g. "a.b.c"
                top = full.split(".")[0]           # e.g. "a"
                results.append((full, 0))
                if top != full:
                    results.append((top, 0))

        elif isinstance(node, ast.ImportFrom):
            level = node.level  # 0 = absolute, 1+ = relative dots

            if node.module:
                # "from a.b import c, d"  or  "from .a.b import c, d"
                mod = node.module
                top = mod.split(".")[0]
                for alias in node.names:
                    if alias.name != "*":
                        results.append((f"{mod}.{alias.name}", level))
                results.append((mod, level))
                if level == 0 and top != mod:
                    # only meaningful to also try the top-level package
                    # name for absolute imports
                    results.append((top, level))
            else:
                # "from . import x"  or  "from .. import x, y"
                # node.module is None — there's no prefix, each imported
                # name IS the target module relative to the package dir.
                for alias in node.names:
                    if alias.name != "*":
                        results.append((alias.name, level))

    return results


# File types that are analysed as importers when building dependency edges.
_IMPORTER_TYPES = {"source", "test"}


def _resolve_candidate(
    importer_rel_path: str, module_name: str, level: int
) -> str | None:
    """Convert a (module_name, level) pair into a repo-relative .py path
    candidate, given the path of the file doing the importing.

    * level == 0 (absolute import): resolved relative to the repo root,
      e.g. "backend.analyzers.repository" -> "backend/analyzers/repository.py"

    * level >= 1 (relative import): resolved relative to the *importing
      file's own package directory*, per Python's relative-import rules.
      level == 1 means "my own package directory" (from . import x, or
      from .sibling import y). Each additional level walks one more
      directory up (from .. import x -> parent of my package directory).

    Returns None if the import has no module name to resolve (shouldn't
    normally happen given how extract_imports emits results, but guards
    against a degenerate case).
    """
    if not module_name:
        return None

    module_as_path = module_name.replace(".", "/")

    if level == 0:
        candidate = f"{module_as_path}.py"
    else:
        # Directory containing the importing file == its package directory.
        base_dir = Path(importer_rel_path).parent
        # level == 1 -> stay in base_dir; level == 2 -> go up one more; etc.
        for _ in range(level - 1):
            base_dir = base_dir.parent
        candidate_path = base_dir / module_as_path
        candidate = f"{candidate_path.as_posix()}.py"

    # Normalize accidental leading "./" and backslashes (Windows paths).
    candidate = candidate.replace("\\", "/")
    if candidate.startswith("./"):
        candidate = candidate[2:]

    return candidate


def build_dependency_edges(file_list: list[dict], repo_path: str = ".") -> list[dict]:
    """Return a list of intra-repo dependency edges for source and test files.

    Files with ``file_type`` in ``{"source", "test"}`` are analysed as
    importers so that test files such as ``test_repository.py`` produce
    edges to the modules they import.

    Each file's ``path`` entry is relative to *repo_path*; the function
    resolves it to an absolute path before calling ``extract_imports``, but
    all edge resolution (including relative-import resolution) is done in
    terms of repo-relative paths, using the importing file's own location
    as the base for relative imports.

    This correctly handles all of:

    * ``import backend.analyzers.repository``
      → tries ``backend/analyzers/repository.py``                    ✓
    * ``from backend.analyzers.repository import walk_repository``
      → tries ``backend/analyzers/repository/walk_repository.py`` (miss),
        then ``backend/analyzers/repository.py``                     ✓
    * ``from backend.analyzers import repository``
      → tries ``backend/analyzers/repository.py``                    ✓
    * ``from ._config import Config``  (inside ``httpx/_client.py``)
      → level=1, resolved relative to ``httpx/`` (the importing file's own
        directory) → tries ``httpx/_config.py``                      ✓
    * ``from . import _urlparse``  (inside ``httpx/__init__.py``)
      → level=1, module is None, name is the target itself
      → tries ``httpx/_urlparse.py``                                 ✓
    * ``from .. import shared``  (two directories up)
      → level=2, resolved relative to the parent of the importing
        file's own directory                                        ✓

    External imports (``os``, ``fastapi``, ``pytest``, etc.) that don't
    resolve to a file in the list are silently skipped — they still count
    toward the total-imports stat upstream, but do not appear as graph
    edges since the graph only shows intra-repo relationships.

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

        importer_rel_path = file_dict["path"]
        abs_path = str(root / importer_rel_path)
        imports = extract_imports(abs_path)
        seen: set[str] = set()  # deduplicate edges per source file

        for module_name, level in imports:
            candidate = _resolve_candidate(importer_rel_path, module_name, level)
            if (
                candidate is not None
                and candidate in path_set
                and candidate != importer_rel_path
                and candidate not in seen
            ):
                seen.add(candidate)
                edges.append(
                    {
                        "source": importer_rel_path,
                        "target": candidate,
                        "type": "import",
                    }
                )

    return edges
