# Git DNA — Requirements & Specification

## 1. Project Summary

Git DNA is a developer onboarding and repository-understanding tool. Given a
local Git repository, it automatically analyzes structure, code dependencies,
and Git history, then presents the results as an interactive graph and
summary dashboard in a web UI.

Pitch: "Google Maps for understanding a codebase."

## 2. Problem Statement

When a developer joins an unfamiliar codebase, they typically have to
manually:

- explore the folder structure
- open many source files one by one
- trace imports/dependencies by hand
- figure out which files/modules are central or important
- inspect Git history to see what changes often
- build a mental map of the architecture
- ask a teammate to explain things

This is slow, error-prone, and doesn't scale as repos grow. Git DNA
automates this into a single analysis + visualization step.

## 3. Scope: MVP (V1)

**In scope:**

1. Accept a local Git repository path as input.
2. Walk the repository and classify files (source, test, docs, config, etc.).
3. Parse Python import statements (via the `ast` module) to build a
   dependency graph between files/modules.
4. Analyze Git history: commit counts, contributors, most-frequently-changed
   files.
5. Compute repository statistics (file counts, largest files, test coverage
   of files, etc.).
6. Expose all of the above through a FastAPI backend (`/analyze` endpoint).
7. Display results in a React frontend:
   - summary stats panel
   - interactive dependency graph (React Flow)
8. Cache analysis results as JSON on disk (no database).

**Explicitly out of scope for V1** (future/stretch):

- Multi-language import parsing (JavaScript, Java, etc.)
- AI-powered natural-language Q&A about the repo
- GitHub OAuth / remote repo cloning
- 3D visualization
- User accounts, persistence beyond local JSON cache
- Advanced code-complexity metrics (cyclomatic complexity, etc.)

## 4. Target Language for V1

Python only. The analyzer parses `import` / `from ... import ...`
statements using Python's built-in `ast` module — no external parsing
dependency required. Architecture must keep the analyzer/graph model
language-agnostic so a second language can be added later without a
rewrite (see Section 8).

## 5. Architecture

```
Repository path
      ↓
Repository Analyzer (file/dir walk, classification)
      ↓
Dependency Analyzer (ast-based import parsing → graph edges)
      ↓
Git History Analyzer (GitPython/git log → commit stats)
      ↓
Repository Metrics (aggregates results from above)
      ↓
Graph Model (networkx) → JSON export
      ↓
FastAPI backend (/analyze endpoint)
      ↓
React frontend (stats panel + React Flow graph)
```

No database. No auth. No cloud deployment required — runs locally.

## 6. Tech Stack

**Backend:** Python 3.11+, FastAPI, uvicorn, GitPython, networkx, pytest

**Frontend:** React + Vite, React Flow, fetch/axios

**Analysis:** Python standard library (`ast`, `pathlib`, `os`), GitPython

## 7. Repository Structure (target)

```
git-dna/
├── backend/
│   ├── api/
│   │   └── main.py
│   ├── analyzers/
│   │   ├── repository.py      # file/dir structure analysis
│   │   ├── dependency.py      # ast-based import graph
│   │   └── git_history.py     # git log analysis
│   └── models/
│       └── graph.py           # networkx graph builder + JSON export
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── GraphView.jsx
│   │   │   └── StatsPanel.jsx
│   │   └── App.jsx
│   └── ...
├── tests/
│   ├── test_repository.py
│   ├── test_dependency.py
│   └── test_git_history.py
├── docs/
│   ├── GIT_DNA_REQUIREMENTS.md  (this file)
│   ├── architecture.md
│   └── workflow.md
├── bob-evidence/
│   ├── plan.png
│   ├── document-understanding.png
│   ├── agent.png
│   ├── subagents.png
│   ├── parallel-tasks.png
│   ├── final-result.png
│   └── LOG.md
├── sample-repository/          # the repo Git DNA analyzes for the demo
├── README.md
└── requirements.txt / package.json
```

## 8. Data Model

