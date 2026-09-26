"""
test_git_history.py — unit tests for backend.analyzers.git_history.
"""

from __future__ import annotations

from pathlib import Path

import git
import pytest

from backend.analyzers.git_history import analyze_git_history


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AUTHOR_A = git.Actor("Alice", "alice@example.com")
_AUTHOR_B = git.Actor("Bob",   "bob@example.com")


def _commit(repo: git.Repo, files: dict[str, str], author: git.Actor) -> None:
    """Write *files* ({rel_path: content}) into *repo*, stage, and commit."""
    for rel, content in files.items():
        p = Path(repo.working_dir) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        repo.index.add([rel])
    repo.index.commit(
        f"add {', '.join(files)}",
        author=author,
        committer=author,
    )


# ---------------------------------------------------------------------------
# Fixture: small synthetic repo
# ---------------------------------------------------------------------------

@pytest.fixture()
def tiny_repo(tmp_path: Path) -> git.Repo:
    """Return an initialised git repo with 3 commits across 2 files and 2 authors.

    Commit history (newest last):
      1. alice adds app.py
      2. alice adds utils.py + modifies app.py
      3. bob   modifies app.py
    """
    repo = git.Repo.init(tmp_path)

    _commit(repo, {"app.py": "x = 1\n"},               _AUTHOR_A)
    _commit(repo, {"utils.py": "y = 2\n", "app.py": "x = 2\n"}, _AUTHOR_A)
    _commit(repo, {"app.py": "x = 3\n"},               _AUTHOR_B)

    return repo


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestAnalyzeGitHistory:

    def test_total_commits(self, tiny_repo: git.Repo):
        result = analyze_git_history(tiny_repo.working_dir)
        assert result["total_commits"] == 3

    def test_contributor_count(self, tiny_repo: git.Repo):
        result = analyze_git_history(tiny_repo.working_dir)
        assert result["contributor_count"] == 2

    def test_file_commit_counts_app(self, tiny_repo: git.Repo):
        """app.py appears in all 3 commits."""
        result = analyze_git_history(tiny_repo.working_dir)
        assert result["file_commit_counts"]["app.py"] == 3

    def test_file_commit_counts_utils(self, tiny_repo: git.Repo):
        """utils.py appears in 1 commit."""
        result = analyze_git_history(tiny_repo.working_dir)
        assert result["file_commit_counts"]["utils.py"] == 1

    def test_top_changed_files_order(self, tiny_repo: git.Repo):
        """top_changed_files must be sorted by commit_count descending."""
        result = analyze_git_history(tiny_repo.working_dir)
        top = result["top_changed_files"]
        assert len(top) >= 1
        assert top[0]["path"] == "app.py"
        assert top[0]["commit_count"] == 3

    def test_top_changed_files_shape(self, tiny_repo: git.Repo):
        """Every entry in top_changed_files has 'path' and 'commit_count' keys."""
        result = analyze_git_history(tiny_repo.working_dir)
        for entry in result["top_changed_files"]:
            assert "path" in entry
            assert "commit_count" in entry
            assert isinstance(entry["commit_count"], int)

    def test_result_keys_present(self, tiny_repo: git.Repo):
        """All four expected keys are present in the result."""
        result = analyze_git_history(tiny_repo.working_dir)
        for key in ("total_commits", "contributor_count",
                    "file_commit_counts", "top_changed_files"):
            assert key in result, f"Missing key: {key}"

    def test_top_changed_files_capped_at_10(self, tmp_path: Path):
        """top_changed_files never exceeds 10 entries, even with 15 distinct files."""
        repo = git.Repo.init(tmp_path)
        # Create 15 files, each in its own commit
        for i in range(15):
            _commit(repo, {f"file{i}.py": f"x = {i}\n"}, _AUTHOR_A)
        result = analyze_git_history(str(tmp_path))
        assert len(result["top_changed_files"]) <= 10


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------

class TestAnalyzeGitHistoryErrors:

    def test_non_git_directory_returns_error_key(self, tmp_path: Path):
        """A plain (non-git) directory must return an 'error' key."""
        result = analyze_git_history(str(tmp_path))
        assert "error" in result

    def test_non_git_directory_empty_counts(self, tmp_path: Path):
        """Error result must still contain the standard zero-value keys."""
        result = analyze_git_history(str(tmp_path))
        assert result["total_commits"] == 0
        assert result["contributor_count"] == 0
        assert result["file_commit_counts"] == {}
        assert result["top_changed_files"] == []

    def test_nonexistent_path_returns_error_key(self, tmp_path: Path):
        """A path that does not exist must return an 'error' key."""
        missing = str(tmp_path / "does_not_exist")
        result = analyze_git_history(missing)
        assert "error" in result
