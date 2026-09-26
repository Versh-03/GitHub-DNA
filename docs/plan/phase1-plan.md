# Git DNA — Detailed Implementation Plan

> **Source of truth:** [`docs/architecture.md`](../architecture.md)
> **Do not implement anything until the plan is approved.**
> Each milestone is designed to be small, independently reviewable, and
> understandable by a solo student developer.

---

## Top-Level Overview

Git DNA is a "Google Maps for codebases" tool. A developer points it at a
local Python repository and gets back:

- a file/module dependency graph
- Git history statistics
- aggregated repository metrics
- a web UI to explore it all interactively

The work is broken into **8 milestones**. The first 5 milestones together
form the Python-only MVP (fully working end-to-end). Milestones 6–8 cover
refinement, measurement, and submission.

**Technology decisions (from spec):**
- Backend: Python 3.11+, FastAPI, uvicorn, GitPython, networkx, pytest
- Frontend: React + Vite, React Flow
- No database — results cached as JSON on disk

---

## Milestone 1 — Project Scaffold + Repository File Walker

### Objective
Stand up the project skeleton and implement the first analyzer: walking a
local git repo and classifying every file into a category (source, test,
docs, config, other).

### Status
`[ ] pending`

### Files / Components Involved
```
backend/
  analyzers/
    repository.py      ← NEW: file walk + classification logic
  api/
    main.py            ← NEW: FastAPI app shell, /analyze stub endpoint
tests/
  test_repository.py   ← NEW: unit tests for repository.py
requirements.txt       ← NEW: backend Python dependencies
```

### Dependencies
- Python 3.11+ (standard library only for this milestone: `pathlib`, `os`)
- FastAPI + uvicorn (installed via requirements.txt)
- pytest (dev dependency)

### Implementation Steps
1. Create `requirements.txt` listing: `fastapi`, `uvicorn`, `gitpython`,
   `networkx`, `pytest`.
2. Create `backend/analyzers/repository.py`:
   - Function `walk_repository(repo_path: str) -> list[dict]` that uses
     `pathlib.Path.rglob("*")` to iterate every file.
   - For each file, record: relative path, size in bytes, and a `file_type`
     classification based on simple rules:
     - path contains `/test` or filename starts with `test_` → `"test"`
     - extension is `.py` → `"source"`
     - extension in `{.md, .rst, .txt}` → `"docs"`
     - extension in `{.json, .yaml, .yml, .toml, .cfg, .ini}` → `"config"`
     - anything else → `"other"`
   - Skip `.git/` directory entries.
3. Create `backend/api/main.py`:
   - Minimal FastAPI app.
   - Single `POST /analyze` endpoint that accepts `{"repo_path": "..."}` in
     the request body and returns the raw list of file dicts from
     `walk_repository`.
4. Create `tests/test_repository.py`:
   - Create a small temporary directory tree in the test using `tmp_path`
     (pytest fixture).
   - Assert correct `file_type` classification for `.py`, test files, `.md`,
     `.yaml`, and unknown extensions.
   - Assert `.git/` entries are excluded.

### Expected Output
- `uvicorn backend.api.main:app --reload` starts without error.
- `POST /analyze` with a valid `repo_path` returns a JSON array of file
  objects, each with `path`, `size_bytes`, and `file_type`.
- `pytest tests/test_repository.py` passes.

### Testing Approach
Pure unit tests with a synthetic temp directory — no real git repo needed
at this stage. Tests cover: classification rules, `.git` exclusion, and
correct relative paths.

---

## Milestone 2 — Dependency Analyzer (AST-based Import Graph)

### Objective
Parse every Python source file's `import` and `from ... import ...`
statements using the standard-library `ast` module and produce a list of
directed edges representing which file depends on which module.

### Status
`[ ] pending`

### Files / Components Involved
```
backend/
  analyzers/
    dependency.py      ← NEW: ast import parsing + edge building
tests/
  test_dependency.py   ← NEW: unit tests for dependency.py
```

### Dependencies
- Milestone 1 complete (uses file list from `walk_repository`)
- Python standard library only: `ast`, `pathlib`

