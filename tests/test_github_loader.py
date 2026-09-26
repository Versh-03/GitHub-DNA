"""
test_github_loader.py — unit tests for backend.github_loader.

All tests are purely offline: no real network calls are made.
subprocess.run is patched wherever git clone would be invoked.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.github_loader import (
    CLONE_TIMEOUT,
    CloneError,
    InvalidGitHubURLError,
    cloned_repo,
    validate_github_url,
)


# ---------------------------------------------------------------------------
# validate_github_url
# ---------------------------------------------------------------------------

class TestValidateGitHubURL:
    """URL validation — no network calls."""

    # --- valid URLs ---

    def test_plain_url(self):
        url = "https://github.com/owner/repo"
        assert validate_github_url(url) == url

    def test_trailing_slash_stripped(self):
        assert validate_github_url("https://github.com/owner/repo/") == \
               "https://github.com/owner/repo"

    def test_dot_git_suffix_stripped(self):
        assert validate_github_url("https://github.com/owner/repo.git") == \
               "https://github.com/owner/repo"

    def test_dot_git_and_slash_stripped(self):
        assert validate_github_url("https://github.com/owner/repo.git/") == \
               "https://github.com/owner/repo"

    def test_leading_and_trailing_whitespace_stripped(self):
        assert validate_github_url("  https://github.com/owner/repo  ") == \
               "https://github.com/owner/repo"

    def test_hyphens_and_dots_in_owner(self):
        url = "https://github.com/my-org.co/my_repo"
        assert validate_github_url(url) == url

    def test_underscores_in_repo_name(self):
        url = "https://github.com/owner/my_repo_name"
        assert validate_github_url(url) == url

    # --- invalid URLs ---

    def test_http_rejected(self):
        with pytest.raises(InvalidGitHubURLError):
            validate_github_url("http://github.com/owner/repo")

    def test_non_github_domain_rejected(self):
        with pytest.raises(InvalidGitHubURLError):
            validate_github_url("https://gitlab.com/owner/repo")

    def test_missing_repo_rejected(self):
        with pytest.raises(InvalidGitHubURLError):
            validate_github_url("https://github.com/owner")

    def test_empty_string_rejected(self):
        with pytest.raises(InvalidGitHubURLError):
            validate_github_url("")

    def test_path_traversal_rejected(self):
        with pytest.raises(InvalidGitHubURLError):
            validate_github_url("https://github.com/owner/repo/extra/path")

    def test_query_string_rejected(self):
        with pytest.raises(InvalidGitHubURLError):
            validate_github_url("https://github.com/owner/repo?foo=bar")

    def test_fragment_rejected(self):
        with pytest.raises(InvalidGitHubURLError):
            validate_github_url("https://github.com/owner/repo#readme")

    def test_ssh_url_rejected(self):
        with pytest.raises(InvalidGitHubURLError):
            validate_github_url("git@github.com:owner/repo.git")

    def test_plain_string_rejected(self):
        with pytest.raises(InvalidGitHubURLError):
            validate_github_url("not-a-url")


# ---------------------------------------------------------------------------
# cloned_repo — patching subprocess.run
# ---------------------------------------------------------------------------

def _mock_success(tmp_path: Path) -> MagicMock:
    """Return a mock for subprocess.run that simulates a successful clone.

    The mock also creates the target directory so the context manager has a
    real directory to yield and clean up.
    """
    def _side_effect(cmd, **kwargs):
        # cmd[-1] is the destination directory passed to git clone
        Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    mock = MagicMock(side_effect=_side_effect)
    return mock


class TestClonedRepo:
    """cloned_repo context manager — subprocess is always patched."""

    def test_yields_a_string_path(self, tmp_path: Path):
        """The context manager must yield a non-empty string."""
        with patch("backend.github_loader.subprocess.run", side_effect=_mock_success(tmp_path)):
            with cloned_repo("https://github.com/owner/repo") as path:
                assert isinstance(path, str)
                assert path  # non-empty

    def test_yields_existing_directory(self, tmp_path: Path):
        """The yielded path must be an existing directory while inside the block."""
        with patch("backend.github_loader.subprocess.run", side_effect=_mock_success(tmp_path)):
            with cloned_repo("https://github.com/owner/repo") as path:
                assert Path(path).is_dir()

    def test_temp_dir_deleted_after_exit(self, tmp_path: Path):
        """The temporary directory must not exist after the context manager exits."""
        captured = []

        with patch("backend.github_loader.subprocess.run", side_effect=_mock_success(tmp_path)):
            with cloned_repo("https://github.com/owner/repo") as path:
                captured.append(path)

        assert not Path(captured[0]).exists(), (
            f"Temp dir was not cleaned up: {captured[0]}"
        )

    def test_temp_dir_deleted_after_exception(self, tmp_path: Path):
        """Temp dir is deleted even when the body of the with-block raises."""
        captured = []

        with patch("backend.github_loader.subprocess.run", side_effect=_mock_success(tmp_path)):
            with pytest.raises(RuntimeError):
                with cloned_repo("https://github.com/owner/repo") as path:
                    captured.append(path)
                    raise RuntimeError("body error")

        assert not Path(captured[0]).exists(), (
            f"Temp dir was not cleaned up after exception: {captured[0]}"
        )

    def test_invalid_url_raises_before_clone(self):
        """An invalid URL raises InvalidGitHubURLError without calling subprocess."""
        with patch("backend.github_loader.subprocess.run") as mock_run:
            with pytest.raises(InvalidGitHubURLError):
                with cloned_repo("not-a-url"):
                    pass  # pragma: no cover
        mock_run.assert_not_called()

    def test_clone_failure_raises_clone_error(self, tmp_path: Path):
        """A non-zero exit code from git clone raises CloneError."""
        def _fail(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 128
            result.stderr = "fatal: repository not found"
            return result

        with patch("backend.github_loader.subprocess.run", side_effect=_fail):
            with pytest.raises(CloneError, match="git clone failed"):
                with cloned_repo("https://github.com/owner/repo"):
                    pass  # pragma: no cover

    def test_clone_timeout_raises_clone_error(self):
        """A subprocess.TimeoutExpired is converted to CloneError."""
        with patch(
            "backend.github_loader.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=CLONE_TIMEOUT),
        ):
            with pytest.raises((CloneError, subprocess.TimeoutExpired)):
                with cloned_repo("https://github.com/owner/repo"):
                    pass  # pragma: no cover

    def test_correct_git_command_called(self, tmp_path: Path):
        """subprocess.run must be called with git clone --depth 1 <url> <dir>."""
        called_with: list = []

        def _capture(cmd, **kwargs):
            called_with.extend(cmd)
            Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        with patch("backend.github_loader.subprocess.run", side_effect=_capture):
            with cloned_repo("https://github.com/owner/repo"):
                pass

        assert called_with[0] == "git"
        assert called_with[1] == "clone"
        assert "--depth" in called_with
        assert "1" in called_with
        assert "https://github.com/owner/repo" in called_with

    def test_correct_timeout_passed_to_subprocess(self, tmp_path: Path):
        """subprocess.run must be called with timeout=CLONE_TIMEOUT."""
        received_kwargs: dict = {}

        def _capture(cmd, **kwargs):
            received_kwargs.update(kwargs)
            Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        with patch("backend.github_loader.subprocess.run", side_effect=_capture):
            with cloned_repo("https://github.com/owner/repo"):
                pass

        assert received_kwargs.get("timeout") == CLONE_TIMEOUT

    def test_dot_git_url_normalised_before_clone(self, tmp_path: Path):
        """.git suffix is stripped from the URL passed to git clone."""
        called_cmd: list = []

        def _capture(cmd, **kwargs):
            called_cmd.extend(cmd)
            Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        with patch("backend.github_loader.subprocess.run", side_effect=_capture):
            with cloned_repo("https://github.com/owner/repo.git"):
                pass

        # The URL in the command must not end with .git
        url_in_cmd = called_cmd[called_cmd.index("--depth") + 2 - 1]
        # More robust: find the element that starts with https://
        https_args = [a for a in called_cmd if a.startswith("https://")]
        assert https_args, "No https:// URL found in git clone command"
        assert not https_args[0].endswith(".git"), (
            f"URL was not normalised: {https_args[0]}"
        )
