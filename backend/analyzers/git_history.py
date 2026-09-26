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

    On error (not a git repo, no commits, etc.) returns the empty structure
    above with an added ``"error"`` key describing the problem.
    """
    try:
        repo = git.Repo(repo_path)
    except git.InvalidGitRepositoryError:
        return {**_EMPTY_RESULT, "error": f"Not a git repository: {repo_path}"}
    except git.NoSuchPathError:
        return {**_EMPTY_RESULT, "error": f"Path does not exist: {repo_path}"}

    total_commits = 0
    contributors: set[str] = set()
    file_commit_counts: dict[str, int] = {}

    try:
        for commit in repo.iter_commits():
            total_commits += 1
            contributors.add(commit.author.email)
            for file_path in commit.stats.files:
                file_commit_counts[file_path] = (
                    file_commit_counts.get(file_path, 0) + 1
                )
    except git.GitCommandError as exc:
        # Repo exists but has no commits yet (empty repo) or other git error
        return {**_EMPTY_RESULT, "error": str(exc)}

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
