"""
test_graph_metrics.py — unit tests for backend.models.graph and
backend.analyzers.metrics.
"""

from __future__ import annotations

import networkx as nx
import pytest

from backend.analyzers.metrics import compute_metrics
from backend.models.graph import build_graph, graph_to_json


# ---------------------------------------------------------------------------
# Shared stub data
# ---------------------------------------------------------------------------

STUB_FILES = [
    {"path": "app.py",        "file_type": "source", "size_bytes": 500},
    {"path": "utils.py",      "file_type": "source", "size_bytes": 200},
    {"path": "test_app.py",   "file_type": "test",   "size_bytes": 100},
    {"path": "README.md",     "file_type": "docs",   "size_bytes":  80},
    {"path": "setup.cfg",     "file_type": "config", "size_bytes":  40},
    {"path": "Makefile",      "file_type": "other",  "size_bytes":  20},
]

STUB_EDGES = [
    {"source": "app.py", "target": "utils.py", "type": "import"},
]

STUB_GIT_HISTORY = {
    "total_commits": 10,
    "contributor_count": 3,
    "file_commit_counts": {"app.py": 8, "utils.py": 4},
    "top_changed_files": [
        {"path": "app.py",   "commit_count": 8},
        {"path": "utils.py", "commit_count": 4},
    ],
}

STUB_GRAPH = build_graph(STUB_FILES, STUB_EDGES)


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:

    def test_node_count(self):
        """One node per file."""
        g = build_graph(STUB_FILES, STUB_EDGES)
        assert g.number_of_nodes() == len(STUB_FILES)

    def test_edge_count(self):
        """One edge per dependency edge."""
        g = build_graph(STUB_FILES, STUB_EDGES)
        assert g.number_of_edges() == len(STUB_EDGES)

    def test_node_type_attribute(self):
        g = build_graph(STUB_FILES, STUB_EDGES)
        assert g.nodes["app.py"]["type"] == "source"
        assert g.nodes["test_app.py"]["type"] == "test"

    def test_node_language_python(self):
        g = build_graph(STUB_FILES, STUB_EDGES)
        assert g.nodes["app.py"]["language"] == "python"

    def test_node_language_unknown_for_non_py(self):
        g = build_graph(STUB_FILES, STUB_EDGES)
        assert g.nodes["README.md"]["language"] == "unknown"

    def test_node_size_bytes(self):
        g = build_graph(STUB_FILES, STUB_EDGES)
        assert g.nodes["app.py"]["size_bytes"] == 500

    def test_edge_direction(self):
        """Edge goes from source to target."""
        g = build_graph(STUB_FILES, STUB_EDGES)
        assert g.has_edge("app.py", "utils.py")
        assert not g.has_edge("utils.py", "app.py")

    def test_empty_inputs(self):
        g = build_graph([], [])
        assert g.number_of_nodes() == 0
        assert g.number_of_edges() == 0


# ---------------------------------------------------------------------------
# graph_to_json
# ---------------------------------------------------------------------------

