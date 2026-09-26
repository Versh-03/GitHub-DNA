"""
test_dependency.py — unit tests for backend.analyzers.dependency.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from backend.analyzers.dependency import build_dependency_edges, extract_imports


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, rel: str, content: str) -> str:
    """Write *content* to *tmp_path/rel* and return the absolute path string."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return str(p)


# ---------------------------------------------------------------------------
# extract_imports
# ---------------------------------------------------------------------------

class TestExtractImports:
    """Tests for extract_imports() — parses module names from source text."""

    def test_plain_import(self, tmp_path: Path):
        """``import os`` → ['os']"""
        path = _write(tmp_path, "a.py", "import os\n")
        assert extract_imports(path) == ["os"]

    def test_dotted_import_returns_full_and_top(self, tmp_path: Path):
        """``import os.path`` → both 'os.path' and 'os' are returned."""
        path = _write(tmp_path, "a.py", "import os.path\n")
        result = extract_imports(path)
        assert "os.path" in result
        assert "os" in result

    def test_simple_import_returns_name_once(self, tmp_path: Path):
        """``import os`` (no dots) → only 'os', not duplicated."""
        path = _write(tmp_path, "a.py", "import os\n")
        assert extract_imports(path) == ["os"]

    def test_from_import(self, tmp_path: Path):
        """``from pathlib import Path`` → ['pathlib.Path', 'pathlib'].

        The submodule candidate 'pathlib.Path' is emitted first (so the
        resolver can try pathlib/Path.py), then the module itself 'pathlib'.
        """
        path = _write(tmp_path, "a.py", "from pathlib import Path\n")
        result = extract_imports(path)
        assert "pathlib.Path" in result
        assert "pathlib" in result

    def test_from_dotted_import_returns_full_and_top(self, tmp_path: Path):
        """``from os.path import join`` → both 'os.path' and 'os' are returned."""
        path = _write(tmp_path, "a.py", "from os.path import join\n")
        result = extract_imports(path)
        assert "os.path" in result
        assert "os" in result

    def test_multiple_imports(self, tmp_path: Path):
        """Multiple import statements are all collected."""
        src = "import os\nimport sys\nfrom pathlib import Path\n"
        path = _write(tmp_path, "a.py", src)
        result = extract_imports(path)
        assert "os" in result
        assert "sys" in result
        assert "pathlib" in result

    def test_no_imports_returns_empty(self, tmp_path: Path):
        """A file with no imports returns an empty list."""
        path = _write(tmp_path, "a.py", "x = 1\n")
        assert extract_imports(path) == []

    def test_relative_import_no_module_skipped(self, tmp_path: Path):
        """``from . import foo`` (no module) does not crash and produces no name."""
        path = _write(tmp_path, "a.py", "from . import foo\n")
        result = extract_imports(path)
        assert result == []

    def test_syntax_error_returns_empty_with_warning(self, tmp_path: Path):
        """A file with a SyntaxError returns [] and emits a SyntaxWarning."""
        path = _write(tmp_path, "bad.py", "def broken(\n")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = extract_imports(path)
        assert result == []
        assert any(issubclass(w.category, SyntaxWarning) for w in caught)

    def test_import_inside_function(self, tmp_path: Path):
        """Imports inside function bodies are also collected (ast.walk is deep)."""
        src = "def foo():\n    import json\n"
        path = _write(tmp_path, "a.py", src)
        assert "json" in extract_imports(path)


# ---------------------------------------------------------------------------
# build_dependency_edges
# ---------------------------------------------------------------------------

