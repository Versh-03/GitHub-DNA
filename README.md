# 🧬 GitHub-DNA

> Google Maps for understanding a codebase.

---

## The Problem

Understanding an unfamiliar codebase can take significant time. Developers
often need to manually explore directories, inspect source files, trace
dependencies, review Git history, and determine which parts of the repository
are most connected or frequently changed.

There is no simple visual "map" that provides this context at a glance.

---

## What GitHub-DNA Does

GitHub-DNA analyzes a Python Git repository and turns it into an interactive
visual map of its structure, dependencies, and development history.

A repository can be provided either as a local filesystem path or as a
public GitHub repository URL. GitHub-DNA analyzes the repository and presents
its files, relationships, repository metrics, and Git history through an
interactive web interface.

---

## Key Features

| Feature | Detail |
|---|---|
| **File classification** | Detects source, test, docs, and config files automatically |
| **Dependency graph** | Parses Python `import` / `from … import` statements via the standard-library `ast` module |
| **Git history overlay** | Counts commits per file and unique contributors using GitPython |
| **Repository metrics** | Totals, top-connected files, top-changed files, largest files, edge count, and contributor information |
| **Interactive visualisation** | React Flow graph with pan, zoom, minimap, and fit-to-view; click any node for a details panel |
| **Smart layout** | Connected components use Dagre hierarchical layout; isolated nodes fall back to a compact grid |
| **Local + GitHub input** | Analyze a local repository path or a public GitHub repository URL |
| **Local-first architecture** | No authentication, database, or cloud infrastructure is required for local analysis |

---

## How It Works

```text
User provides local path or GitHub URL
        │
        ├── Local path ───────────────┐
        │                             │
        └── GitHub URL → Clone repo ──┤
                                      ▼
                           ┌──────────────────┐
                           │ Repository Walk  │
                           │ Scan + classify  │
                           └────────┬─────────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │ Dependency Parse │
                           │ Python AST        │
                           └────────┬─────────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │   Git History    │
                           │ GitPython        │
                           └────────┬─────────┘
                                    │
                                    ▼
                           ┌──────────────────────┐
                           │ Graph + Metrics Build│
                           │ NetworkX             │
                           └──────────┬───────────┘
                                      │
                                      ▼
                              React visualization
```

The API returns a single JSON object containing:

* **`graph.nodes`** — file path, type, size, commit count
* **`graph.edges`** — source → target import relationships
* **`metrics`** — aggregated repository statistics

---

## Architecture

```text
GitHub-DNA/
├── backend/
│   ├── api/
│   │   └── main.py              # FastAPI app and API endpoints
│   ├── analyzers/
│   │   ├── repository.py        # File walker + classifier
│   │   ├── dependency.py        # AST-based import graph builder
│   │   ├── git_history.py       # Git commit history analysis
│   │   └── metrics.py           # Metrics aggregator
│   ├── models/
│   │   └── graph.py             # NetworkX graph + JSON export
│   └── github_loader.py         # GitHub URL → temporary local clone
├── frontend/
│   └── src/
│       ├── App.jsx              # Root component + API interaction
│       └── components/
│           ├── GraphView.jsx    # React Flow renderer + Dagre layout
│           ├── StatsPanel.jsx   # Repository metrics
│           └── FileDetailPanel.jsx
├── tests/                       # pytest test suite
├── docs/                        # Architecture and development documentation
├── cache/                       # Runtime JSON cache
└── requirements.txt
```

---

## Tech Stack

### Backend

* **Python 3.11+**
* **FastAPI** — REST API framework
* **uvicorn** — ASGI server
* **GitPython** — Git history extraction
* **NetworkX** — directed graph model
* **`ast`** — Python import parsing using the standard library

### Frontend

* **React 18**
* **Vite** — build tool and development server
* **@xyflow/react** — interactive graph visualization
* **dagre** — hierarchical graph layout
* **Vanilla CSS** — dark GitHub-inspired interface

---

## Running the Backend

### 1. Clone the repository

```bash
git clone https://github.com/Versh-03/GitHub-DNA.git
cd GitHub-DNA
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the backend

```bash
uvicorn backend.api.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

### Run tests

```bash
pytest tests/
```

---

## Running the Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at:

```text
http://localhost:5173
```

---

## Example Usage

### Analyze a local repository

Open the application, enter an absolute path to a local Python Git
repository, and click **Analyse**.

The API call looks like:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/absolute/path/to/my-python-project"}'
```

### Analyze a public GitHub repository

The deployed version can also analyze a public GitHub repository directly.

For example:

```text
https://github.com/pallets/flask
```

GitHub-DNA temporarily clones the repository, runs the same analysis
pipeline, and removes the temporary clone afterward.

The API endpoint is:

```text
POST /analyze-github
```

with:

```json
{
  "github_url": "https://github.com/pallets/flask"
}
```

### Example response

```json
{
  "graph": {
    "nodes": [
      {
        "id": "backend/api/main.py",
        "type": "source",
        "language": "python",
        "size_bytes": 2104,
        "commit_count": 7
      }
    ],
    "edges": [
      {
        "source": "backend/api/main.py",
        "target": "backend/analyzers/repository.py",
        "type": "import"
      }
    ]
  },
  "metrics": {
    "total_files": 14,
    "source_files": 8,
    "test_files": 4,
    "total_commits": 42,
    "contributor_count": 1,
    "total_edges": 11
  }
}
```

---

## Deployed Version

* **Frontend:** [https://github-dna-three.vercel.app/](https://github-dna-three.vercel.app/)
* **Backend API:** [https://github-dna.onrender.com/](https://github-dna.onrender.com/)
* **API documentation:** [https://github-dna.onrender.com/docs](https://github-dna.onrender.com/docs)

---

## Limitations

* Only Python repositories are currently supported.
* GitHub URL analysis supports public repositories only.
* No authentication or multi-user support.
* GitHub URL analysis depends on the repository being publicly accessible.
