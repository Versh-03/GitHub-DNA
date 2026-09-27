"""
git_history.py — GitPython-based git log analyzer.
"""

from __future__ import annotations

import git


_EMPTY_RESULT = {
    "total_commits": 0,
    "contributor_count": 0,
    "file_commit_counts": {},
    "top_changed_files": [],
}


def analyze_git_history(repo_path: str) -> dict:
    """Analyze the git history of the repository at *repo_path*.

    Returns::

        {
            "total_commits": 42,
            "contributor_count": 5,
            "file_commit_counts": {"path/to/file.py": 12, ...},
            "top_changed_files": [{"path": "...", "commit_count": 12}, ...]
        }

    ``top_changed_files`` is the top 10 files sorted by ``commit_count``
    descending.

    Implementation note: this uses a single bulk ``git log --name-only``
    call rather than iterating commits with GitPython's ``commit.stats``,
    which internally spawns one subprocess per commit and is prohibitively
    slow on repositories with large histories (thousands of commits).

    On error (not a git repo, no commits, etc.) returns the empty structure
    above with an added ``"error"`` key describing the problem.
    """
    try:
        repo = git.Repo(repo_path)
    except git.InvalidGitRepositoryError:
        return {**_EMPTY_RESULT, "error": f"Not a git repository: {repo_path}"}
    except git.NoSuchPathError:
        return {**_EMPTY_RESULT, "error": f"Path does not exist: {repo_path}"}

    contributors: set[str] = set()
    file_commit_counts: dict[str, int] = {}
    total_commits = 0

    try:
        # Single bulk call: one line per commit (author email), then the
        # names of the files that commit touched. This avoids GitPython's
        # per-commit .stats subprocess overhead entirely.
        log_output = repo.git.log(
            "--name-only",
            "--pretty=format:__COMMIT__%ae",
        )
    except git.GitCommandError as exc:
        return {**_EMPTY_RESULT, "error": f"Unable to read git history: {exc}"}

    for line in log_output.splitlines():
        if line.startswith("__COMMIT__"):
            total_commits += 1
            author = line[len("__COMMIT__"):].strip()
            if author:
                contributors.add(author)
        elif line.strip():
            file_commit_counts[line] = file_commit_counts.get(line, 0) + 1

    top_changed_files = sorted(
        [{"path": p, "commit_count": c} for p, c in file_commit_counts.items()],
        key=lambda x: x["commit_count"],
        reverse=True,
    )[:10]

    return {
        "total_commits": total_commits,
        "contributor_count": len(contributors),
        "file_commit_counts": file_commit_counts,
        "top_changed_files": top_changed_files,
    }