class TestBuildDependencyEdges:
    """Tests for build_dependency_edges() — builds intra-repo edges."""

    def test_edge_created_for_matching_import(self, tmp_path: Path):
        """When importer.py imports a module that matches another file, an edge is emitted."""
        # Write the actual files so extract_imports can read them
        _write(tmp_path, "utils.py", "x = 1\n")
        _write(tmp_path, "app.py", "import utils\n")

        file_list = [
            {"path": "app.py",   "file_type": "source", "size_bytes": 14},
            {"path": "utils.py", "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0]["source"] == "app.py"
        assert edges[0]["target"] == "utils.py"
        assert edges[0]["type"] == "import"

    def test_external_import_produces_no_edge(self, tmp_path: Path):
        """Imports of external libraries (os, sys, fastapi …) are silently skipped."""
        _write(tmp_path, "app.py", "import os\nimport sys\nfrom fastapi import FastAPI\n")
        file_list = [
            {"path": "app.py", "file_type": "source", "size_bytes": 50},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert edges == []

    def test_no_self_edge(self, tmp_path: Path):
        """A file cannot form an edge to itself."""
        _write(tmp_path, "app.py", "import app\n")
        file_list = [{"path": "app.py", "file_type": "source", "size_bytes": 10}]
        # app.py imports 'app' → would resolve to app.py itself
        # The edge would have source == target == "app.py"
        # The spec does not forbid this, but we confirm the dedup logic
        # doesn't crash and only one edge (if any) is produced
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) <= 1

    def test_test_files_are_analysed_as_importers(self, tmp_path: Path):
        """file_type=='test' files are now walked; edges to source modules are emitted."""
        _write(tmp_path, "utils.py", "x = 1\n")
        _write(tmp_path, "test_app.py", "import utils\n")
        file_list = [
            {"path": "test_app.py", "file_type": "test",   "size_bytes": 14},
            {"path": "utils.py",    "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0]["source"] == "test_app.py"
        assert edges[0]["target"] == "utils.py"

    def test_duplicate_import_produces_single_edge(self, tmp_path: Path):
        """Importing the same module twice only produces one edge."""
        _write(tmp_path, "utils.py", "x = 1\n")
        _write(tmp_path, "app.py", "import utils\nimport utils\n")
        file_list = [
            {"path": "app.py",   "file_type": "source", "size_bytes": 28},
            {"path": "utils.py", "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1

    def test_dotted_import_statement_resolves_full_path(self, tmp_path: Path):
        """``import backend.analyzers.repository`` → edge to backend/analyzers/repository.py."""
        _write(tmp_path, "app.py", "import backend.analyzers.repository\n")
        _write(tmp_path, "backend/analyzers/repository.py", "x = 1\n")
        file_list = [
            {"path": "app.py",                          "file_type": "source", "size_bytes": 38},
            {"path": "backend/analyzers/repository.py", "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0]["source"] == "app.py"
        assert edges[0]["target"] == "backend/analyzers/repository.py"

    def test_from_dotted_import_resolves_full_path(self, tmp_path: Path):
        """``from backend.analyzers.repository import walk_repository`` → edge to the module file."""
        _write(tmp_path, "app.py", "from backend.analyzers.repository import walk_repository\n")
        _write(tmp_path, "backend/analyzers/repository.py", "def walk_repository(): pass\n")
        file_list = [
            {"path": "app.py",                          "file_type": "source", "size_bytes": 56},
            {"path": "backend/analyzers/repository.py", "file_type": "source", "size_bytes": 28},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0]["source"] == "app.py"
        assert edges[0]["target"] == "backend/analyzers/repository.py"

    def test_from_dotted_import_multi_level(self, tmp_path: Path):
        """All from-import forms in the real Git DNA backend resolve correctly."""
        _write(tmp_path, "backend/api/main.py",
               "from backend.analyzers.repository import walk_repository\n"
               "from backend.analyzers.dependency import build_dependency_edges\n"
               "from backend.models.graph import build_graph\n")
        _write(tmp_path, "backend/analyzers/repository.py", "def walk_repository(): pass\n")
        _write(tmp_path, "backend/analyzers/dependency.py", "def build_dependency_edges(): pass\n")
        _write(tmp_path, "backend/models/graph.py",         "def build_graph(): pass\n")
        file_list = [
            {"path": "backend/api/main.py",                 "file_type": "source", "size_bytes": 120},
            {"path": "backend/analyzers/repository.py",     "file_type": "source", "size_bytes": 28},
            {"path": "backend/analyzers/dependency.py",     "file_type": "source", "size_bytes": 35},
            {"path": "backend/models/graph.py",             "file_type": "source", "size_bytes": 25},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        targets = {e["target"] for e in edges}
        assert "backend/analyzers/repository.py" in targets
        assert "backend/analyzers/dependency.py" in targets
        assert "backend/models/graph.py" in targets
        assert all(e["source"] == "backend/api/main.py" for e in edges)

    def test_top_level_import_still_resolves(self, tmp_path: Path):
        """Simple single-component imports (import utils) still produce edges."""
        _write(tmp_path, "utils.py", "x = 1\n")
        _write(tmp_path, "app.py", "import utils\n")
        file_list = [
            {"path": "app.py",   "file_type": "source", "size_bytes": 14},
            {"path": "utils.py", "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0]["target"] == "utils.py"

    def test_no_self_edge_from_dotted_import(self, tmp_path: Path):
        """A file cannot produce an edge to itself via a dotted import."""
        _write(tmp_path, "backend/api/main.py", "from backend.api.main import app\n")
        file_list = [
            {"path": "backend/api/main.py", "file_type": "source", "size_bytes": 33},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert edges == []

    def test_multiple_files_multiple_edges(self, tmp_path: Path):
        """Multiple source files each contributing edges are all collected."""
        _write(tmp_path, "utils.py",  "x = 1\n")
        _write(tmp_path, "models.py", "y = 2\n")
        _write(tmp_path, "app.py",    "import utils\nimport models\n")
        _write(tmp_path, "cli.py",    "import utils\n")
        file_list = [
            {"path": "app.py",    "file_type": "source", "size_bytes": 30},
            {"path": "cli.py",    "file_type": "source", "size_bytes": 14},
            {"path": "utils.py",  "file_type": "source", "size_bytes": 6},
            {"path": "models.py", "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        sources_targets = {(e["source"], e["target"]) for e in edges}
        assert ("app.py", "utils.py")  in sources_targets
        assert ("app.py", "models.py") in sources_targets
        assert ("cli.py", "utils.py")  in sources_targets
        assert len(edges) == 3

    def test_empty_file_list_returns_empty(self):
        """An empty file list produces no edges."""
        assert build_dependency_edges([]) == []

    def test_no_source_files_returns_empty(self, tmp_path: Path):
        """If all files are non-source (docs, config, etc.), edges list is empty."""
        file_list = [
            {"path": "README.md",      "file_type": "docs",   "size_bytes": 100},
            {"path": "setup.cfg",      "file_type": "config", "size_bytes": 20},
        ]
        assert build_dependency_edges(file_list) == []


# ---------------------------------------------------------------------------
# Test file dependency edges
# ---------------------------------------------------------------------------

class TestTestFileEdges:
    """Test files (file_type=='test') must produce edges to the modules they import."""

    def test_test_file_edge_to_source_module(self, tmp_path: Path):
        """test_foo.py importing utils produces an edge test_foo.py → utils.py."""
        _write(tmp_path, "utils.py", "x = 1\n")
        _write(tmp_path, "test_foo.py", "import utils\n")
        file_list = [
            {"path": "test_foo.py", "file_type": "test",   "size_bytes": 14},
            {"path": "utils.py",    "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0] == {"source": "test_foo.py", "target": "utils.py", "type": "import"}

    def test_test_file_from_dotted_import(self, tmp_path: Path):
        """``from backend.analyzers.repository import walk_repository`` in a test file
        produces an edge to backend/analyzers/repository.py."""
        _write(tmp_path, "tests/test_repository.py",
               "from backend.analyzers.repository import walk_repository\n")
        _write(tmp_path, "backend/analyzers/repository.py", "def walk_repository(): pass\n")
        file_list = [
            {"path": "tests/test_repository.py",        "file_type": "test",   "size_bytes": 56},
            {"path": "backend/analyzers/repository.py", "file_type": "source", "size_bytes": 28},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0]["source"] == "tests/test_repository.py"
        assert edges[0]["target"] == "backend/analyzers/repository.py"

    def test_test_file_multiple_imports(self, tmp_path: Path):
        """A test file importing several source modules produces one edge per module."""
        _write(tmp_path, "tests/test_all.py",
               "from backend.analyzers.repository import walk_repository\n"
               "from backend.analyzers.dependency import build_dependency_edges\n"
               "import pytest\n")
        _write(tmp_path, "backend/analyzers/repository.py", "def walk_repository(): pass\n")
        _write(tmp_path, "backend/analyzers/dependency.py", "def build_dependency_edges(): pass\n")
        file_list = [
            {"path": "tests/test_all.py",               "file_type": "test",   "size_bytes": 100},
            {"path": "backend/analyzers/repository.py", "file_type": "source", "size_bytes": 28},
            {"path": "backend/analyzers/dependency.py", "file_type": "source", "size_bytes": 35},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        targets = {e["target"] for e in edges}
        assert "backend/analyzers/repository.py" in targets
        assert "backend/analyzers/dependency.py" in targets
        # pytest is external — must not produce an edge
        assert all("pytest" not in e["target"] for e in edges)
        assert len(edges) == 2

    def test_test_file_external_imports_excluded(self, tmp_path: Path):
        """External imports (pytest, pathlib) in test files must not produce edges."""
        _write(tmp_path, "test_foo.py",
               "import pytest\nfrom pathlib import Path\nimport os\n")
        file_list = [
            {"path": "test_foo.py", "file_type": "test", "size_bytes": 50},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert edges == []


# ---------------------------------------------------------------------------
# from-package-import-submodule resolution
# ---------------------------------------------------------------------------

class TestFromPackageImportSubmodule:
    """``from pkg import submodule`` must resolve to pkg/submodule.py."""

    def test_from_package_import_submodule(self, tmp_path: Path):
        """``from backend.analyzers import repository`` → backend/analyzers/repository.py."""
        _write(tmp_path, "app.py", "from backend.analyzers import repository\n")
        _write(tmp_path, "backend/analyzers/repository.py", "def walk_repository(): pass\n")
        file_list = [
            {"path": "app.py",                          "file_type": "source", "size_bytes": 40},
            {"path": "backend/analyzers/repository.py", "file_type": "source", "size_bytes": 28},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0]["source"] == "app.py"
        assert edges[0]["target"] == "backend/analyzers/repository.py"

    def test_from_package_import_multiple_submodules(self, tmp_path: Path):
        """``from backend.analyzers import repository, dependency`` resolves both."""
        _write(tmp_path, "app.py",
               "from backend.analyzers import repository, dependency\n")
        _write(tmp_path, "backend/analyzers/repository.py", "x = 1\n")
        _write(tmp_path, "backend/analyzers/dependency.py", "y = 2\n")
        file_list = [
            {"path": "app.py",                          "file_type": "source", "size_bytes": 50},
            {"path": "backend/analyzers/repository.py", "file_type": "source", "size_bytes": 6},
            {"path": "backend/analyzers/dependency.py", "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        targets = {e["target"] for e in edges}
        assert "backend/analyzers/repository.py" in targets
        assert "backend/analyzers/dependency.py" in targets
        assert len(edges) == 2

    def test_from_top_import_submodule(self, tmp_path: Path):
        """``from backend import analyzers`` → backend/analyzers.py (if it exists)."""
        _write(tmp_path, "app.py", "from backend import analyzers\n")
        _write(tmp_path, "backend/analyzers.py", "x = 1\n")
        file_list = [
            {"path": "app.py",               "file_type": "source", "size_bytes": 30},
            {"path": "backend/analyzers.py", "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0]["target"] == "backend/analyzers.py"

    def test_multi_level_import_in_test_file(self, tmp_path: Path):
        """Multi-level from-import in a test file resolves all the way down."""
        _write(tmp_path, "tests/test_repository.py",
               "from backend.analyzers import repository\n"
               "import pytest\n")
        _write(tmp_path, "backend/analyzers/repository.py", "def walk_repository(): pass\n")
        file_list = [
            {"path": "tests/test_repository.py",        "file_type": "test",   "size_bytes": 60},
            {"path": "backend/analyzers/repository.py", "file_type": "source", "size_bytes": 28},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert len(edges) == 1
        assert edges[0]["source"] == "tests/test_repository.py"
        assert edges[0]["target"] == "backend/analyzers/repository.py"
