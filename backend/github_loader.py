"""
github_loader.py — thin layer that clones a public GitHub repository into a
temporary directory and yields the local path for the analysis pipeline.

Design constraints:
  - No code from the cloned repo is ever executed.
  - The temporary directory is always cleaned up, even on failure.
  - No authentication; public repos only.
  - The existing analysis pipeline receives a plain local filesystem path.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Generator

# Matches https://github.com/<owner>/<repo> with an optional .git suffix
# and optional trailing slash.  Query strings / fragments are rejected.
_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+"
    r"(?:\.git)?/?$"
)

# Maximum seconds to wait for `git clone` to complete.
CLONE_TIMEOUT = 120


class InvalidGitHubURLError(ValueError):
    """Raised when the supplied string is not a valid public GitHub HTTPS URL."""


class CloneError(RuntimeError):
    """Raised when `git clone` exits with a non-zero status."""


def validate_github_url(url: str) -> str:
    """Return the normalised URL (trailing slash / .git stripped) or raise.

    Raises
    ------
    InvalidGitHubURLError
        If *url* does not match the expected GitHub HTTPS pattern.
    """
    url = url.strip()
    if not _GITHUB_URL_RE.match(url):
        raise InvalidGitHubURLError(
            f"Not a valid public GitHub HTTPS URL: {url!r}\n"
            "Expected format: https://github.com/<owner>/<repo>"
        )
    # Normalise: drop trailing slash and .git suffix so the URL is canonical.
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url


@contextmanager
def cloned_repo(url: str) -> Generator[str, None, None]:
    """Context manager: clone *url* into a temp dir and yield the local path.

    The temporary directory is deleted on exit regardless of whether the body
    of the ``with`` block raises.

    Parameters
    ----------
    url:
        A public GitHub HTTPS URL (validated before cloning).

    Yields
    ------
    str
        Absolute path to the cloned repository root.

    Raises
    ------
    InvalidGitHubURLError
        If *url* fails validation.
    CloneError
        If ``git clone`` fails (non-zero exit code or timeout).
    """
    canonical_url = validate_github_url(url)
    tmp_dir = tempfile.mkdtemp(prefix="gitdna_clone_")
    try:
        result = subprocess.run(  # noqa: S603 — no user code executed
            ["git", "clone", "--depth", "1", canonical_url, tmp_dir],
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT,
        )
        if result.returncode != 0:
            raise CloneError(
                f"git clone failed (exit {result.returncode}):\n{result.stderr.strip()}"
            )
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