### Implementation Steps
1. Create `backend/analyzers/dependency.py`:
   - Function `extract_imports(file_path: str) -> list[str]` that:
     - Reads the file, parses it with `ast.parse()`.
     - Walks the AST to collect `ast.Import` and `ast.ImportFrom` nodes.
     - Returns the list of top-level module names imported.
     - Handles `SyntaxError` gracefully (returns empty list with a warning).
   - Function `build_dependency_edges(file_list: list[dict]) -> list[dict]`
     that iterates only `file_type == "source"` files, calls
     `extract_imports` for each, and for every imported name checks whether
     a matching file exists in `file_list` (by converting module path
     `a.b.c` → `a/b/c.py`).
     - If a match is found → emit an edge:
       `{"source": <file_path>, "target": <matched_file_path>, "type": "import"}`
     - If no match (external library) → skip silently.
2. Update `backend/api/main.py`:
   - Import and call `build_dependency_edges` inside `/analyze`.
   - Add `"edges"` key to the response alongside the file list.

### Expected Output
- `/analyze` response now includes `"edges": [...]` in addition to
  `"files": [...]`.
- Edges list contains only intra-repo imports (external libraries like
  `os`, `fastapi` are not included).
- `pytest tests/test_dependency.py` passes.

### Testing Approach
Write two or three small synthetic `.py` files as strings, parse them with
`extract_imports`, and assert the returned module names are correct.
Test `build_dependency_edges` with a tiny hand-crafted `file_list` to
confirm edge creation and missing-match suppression.

---

## Milestone 3 — Git History Analyzer

### Objective
Use GitPython to read the repository's git log and extract commit counts
per file, total commit count, unique contributors, and the top most-changed
files.

### Status
`[ ] pending`

### Files / Components Involved
```
backend/
  analyzers/
    git_history.py     ← NEW: GitPython-based log analysis
tests/
  test_git_history.py  ← NEW: unit tests for git_history.py
```

### Dependencies
- Milestone 1 complete
- `gitpython` (already in requirements.txt)
- A real git repository at test time (use `sample-repository/` or a small
  fixture repo initialized with `git.Repo.init()` in the test)

### Implementation Steps
1. Create `backend/analyzers/git_history.py`:
   - Function `analyze_git_history(repo_path: str) -> dict` that:
     - Opens the repo with `git.Repo(repo_path)`.
     - Iterates `repo.iter_commits()` to collect:
       - `total_commits`: count of all commits.
       - `contributors`: set of unique author email addresses → final count.
       - `file_commit_counts`: `dict[str, int]` mapping each file path to
         how many commits touched it (via `commit.stats.files`).
     - Returns a dict:
       ```json
       {
         "total_commits": 42,
         "contributor_count": 5,
         "file_commit_counts": {"path/to/file.py": 12, ...},
         "top_changed_files": [{"path": "...", "commit_count": 12}, ...]
       }
       ```
     - `top_changed_files` is the top 10 entries sorted by `commit_count`
       descending.
   - Handle `git.InvalidGitRepositoryError` gracefully — return empty
     structure with an `"error"` key.
2. Update `backend/api/main.py`:
   - Call `analyze_git_history` inside `/analyze`.
   - Add `"git_history"` key to the response.

### Expected Output
- `/analyze` response includes `"git_history"` with commit stats.
- `pytest tests/test_git_history.py` passes.

### Testing Approach
Initialize a temporary git repo using `git.Repo.init()` in the pytest
`tmp_path` fixture, make a few commits touching different files, then
assert `total_commits`, `contributor_count`, and `file_commit_counts` are
correct. Test the error path with a non-git directory.

---

## Milestone 4 — Graph Model + Repository Metrics Aggregator

### Objective
Combine the outputs of Milestones 1–3 into a networkx graph and compute the
final set of repository-level metrics. Export the graph as a JSON structure
the frontend can consume directly.

### Status
`[ ] pending`

### Files / Components Involved
```
backend/
  models/
    graph.py           ← NEW: networkx graph builder + JSON export
  analyzers/
    metrics.py         ← NEW: aggregator function
  api/
    main.py            ← MODIFIED: wire everything together, add JSON cache
```

### Dependencies
- Milestones 1, 2, 3 complete
- `networkx` (already in requirements.txt)

### Implementation Steps
1. Create `backend/models/graph.py`:
   - Function `build_graph(files: list[dict], edges: list[dict]) -> nx.DiGraph`:
     - Add one node per file with attributes: `type`, `language`, `size_bytes`.
     - Add one directed edge per dependency edge dict.
   - Function `graph_to_json(graph: nx.DiGraph, git_data: dict) -> dict`:
     - Returns `{"nodes": [...], "edges": [...]}` where each node includes
       its attributes plus `commit_count` looked up from `git_data["file_commit_counts"]`.
     - This is the shape React Flow will consume.
