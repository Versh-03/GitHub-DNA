"""
metrics.py — Repository-level metrics aggregator for Git DNA.
"""

from __future__ import annotations

import networkx as nx


def compute_metrics(
    files: list[dict],
    edges: list[dict],
    git_history: dict,
    graph: nx.DiGraph,
) -> dict:
    """Aggregate all pipeline outputs into a single metrics dict.

    Parameters
    ----------
    files:
        Output of ``walk_repository`` — list of file dicts with
        ``path``, ``size_bytes``, ``file_type``.
    edges:
        Output of ``build_dependency_edges`` — list of edge dicts.
    git_history:
        Output of ``analyze_git_history``.
    graph:
        NetworkX DiGraph built by ``build_graph``.

    Returns
    -------
    dict with keys:
        total_files, source_files, test_files, doc_files, directories,
        total_commits, contributor_count,
        top_changed_files, top_connected_files, largest_files,
        recently_modified_files, total_edges
    """
    # --- file counts ---
    total_files = len(files)
    source_files = sum(1 for f in files if f.get("file_type") == "source")
    test_files   = sum(1 for f in files if f.get("file_type") == "test")
    doc_files    = sum(1 for f in files if f.get("file_type") == "docs")

    # Unique parent directories (excluding the repo root itself)
    directories: set[str] = set()
    for f in files:
        parts = f["path"].split("/")
        for i in range(1, len(parts)):
            directories.add("/".join(parts[:i]))

    # --- git stats ---
    total_commits    = git_history.get("total_commits", 0)
    contributor_count = git_history.get("contributor_count", 0)
    top_changed_files = git_history.get("top_changed_files", [])

    # --- graph-derived: top connected files (in-degree + out-degree) ---
    top_connected_files: list[dict] = []
    if graph.number_of_nodes() > 0:
        degree_map = {
            node: graph.in_degree(node) + graph.out_degree(node)
            for node in graph.nodes()
        }
        top_connected_files = sorted(
            [{"path": p, "connections": d} for p, d in degree_map.items() if d > 0],
            key=lambda x: x["connections"],
            reverse=True,
        )[:10]

    # --- largest files ---
    largest_files = sorted(
        [{"path": f["path"], "size_bytes": f["size_bytes"]} for f in files],
        key=lambda x: x["size_bytes"],
        reverse=True,
    )[:10]

    # --- recently modified files ---
    # last_modified is not collected by walk_repository; return empty list
    # rather than inventing data.
    recently_modified_files: list[dict] = []
    files_with_modified = [f for f in files if f.get("last_modified")]
    if files_with_modified:
        recently_modified_files = sorted(
            files_with_modified,
            key=lambda x: x["last_modified"],
            reverse=True,
        )[:10]

    return {
        "total_files": total_files,
        "source_files": source_files,
        "test_files": test_files,
        "doc_files": doc_files,
        "directories": len(directories),
        "total_commits": total_commits,
        "contributor_count": contributor_count,
        "top_changed_files": top_changed_files,
        "top_connected_files": top_connected_files,
        "largest_files": largest_files,
        "recently_modified_files": recently_modified_files,
        "total_edges": len(edges),
    }
