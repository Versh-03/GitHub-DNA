"""
test_repository.py — unit tests for backend.analyzers.repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.analyzers.repository import walk_repository, _IGNORED_DIRS, _IGNORED_EXTENSIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tree(tmp_path: Path) -> dict[str, Path]:
    """Create a small synthetic directory tree and return a name → Path map.

    Includes files inside every ignored directory so the exclusion tests
    have real content to assert against.
    """
    files: dict[str, Path] = {}

    def touch(rel: str, content: str = "") -> Path:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        files[rel] = p
        return p

    # Source files
    touch("app.py", "# source")
    touch("utils/helpers.py", "# source")

    # Test files — detected by filename prefix
    touch("test_app.py", "# test by name")

    # Test files — detected by directory component
    touch("tests/test_helpers.py", "# test by dir")
    touch("test/unit/core.py", "# test by dir component")

    # Docs
    touch("README.md", "# readme")
    touch("docs/guide.rst", "# guide")
    touch("CHANGES.txt", "changes")

    # Config
    touch("setup.cfg", "[metadata]")
    touch("pyproject.toml", "[build-system]")
    touch("config/settings.yaml", "key: value")
    touch("config/db.json", "{}")
    touch("config/app.yml", "---")
    touch(".env.ini", "FOO=bar")

    # Other
    touch("Makefile", "all:")
    touch("data/dump.csv", "a,b,c")

    # Ignored directories — must all be excluded from results
    touch(".git/HEAD", "ref: refs/heads/main")
    touch(".git/config", "[core]")
    touch(".venv/lib/site-packages/requests/__init__.py", "# venv pkg")
    touch("venv/lib/site-packages/flask/__init__.py", "# venv pkg")
    touch("env/Scripts/activate", "# env activate")
    touch("node_modules/.bin/vite", "#!/usr/bin/env node")
    touch("node_modules/react/index.js", "// react")
    touch("__pycache__/app.cpython-313.pyc", "\x00bytecode")
    touch("utils/__pycache__/helpers.cpython-313.pyc", "\x00bytecode")
    touch(".pytest_cache/v/cache/lastfailed", "{}")
    touch(".mypy_cache/3.13/builtins.json", "{}")
    touch("dist/app-1.0.tar.gz", "binary")
    touch("build/lib/app.py", "# built")

    return files


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFileTypeClassification:
    """Each rule is tested in isolation."""

    def _result_map(self, tmp_path: Path) -> dict[str, dict]:
        """Return {relative_posix_path: file_dict} for easy lookup."""
        _make_tree(tmp_path)
        return {r["path"]: r for r in walk_repository(str(tmp_path))}

    def test_plain_python_is_source(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["app.py"]["file_type"] == "source"
        assert results["utils/helpers.py"]["file_type"] == "source"

    def test_test_prefix_filename_is_test(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["test_app.py"]["file_type"] == "test"

    def test_tests_directory_component_is_test(self, tmp_path: Path):
        """Files inside a 'tests/' directory must be classified as test."""
        results = self._result_map(tmp_path)
        assert results["tests/test_helpers.py"]["file_type"] == "test"

    def test_test_directory_component_is_test(self, tmp_path: Path):
        """Files inside a 'test/' directory (singular) must be classified as test."""
        results = self._result_map(tmp_path)
        assert results["test/unit/core.py"]["file_type"] == "test"

    def test_test_takes_priority_over_source(self, tmp_path: Path):
        """A .py file inside a test directory must be 'test', not 'source'."""
        results = self._result_map(tmp_path)
        # tests/test_helpers.py and test/unit/core.py are both .py but are "test"
        assert results["tests/test_helpers.py"]["file_type"] == "test"
        assert results["test/unit/core.py"]["file_type"] == "test"

    def test_markdown_is_docs(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["README.md"]["file_type"] == "docs"

    def test_rst_is_docs(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["docs/guide.rst"]["file_type"] == "docs"

    def test_txt_is_docs(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["CHANGES.txt"]["file_type"] == "docs"

    def test_cfg_is_config(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["setup.cfg"]["file_type"] == "config"

    def test_toml_is_config(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["pyproject.toml"]["file_type"] == "config"

    def test_yaml_is_config(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["config/settings.yaml"]["file_type"] == "config"

    def test_json_is_config(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["config/db.json"]["file_type"] == "config"

    def test_yml_is_config(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["config/app.yml"]["file_type"] == "config"

    def test_ini_is_config(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results[".env.ini"]["file_type"] == "config"

    def test_unknown_extension_is_other(self, tmp_path: Path):
        results = self._result_map(tmp_path)
        assert results["Makefile"]["file_type"] == "other"
        assert results["data/dump.csv"]["file_type"] == "other"


class TestIgnoredDirectories:
    """All directories in _IGNORED_DIRS must never appear in results."""

    def _paths(self, tmp_path: Path) -> list[str]:
        _make_tree(tmp_path)
        return [r["path"] for r in walk_repository(str(tmp_path))]

    def test_git_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any(p.startswith(".git/") or p == ".git" for p in paths), (
            f"Found .git entries: {[p for p in paths if '.git' in p.split('/')]}"
        )

    def test_venv_dot_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any(".venv" in p.split("/") for p in paths), (
            f"Found .venv entries: {[p for p in paths if '.venv' in p.split('/')]}"
        )

    def test_venv_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any("venv" in p.split("/") for p in paths), (
            f"Found venv entries: {[p for p in paths if 'venv' in p.split('/')]}"
        )

    def test_env_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any("env" in p.split("/") for p in paths), (
            f"Found env entries: {[p for p in paths if 'env' in p.split('/')]}"
        )

    def test_node_modules_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any("node_modules" in p.split("/") for p in paths), (
            f"Found node_modules entries: {[p for p in paths if 'node_modules' in p.split('/')]}"
        )

    def test_pycache_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any("__pycache__" in p.split("/") for p in paths), (
            f"Found __pycache__ entries: {[p for p in paths if '__pycache__' in p.split('/')]}"
        )

    def test_pytest_cache_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any(".pytest_cache" in p.split("/") for p in paths), (
            f"Found .pytest_cache entries: {[p for p in paths if '.pytest_cache' in p.split('/')]}"
        )

    def test_mypy_cache_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any(".mypy_cache" in p.split("/") for p in paths), (
            f"Found .mypy_cache entries: {[p for p in paths if '.mypy_cache' in p.split('/')]}"
        )

    def test_dist_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any("dist" in p.split("/") for p in paths), (
            f"Found dist entries: {[p for p in paths if 'dist' in p.split('/')]}"
        )

    def test_build_excluded(self, tmp_path: Path):
        paths = self._paths(tmp_path)
        assert not any("build" in p.split("/") for p in paths), (
            f"Found build entries: {[p for p in paths if 'build' in p.split('/')]}"
        )

    def test_nested_pycache_excluded(self, tmp_path: Path):
        """__pycache__ nested under a source dir must also be excluded."""
        paths = self._paths(tmp_path)
        assert "utils/__pycache__/helpers.cpython-313.pyc" not in paths

    def test_ignored_dirs_set_is_complete(self, tmp_path: Path):
        """All required names are present in _IGNORED_DIRS."""
        required = {
            ".git", ".venv", "venv", "env", "node_modules",
            "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build",
        }
        assert required.issubset(_IGNORED_DIRS), (
            f"Missing from _IGNORED_DIRS: {required - _IGNORED_DIRS}"
        )

    def test_real_source_files_still_present(self, tmp_path: Path):
        """Ignoring generated dirs must not suppress regular source files."""
        paths = self._paths(tmp_path)
        assert "app.py" in paths
        assert "utils/helpers.py" in paths


class TestBytecodeExclusion:
    """Compiled .pyc/.pyo files must never appear in walk results."""

    def test_pyc_at_root_excluded(self, tmp_path: Path):
        """A .pyc file sitting directly at the repo root is excluded."""
        (tmp_path / "app.pyc").write_bytes(b"\x00bytecode")
        (tmp_path / "app.py").write_text("x = 1")
        results = walk_repository(str(tmp_path))
        paths = [r["path"] for r in results]
        assert "app.pyc" not in paths
        assert "app.py" in paths

    def test_pyo_excluded(self, tmp_path: Path):
        """A .pyo file is also excluded."""
        (tmp_path / "app.pyo").write_bytes(b"\x00bytecode")
        results = walk_repository(str(tmp_path))
        paths = [r["path"] for r in results]
        assert "app.pyo" not in paths

    def test_pyc_in_subdir_excluded(self, tmp_path: Path):
        """A .pyc in a source subdirectory (outside __pycache__) is excluded."""
        sub = tmp_path / "utils"
        sub.mkdir()
        (sub / "helpers.pyc").write_bytes(b"\x00")
        (sub / "helpers.py").write_text("x = 1")
        results = walk_repository(str(tmp_path))
        paths = [r["path"] for r in results]
        assert "utils/helpers.pyc" not in paths
        assert "utils/helpers.py" in paths

    def test_ignored_extensions_set_contains_pyc_and_pyo(self):
        """_IGNORED_EXTENSIONS must contain both .pyc and .pyo."""
        assert ".pyc" in _IGNORED_EXTENSIONS
        assert ".pyo" in _IGNORED_EXTENSIONS


class TestRelativePaths:
    """Returned paths must be relative, not absolute."""

    def test_paths_are_relative(self, tmp_path: Path):
        _make_tree(tmp_path)
        results = walk_repository(str(tmp_path))
        for r in results:
            assert not Path(r["path"]).is_absolute(), (
                f"Expected relative path but got: {r['path']}"
            )

    def test_paths_use_posix_separators(self, tmp_path: Path):
        _make_tree(tmp_path)
        results = walk_repository(str(tmp_path))
        for r in results:
            assert "\\" not in r["path"], (
                f"Path contains backslash: {r['path']}"
            )


class TestSizeBytes:
    """size_bytes must be a non-negative integer."""

    def test_size_bytes_present_and_non_negative(self, tmp_path: Path):
        _make_tree(tmp_path)
        results = walk_repository(str(tmp_path))
        for r in results:
            assert isinstance(r["size_bytes"], int), (
                f"size_bytes is not int for {r['path']}"
            )
            assert r["size_bytes"] >= 0, (
                f"Negative size_bytes for {r['path']}"
            )