2. Create `backend/analyzers/metrics.py`:
   - Function `compute_metrics(files, edges, git_history, graph) -> dict`
     that returns the full metrics dict (see Section 9 of the spec):
       - `total_files`, `source_files`, `test_files`, `doc_files`, `directories`
       - `total_commits`, `contributor_count`
       - `top_changed_files` (from git_history)
       - `top_connected_files` (highest in+out degree from networkx graph)
       - `largest_files` (top 10 by `size_bytes`)
       - `recently_modified_files` (top 10 by `last_modified`, if available)
       - `total_edges`
3. Update `backend/api/main.py`:
   - Assemble the full pipeline: walk → deps → git → graph → metrics.
   - Cache result as `{repo_path_hash}.json` in a local `cache/` directory.
   - Return a single unified response:
     ```json
     {
       "graph": { "nodes": [...], "edges": [...] },
       "metrics": { ... }
     }
     ```

### Expected Output
- `/analyze` returns a single, complete JSON response with `graph` and
  `metrics` keys.
- JSON cache file is written to `cache/` after analysis.
- `pytest` passes (add a small integration test calling `compute_metrics`
  with mock data).

### Testing Approach
Unit-test `compute_metrics` with hard-coded stub data (no real files or
git repo needed). Assert each metric key is present and has the correct
type/value. Test `graph_to_json` with a small two-node graph.

---

## Milestone 5 — React Frontend (Stats Panel + Dependency Graph)

### Objective
Build the minimal React + Vite frontend that fetches `/analyze`, displays
the metrics in a summary panel, and renders the dependency graph
interactively with React Flow.

### Status
`[ ] pending`

### Files / Components Involved
```
frontend/
  src/
    App.jsx                  ← NEW: root component, fetch logic
    components/
      StatsPanel.jsx         ← NEW: displays metrics dict
      GraphView.jsx          ← NEW: renders React Flow graph
  index.html
  vite.config.js
package.json                 ← NEW: React, Vite, React Flow deps
```

### Dependencies
- Milestone 4 complete (backend returns unified JSON)
- Node.js + npm (for frontend build tooling)
- `react`, `react-dom`, `@xyflow/react`, `vite`

### Implementation Steps
1. Scaffold the frontend with `npm create vite@latest frontend -- --template react`.
2. Install `@xyflow/react`: `npm install @xyflow/react`.
3. Create `App.jsx`:
   - A text input for the repo path + "Analyze" button.
   - On click: `fetch("http://localhost:8000/analyze", {method:"POST", body: JSON.stringify({repo_path})})`.
   - Store the response in state: `{ graph, metrics }`.
   - Render `<StatsPanel metrics={metrics} />` and `<GraphView graph={graph} />`.
4. Create `StatsPanel.jsx`:
   - Simple list/table rendering all keys from the `metrics` object.
   - No styling required beyond readable layout.
5. Create `GraphView.jsx`:
   - Map `graph.nodes` to React Flow `nodes` array (add a basic `position`
     using a layout algorithm or fixed grid — keep it simple).
   - Map `graph.edges` to React Flow `edges` array.
   - Render `<ReactFlow nodes={nodes} edges={edges} fitView />`.
6. Add CORS middleware to `backend/api/main.py` so the frontend can call
   the backend during local development.

### Expected Output
- `npm run dev` starts the frontend at `http://localhost:5173`.
- Entering a valid local Python repo path and clicking "Analyze" shows:
  - A stats panel with all metrics.
  - An interactive dependency graph with nodes and edges.
- This is the **first fully working end-to-end MVP milestone**.

### Testing Approach
Manual browser test against `sample-repository/`. No automated frontend
tests in the MVP. Verify the full round-trip: input → API call → graph
rendered in the browser.

---

## Milestone 6 — Sample Repository + Polish

### Objective
Select and commit a small real Python repository (~30–60 files with genuine
commit history) as `sample-repository/`. Run Git DNA against it, verify
output quality, and fix any edge cases discovered.

### Status
`[ ] pending`

