import ast
from pathlib import Path

import networkx as nx

from .config import MAX_PY_FILES, MAX_FILE_SIZE_KB, SKIP_DIRS


def find_python_files(repo_path: Path) -> list[Path]:
    files = []
    for p in repo_path.rglob("*.py"):
        rel_parts = p.relative_to(repo_path).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if p.is_symlink() or not p.is_file():
            continue
        if p.stat().st_size > MAX_FILE_SIZE_KB * 1024:
            continue
        files.append(p)
    return sorted(files)[:MAX_PY_FILES]


def module_name(rel_path: Path) -> str:
    """src/pkg/mod.py -> src.pkg.mod ; pkg/__init__.py -> pkg"""
    parts = list(rel_path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def analyze_file(path: Path, rel: Path) -> dict:
    info = {
        "path": rel.as_posix(),
        "module": module_name(rel),
        "functions": [],
        "classes": [],
        "imports": [],
        "parse_error": None,
    }
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except SyntaxError as e:
        info["parse_error"] = f"SyntaxError line {e.lineno}: {e.msg}"
        return info

    info["lines"] = source.count("\n") + 1

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info["functions"].append({"name": node.name, "line": node.lineno})
        elif isinstance(node, ast.ClassDef):
            info["classes"].append({"name": node.name, "line": node.lineno})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                info["imports"].append({"module": alias.name, "level": 0, "line": node.lineno})
        elif isinstance(node, ast.ImportFrom):
            info["imports"].append({
                "module": node.module or "",
                "level": node.level,  # >0 means relative import
                "names": [a.name for a in node.names],
                "line": node.lineno,
            })
    return info


def _resolve_import(imp: dict, current_module: str, is_package: bool, known: set[str]) -> str | None:
    """Return the internal module name this import points to, or None if external/unresolved."""
    level, mod = imp["level"], imp["module"]

    if level > 0:
        base_parts = current_module.split(".") if current_module else []
        if not is_package:
            base_parts = base_parts[:-1]
        base_parts = base_parts[: len(base_parts) - (level - 1)] if level > 1 else base_parts
        candidate = ".".join(base_parts + ([mod] if mod else []))
        if candidate in known:
            return candidate
        # "from . import x" -> x may be a submodule
        for name in imp.get("names", []):
            sub = f"{candidate}.{name}" if candidate else name
            if sub in known:
                return sub
        return None

    # absolute import: try longest matching prefix that is an internal module
    parts = mod.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in known:
            return cand
    # "from pkg import submodule"
    for name in imp.get("names", []):
        cand = f"{mod}.{name}" if mod else name
        if cand in known:
            return cand
    return None


def analyze_repo(repo_path: Path) -> dict:
    py_files = find_python_files(repo_path)
    files = [analyze_file(p, p.relative_to(repo_path)) for p in py_files]

    known = {f["module"] for f in files if f["module"]}
    package_modules = {f["module"] for f in files if f["path"].endswith("__init__.py")}

    g = nx.DiGraph()
    for f in files:
        g.add_node(f["module"] or f["path"], kind="internal", path=f["path"])

    external = set()
    unresolved_relative = 0
    for f in files:
        src = f["module"] or f["path"]
        for imp in f["imports"]:
            target = _resolve_import(imp, f["module"], f["module"] in package_modules, known)
            if target and target != src:
                g.add_edge(src, target)
            elif imp["level"] > 0:
                unresolved_relative += 1
            elif imp["module"]:
                external.add(imp["module"].split(".")[0])

    return {
        "stats": {
            "python_files": len(files),
            "functions": sum(len(f["functions"]) for f in files),
            "classes": sum(len(f["classes"]) for f in files),
            "internal_edges": g.number_of_edges(),
            "parse_errors": sum(1 for f in files if f["parse_error"]),
        },
        "files": files,
        "graph": {
            "nodes": [{"id": n, "path": d.get("path")} for n, d in g.nodes(data=True)],
            "edges": [{"source": a, "target": b} for a, b in g.edges()],
        },
        "external_imports": sorted(external),
        "unresolved_relative_imports": unresolved_relative,
    }
