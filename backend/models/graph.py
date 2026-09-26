"""
graph.py — NetworkX graph builder and JSON exporter for Git DNA.
"""

from __future__ import annotations

import networkx as nx


def build_graph(files: list[dict], edges: list[dict]) -> nx.DiGraph:
    """Build a directed graph from the file list and dependency edges.

    Each file becomes a node with attributes:
      - ``type``       — file_type from the repository walker ("source", "test", …)
      - ``language``   — "python" for .py files, otherwise "unknown"
      - ``size_bytes`` — file size in bytes

    Each dependency edge becomes a directed edge in the graph.
    """
    graph: nx.DiGraph = nx.DiGraph()

    for f in files:
        path = f["path"]
        language = "python" if path.endswith(".py") else "unknown"
        graph.add_node(
            path,
            type=f.get("file_type", "other"),
            language=language,
            size_bytes=f.get("size_bytes", 0),
        )

    for edge in edges:
        graph.add_edge(edge["source"], edge["target"], type=edge.get("type", "import"))

    return graph


def graph_to_json(graph: nx.DiGraph, git_data: dict) -> dict:
    """Export *graph* to a JSON-serialisable dict ready for React Flow.

    Returns::

        {
            "nodes": [
                {
                    "id": "backend/api/main.py",
                    "type": "source",
                    "language": "python",
                    "size_bytes": 1234,
                    "commit_count": 7
                },
                ...
            ],
            "edges": [
                {
                    "source": "backend/api/main.py",
                    "target": "backend/analyzers/repository.py",
                    "type": "import"
                },
                ...
            ]
        }

    ``commit_count`` for each node is looked up from
    ``git_data["file_commit_counts"]``; defaults to 0 if the file has no
    git history.
    """
    file_commit_counts: dict[str, int] = git_data.get("file_commit_counts", {})

    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        nodes.append(
            {
                "id": node_id,
                "type": attrs.get("type", "other"),
                "language": attrs.get("language", "unknown"),
                "size_bytes": attrs.get("size_bytes", 0),
                "commit_count": file_commit_counts.get(node_id, 0),
            }
        )

    edges = []
    for src, tgt, attrs in graph.edges(data=True):
        edges.append(
            {
                "source": src,
                "target": tgt,
                "type": attrs.get("type", "import"),
            }
        )

    return {"nodes": nodes, "edges": edges}