### Files / Components Involved
```
sample-repository/     ← NEW: real Python repo (submodule or cloned copy)
backend/analyzers/     ← MODIFIED: bug fixes from real-repo testing
```

### Dependencies
- Milestone 5 complete (full pipeline working)

### Implementation Steps
1. Choose a well-known small Python project with genuine history (e.g.
   `flask`, `click`, or a comparable project with 30–60 `.py` files).
2. Add it as a git submodule or copy it into `sample-repository/`.
3. Run Git DNA against it and inspect results:
   - Are dependency edges plausible?
   - Are git stats correct?
   - Does the graph render cleanly in the browser?
4. Fix any bugs uncovered (syntax errors in `.py` files breaking the AST
   parser, binary files causing issues, missing git history, etc.).
5. Update `README.md` with setup and run instructions.

### Expected Output
- Running Git DNA on `sample-repository/` produces a legible graph in the
  browser with correct metrics.
- `README.md` contains clear local setup instructions.

### Testing Approach
Manual end-to-end run. All existing pytest tests still pass.

---

## Milestone 7 — Before/After Measurement

### Objective
Record the real, timed "before" (manual exploration) and "after" (Git DNA)
measurements on the sample repository as specified in Section 10 of the
spec, and add them to the README.

### Status
`[ ] pending`

### Files / Components Involved
```
README.md              ← MODIFIED: before/after metrics table
```

### Dependencies
- Milestone 6 complete

### Implementation Steps
1. Time yourself manually finding the most-connected files without Git DNA.
2. Time yourself manually finding the most-changed files via `git log`.
3. Count how many files you had to open manually to build a mental map.
4. Record all figures.
5. Run Git DNA and record the equivalent times.
6. Fill in the table in `README.md` with real numbers.

### Expected Output
- README contains a completed before/after table with real measured numbers.

### Testing Approach
N/A — this is a measurement and documentation task.

---

## Milestone 8 — Evidence, README, and Submission

### Objective
Collect all Bob evidence (screenshots of Plan mode, Agent mode, subagents,
parallel tasks, test runs), finalize the README, and prepare the demo video.

### Status
`[ ] pending`

### Files / Components Involved
```
bob-evidence/
  LOG.md             ← MODIFIED: running log of Bob usage
  plan.png           ← NEW: screenshot of Bob plan output
  agent.png          ← NEW: screenshot of Bob agent mode
  subagents.png      ← NEW: screenshot of Bob subagents
  parallel-tasks.png ← NEW: screenshot of parallel tasks
  final-result.png   ← NEW: screenshot of finished frontend
README.md            ← MODIFIED: final polish, demo link
```

### Dependencies
- Milestones 1–7 complete

### Implementation Steps
1. Take screenshots of each Bob feature used during development.
2. Fill in `bob-evidence/LOG.md` with a narrative of how Bob was used.
3. Final README review: ensure setup, run instructions, and metrics table
   are correct.
4. Record demo video (screen capture of the full analysis run).
5. Make repository public.

### Expected Output
- All checklist items in Section 15 "Definition of Done" of the spec are
  ticked off.
- Repository is public with complete README and evidence.

### Testing Approach
Review each item in the Definition of Done checklist:
- `/analyze` returns full data ✓
- Frontend shows stats + graph ✓
- pytest suite passes ✓
- Before/after metrics recorded ✓
- Bob evidence collected ✓
- Repository is public ✓

---

## Milestone Dependency Order

```
M1 (scaffold + file walker)
 └── M2 (dependency analyzer)
      └── M4 (graph model + metrics)  ←── M3 (git history)
           └── M5 (frontend MVP)  ← FIRST END-TO-END
                └── M6 (sample repo + polish)
                     └── M7 (measurement)
                          └── M8 (evidence + submission)
```

M2 and M3 can be built in parallel (they share only the file list interface
from M1, not each other's code). M4 depends on both.

---

## Definition of Done (from spec §15)

- [ ] Can point Git DNA at a local Python repo and get back structure,
      dependencies, and git history via `/analyze`.
- [ ] Frontend displays stats panel and interactive dependency graph.
- [ ] pytest suite passes for all analyzer modules.
- [ ] Real before/after metrics recorded in README table.
- [ ] Bob evidence collected across Plan/Agent/Subagents/Parallel/Testing.
- [ ] Repository is public, structured as in Section 7 of architecture.md.