**File node:**
```json
{
  "path": "backend/analyzers/dependency.py",
  "type": "source",
  "language": "python",
  "size_bytes": 4210,
  "commit_count": 12,
  "last_modified": "2026-09-10"
}
```

**Dependency edge:**
```json
{
  "source": "backend/api/main.py",
  "target": "backend/analyzers/repository.py",
  "type": "import"
}
```

Keeping node/edge shape generic (not Python-specific field names) is what
lets a future language analyzer plug into the same graph model.

## 9. Repository Metrics to Compute

- total files, source files, test files, doc files, directories
- total commits, contributor count (if available)
- top N most-frequently-changed files
- top N most-connected files (highest in+out degree in dependency graph)
- largest files by size
- recently modified files
- total dependency edges discovered

## 10. Measurable Before/After Impact

We will measure real numbers on the chosen sample repository — no
fabricated figures.

| Metric | Manual workflow | Git DNA |
|---|---|---|
| Time to identify most-connected/core files | timed manually | timed tool run |
| Files manually opened to build a mental map | counted | 0 (viewed via graph) |
| Time to find most-frequently-changed files | timed manually (`git log` digging) | instant from stats panel |
| Dependency relationships identified | manual trace, counted | counted from graph edges |

## 11. Sample Repository

A small-to-medium, real, public Python repository (~30–60 Python files)
with genuine commit history, chosen for legibility of the resulting graph.
Final choice to be confirmed and placed in `sample-repository/` (or
referenced by path/URL) before demo recording.

## 12. Non-Functional Requirements

- Must run fully locally (no cloud dependency) for demo reliability.
- Analysis of the sample repo should complete in a reasonably short time
  (seconds, not minutes) to keep the live demo smooth.
- Code must be simple enough for a solo beginner/intermediate developer to
  explain and defend, not just generated and pasted in.
- pytest coverage on analyzer modules (pure functions — repository walk,
  dependency parsing, git history parsing) since these are the core logic.

## 13. Development Process Notes (for IBM Bob)

This project is being built solo using IBM Bob 2.0 as the agentic
development tool. Intended usage of Bob's features:

- **Document understanding**: this requirements doc is the shared context
  for planning and implementation.
- **Plan mode**: used to turn this spec into a phased implementation plan
  before any large implementation step.
- **Agent mode**: used for actual implementation of backend analyzers,
  API routes, and frontend components.
- **Subagents**: used where tasks are genuinely independent, e.g. one
  subagent for dependency/import analysis, one for Git history analysis,
  one for reviewing test coverage/maintainability.
- **Parallel/background tasks**: used once the core pipeline works, to
  refine dependency analysis, Git history analysis, and frontend polish
  concurrently.
- **Testing/debugging**: Bob is used to write and fix pytest tests for the
  analyzer modules.

## 14. Phased Implementation Plan

1. **Phase 1** — Backend skeleton: FastAPI app + `/analyze` endpoint +
   file/directory walker only.
2. **Phase 2** — Dependency analyzer (ast-based) → graph edges, with tests.
3. **Phase 3** — Git history analyzer, with tests.
4. **Phase 4** — Repository metrics aggregator combining Phases 1–3.
5. **Phase 5** — Frontend: fetch `/analyze`, render stats panel + graph.
   First fully working end-to-end milestone.
6. **Phase 6** — Parallel-task refinement (dependency analysis, git
   analysis, frontend polish) demonstrating Bob's parallel task feature.
7. **Phase 7** — Measure real before/after numbers on the sample repo.
8. **Phase 8** — README, evidence organization, submission statements,
   demo video.

## 15. Definition of Done (V1 / MVP)

- [ ] Can point Git DNA at a local Python repo and get back structure,
      dependencies, and git history via `/analyze`.
- [ ] Frontend displays stats panel and interactive dependency graph.
- [ ] pytest suite passes for all analyzer modules.
- [ ] Real before/after metrics recorded in README table.
- [ ] Bob evidence collected across Plan/Agent/Subagents/Parallel/Testing.
- [ ] Repository is public, structured as in Section 7.
