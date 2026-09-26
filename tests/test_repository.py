"""
test_repository.py — unit tests for backend.analyzers.repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.analyzers.repository import walk_repository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tree(tmp_path: Path) -> dict[str, Path]:
    """Create a small synthetic directory tree and return a name → Path map."""
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

    # .git directory — must be excluded
    touch(".git/HEAD", "ref: refs/heads/main")
    touch(".git/config", "[core]")

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


class TestGitExclusion:
    """The .git/ directory must never appear in results."""

    def test_git_directory_excluded(self, tmp_path: Path):
        _make_tree(tmp_path)
        results = walk_repository(str(tmp_path))
        paths = [r["path"] for r in results]
        assert not any(p.startswith(".git") for p in paths), (
            f"Found .git entries: {[p for p in paths if p.startswith('.git')]}"
        )


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
