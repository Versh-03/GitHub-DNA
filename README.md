# GitHub DNA

> Visualize a Python codebase as an interactive dependency graph — instantly understand structure, hotspots, and contributor history.

---

## The Problem

Joining a new codebase is slow. Developers can spend significant time reading files and tracing relationships manually, how things connect; which modules depend on which, which files change the most, which files are connected, and which contributors have worked on the repository.. There is no easy "map" of the code.

---

## What Git DNA Does

Git DNA takes a local Python repository path, runs a four-stage analysis pipeline (file walk → AST dependency parse → Git history extract → graph build), and returns an interactive web-based architecture map. Each node is a file; each edge is an import relationship. Node colour encodes file type, and each node shows the file's commit frequency at a glance.

---

## Key Features

| Feature | Detail |
|---|---|
| **File classification** | Detects source, test, docs, and config files automatically |
| **Dependency graph** | Parses Python `import` / `from … import` statements via the standard-library `ast` module — no external parser needed |
| **Git history overlay** | Counts commits per file and unique contributors using GitPython |
| **Repository metrics** | Totals, top-connected files, top-changed files, largest files, edge count |
| **Interactive visualisation** | React Flow graph with pan, zoom, minimap, and fit-to-view; click any node for a details panel |
| **Smart layout** | Connected components use Dagre hierarchical layout; isolated nodes fall back to a compact grid |
| **Response caching** | Results saved to `cache/` as JSON (keyed by SHA-256 of the repo path) |
| **Local-first** | No cloud, no authentication, no database — runs fully offline |

---

## How It Works

```
User inputs repo path
        │
        ▼
┌──────────────────┐
│  Repository Walk │  repository.py — scan files, classify type, collect size
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Dependency Parse │  dependency.py — Python AST → intra-repo import edges
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Git History     │  git_history.py — GitPython → commit count per file
└────────┬─────────┘
         │
         ▼
┌──────────────────────────┐
│  Graph + Metrics Build   │  graph.py (NetworkX) + metrics.py → JSON
└────────┬─────────────────┘
         │
         ▼
  POST /analyze → React frontend renders graph + stats panel
```

The API returns a single JSON object containing:
- **`graph.nodes`** — file path, type, size, commit count
- **`graph.edges`** — source → target import relationships
- **`metrics`** — aggregated repository statistics

---

## Architecture

```
GitHub-DNA/
├── backend/
│   ├── api/
│   │   └── main.py              # FastAPI app, POST /analyze endpoint
│   ├── analyzers/
│   │   ├── repository.py        # File walker + classifier
│   │   ├── dependency.py        # AST-based import graph builder
│   │   ├── git_history.py       # Git commit history per file
│   │   └── metrics.py           # Metrics aggregator
│   └── models/
│       └── graph.py             # NetworkX directed graph + JSON export
├── frontend/
│   └── src/
│       ├── App.jsx              # Root component + fetch logic
│       └── components/
│           ├── GraphView.jsx    # React Flow renderer + Dagre layout
│           ├── StatsPanel.jsx   # Left sidebar metrics
│           └── FileDetailPanel.jsx  # Node detail popup
├── tests/                       # pytest suite
├── docs/                        # Architecture spec and phase plan
├── cache/                       # Runtime JSON cache (auto-created)
└── requirements.txt
```

---

## Tech Stack

**Backend**
- Python 3.11+
- [FastAPI](https://fastapi.tiangolo.com/) — REST API framework
- [uvicorn](https://www.uvicorn.org/) — ASGI server
- [GitPython](https://gitpython.readthedocs.io/) — git history extraction
- [NetworkX](https://networkx.org/) — directed graph model
- `ast` (standard library) — Python import parsing

**Frontend**
- React 18
- [Vite](https://vitejs.dev/) — build tool / dev server
- [@xyflow/react](https://reactflow.dev/) (React Flow v12) — interactive graph
- [dagre](https://github.com/dagrejs/dagre) — hierarchical graph layout
- Vanilla CSS (dark GitHub-inspired theme)

---

## Running the Backend

```bash
# 1. Clone the repo
git clone https://github.com/Versh-03/GitHub-DNA.git
cd GitHub-DNA

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start the backend
uvicorn backend.api.main:app --reload
# API available at http://localhost:8000
```

**Run tests:**
```bash
pytest tests/
```

---

## Running the Frontend

```bash
cd frontend
npm install
npm run dev
# UI available at http://localhost:5173
```

---

## Example Usage

Open `http://localhost:5173`, enter an absolute path to any local Python repository, and click **Analyse**.

The API call looks like:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/absolute/path/to/my-python-project"}'
```

Example response (abbreviated):

```json
{
  "graph": {
    "nodes": [
      {"id": "backend/api/main.py", "type": "source", "language": "python", "size_bytes": 2104, "commit_count": 7}
    ],
    "edges": [
      {"source": "backend/api/main.py", "target": "backend/analyzers/repository.py", "type": "import"}
    ]
  },
  "metrics": {
    "total_files": 14,
    "source_files": 8,
    "test_files": 4,
    "total_commits": 42,
    "contributors_count": 1,
    "total_edges": 11
  }
}
```

---

**Limitations (current scope):**
- Only analyses Python repositories (JavaScript / other languages not yet supported)
- Requires a locally accessible repository path — no remote URL support
- No authentication or multi-user support
