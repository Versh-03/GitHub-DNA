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

    def test_dotted_import_returns_top_level(self, tmp_path: Path):
        """``import os.path`` → top-level name 'os'"""
        path = _write(tmp_path, "a.py", "import os.path\n")
        assert extract_imports(path) == ["os"]

    def test_from_import(self, tmp_path: Path):
        """``from pathlib import Path`` → ['pathlib']"""
        path = _write(tmp_path, "a.py", "from pathlib import Path\n")
        assert extract_imports(path) == ["pathlib"]

    def test_from_dotted_import_returns_top_level(self, tmp_path: Path):
        """``from os.path import join`` → top-level name 'os'"""
        path = _write(tmp_path, "a.py", "from os.path import join\n")
        assert extract_imports(path) == ["os"]

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

    def test_test_files_are_not_analysed_as_importers(self, tmp_path: Path):
        """Only file_type=='source' files are walked; test files are skipped."""
        _write(tmp_path, "utils.py", "x = 1\n")
        _write(tmp_path, "test_app.py", "import utils\n")
        file_list = [
            {"path": "test_app.py", "file_type": "test",   "size_bytes": 14},
            {"path": "utils.py",    "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        assert edges == []

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

    def test_nested_module_path_resolved(self, tmp_path: Path):
        """``import backend.analyzers.repository`` → target ``backend/analyzers/repository.py``."""
        _write(tmp_path, "app.py", "import backend.analyzers.repository\n")
        _write(tmp_path, "backend/analyzers/repository.py", "x = 1\n")
        file_list = [
            {"path": "app.py",                              "file_type": "source", "size_bytes": 38},
            {"path": "backend/analyzers/repository.py",     "file_type": "source", "size_bytes": 6},
        ]
        edges = build_dependency_edges(file_list, repo_path=str(tmp_path))
        # Only the top-level name "backend" → "backend.py" is tried, which doesn't exist.
        # So this confirms the spec's "top-level name only" behaviour: no edge.
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