class TestGraphToJson:

    def test_has_nodes_and_edges_keys(self):
        result = graph_to_json(STUB_GRAPH, STUB_GIT_HISTORY)
        assert "nodes" in result
        assert "edges" in result

    def test_node_count_matches_graph(self):
        result = graph_to_json(STUB_GRAPH, STUB_GIT_HISTORY)
        assert len(result["nodes"]) == STUB_GRAPH.number_of_nodes()

    def test_edge_count_matches_graph(self):
        result = graph_to_json(STUB_GRAPH, STUB_GIT_HISTORY)
        assert len(result["edges"]) == STUB_GRAPH.number_of_edges()

    def test_node_has_required_keys(self):
        result = graph_to_json(STUB_GRAPH, STUB_GIT_HISTORY)
        for node in result["nodes"]:
            for key in ("id", "type", "language", "size_bytes", "commit_count"):
                assert key in node, f"Node missing key '{key}': {node}"

    def test_commit_count_populated_from_git_data(self):
        result = graph_to_json(STUB_GRAPH, STUB_GIT_HISTORY)
        node_map = {n["id"]: n for n in result["nodes"]}
        assert node_map["app.py"]["commit_count"] == 8
        assert node_map["utils.py"]["commit_count"] == 4

    def test_commit_count_zero_when_no_history(self):
        result = graph_to_json(STUB_GRAPH, STUB_GIT_HISTORY)
        node_map = {n["id"]: n for n in result["nodes"]}
        # README.md has no git history in the stub
        assert node_map["README.md"]["commit_count"] == 0

    def test_edge_has_source_target_type(self):
        result = graph_to_json(STUB_GRAPH, STUB_GIT_HISTORY)
        for edge in result["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "type" in edge

    def test_empty_graph_produces_empty_lists(self):
        empty = nx.DiGraph()
        result = graph_to_json(empty, {})
        assert result == {"nodes": [], "edges": []}


# ---------------------------------------------------------------------------
# compute_metrics
# ---------------------------------------------------------------------------

class TestComputeMetrics:

    @pytest.fixture()
    def metrics(self) -> dict:
        return compute_metrics(STUB_FILES, STUB_EDGES, STUB_GIT_HISTORY, STUB_GRAPH)

    def test_all_keys_present(self, metrics):
        expected_keys = {
            "total_files", "source_files", "test_files", "doc_files",
            "directories", "total_commits", "contributor_count",
            "top_changed_files", "top_connected_files", "largest_files",
            "recently_modified_files", "total_edges",
        }
        assert expected_keys <= metrics.keys(), (
            f"Missing keys: {expected_keys - metrics.keys()}"
        )

    def test_total_files(self, metrics):
        assert metrics["total_files"] == 6

    def test_source_files(self, metrics):
        assert metrics["source_files"] == 2

    def test_test_files(self, metrics):
        assert metrics["test_files"] == 1

    def test_doc_files(self, metrics):
        assert metrics["doc_files"] == 1

    def test_directories_count(self, metrics):
        # All stub files are at root level → no subdirectories
        assert metrics["directories"] == 0

    def test_directories_with_nested_files(self):
        nested_files = [
            {"path": "src/app.py",      "file_type": "source", "size_bytes": 100},
            {"path": "src/utils.py",    "file_type": "source", "size_bytes": 100},
            {"path": "tests/test_a.py", "file_type": "test",   "size_bytes":  50},
        ]
        g = build_graph(nested_files, [])
        m = compute_metrics(nested_files, [], {}, g)
        assert m["directories"] == 2   # "src" and "tests"

    def test_total_commits_from_git_history(self, metrics):
        assert metrics["total_commits"] == 10

    def test_contributor_count_from_git_history(self, metrics):
        assert metrics["contributor_count"] == 3

    def test_top_changed_files_passthrough(self, metrics):
        assert metrics["top_changed_files"] == STUB_GIT_HISTORY["top_changed_files"]

    def test_total_edges(self, metrics):
        assert metrics["total_edges"] == 1

    def test_top_connected_files_sorted_descending(self, metrics):
        top = metrics["top_connected_files"]
        if len(top) >= 2:
            assert top[0]["connections"] >= top[1]["connections"]

    def test_top_connected_files_app_most_connected(self, metrics):
        """app.py has 1 out-edge; utils.py has 1 in-edge — both have degree 1."""
        top = metrics["top_connected_files"]
        paths = [e["path"] for e in top]
        assert "app.py" in paths
        assert "utils.py" in paths

    def test_largest_files_sorted_descending(self, metrics):
        top = metrics["largest_files"]
        sizes = [e["size_bytes"] for e in top]
        assert sizes == sorted(sizes, reverse=True)

    def test_largest_files_capped_at_10(self):
        """Even with 20 files, largest_files has at most 10 entries."""
        many = [
            {"path": f"f{i}.py", "file_type": "source", "size_bytes": i * 10}
            for i in range(20)
        ]
        g = build_graph(many, [])
        m = compute_metrics(many, [], {}, g)
        assert len(m["largest_files"]) <= 10

    def test_recently_modified_files_empty_when_no_last_modified(self, metrics):
        """recently_modified_files must be [] when no file has last_modified."""
        assert metrics["recently_modified_files"] == []

    def test_recently_modified_files_populated_when_data_present(self):
        """recently_modified_files is sorted desc when last_modified is present."""
        files_with_dates = [
            {"path": "a.py", "file_type": "source", "size_bytes": 10, "last_modified": "2024-01-03"},
            {"path": "b.py", "file_type": "source", "size_bytes": 10, "last_modified": "2024-01-01"},
            {"path": "c.py", "file_type": "source", "size_bytes": 10, "last_modified": "2024-01-02"},
        ]
        g = build_graph(files_with_dates, [])
        m = compute_metrics(files_with_dates, [], {}, g)
        dates = [f["last_modified"] for f in m["recently_modified_files"]]
        assert dates == sorted(dates, reverse=True)

    def test_empty_inputs_produce_zero_metrics(self):
        g = build_graph([], [])
        m = compute_metrics([], [], {}, g)
        assert m["total_files"] == 0
        assert m["total_edges"] == 0
        assert m["top_connected_files"] == []
        assert m["largest_files"] == []
        assert m["recently_modified_files"] == []
