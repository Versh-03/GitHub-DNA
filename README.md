# GitHub DNA

> **Agentic AI Engineering Platform for Python Repositories**

GitHub DNA accepts a public Python GitHub repository URL, analyzes its AST structure, and deploys an AI-driven engineering workflow to investigate potential bugs, propose fixes, generate tests, and verify outcomes using real test execution inside an isolated container sandbox.

---

## 1. Core Architecture

```
Repository URL
      │
      ▼
Repository Ingestion (Safe shallow-clone, size limits, SSRF prevention)
      │
      ▼
AST Static Analysis (Imports, functions, classes, NetworkX module graph)
      │
      ▼
Agent B: Planner (Selects investigation target based on repository evidence)
      │
      ▼
Agent C: Investigator (Read-only tools: get_outline, read_file, search_code)
      │
      ▼
Deterministic Verifier (Grounding check verifying quoted evidence verbatim)
      │
      ▼
Agent D: Test Generator (Focused pytest script asserting correct behavior)
      │
      ▼
Isolated Docker Sandbox (--network none, 256MB RAM, 1 CPU, timeout)
      ├── Baseline Test Run (Unpatched repo)
      └── Patched Test Run (Fix applied in temporary volume)
      │
      ▼
Bounded Feedback Loop (Retries fix with test failure output if verification fails)
      │
      ▼
Structured Audit Report (Distinguishes suggestions from verified results)
```

---

## 2. Specialized Agents

- **Agent A: Repository Analyst (Deterministic AST)**
  - Extracts Python modules, imports, function/class signatures, and line numbers.
  - Resolves internal vs. external dependencies into a NetworkX directed graph.
  - Zero LLM quota spent on pure structural extraction.

- **Agent B: Planner / Orchestrator**
  - Considers high-level repository complexity metrics and function counts.
  - Selects a high-impact target module with explicit reasoning and focus area.

- **Agent C: Code Investigator**
  - Concurrently uses safe, path-confined inspection tools (`get_outline`, `read_file`, `search_code`).
  - Reports findings with exact quoted lines, severity, and proposed fix.

- **Agent D: Test & Verification Agent**
  - Produces isolated test scripts verifying the identified condition.
  - Validates test syntax and prohibits dangerous imports (`subprocess`, `socket`, `http`).
  - Executes tests against both baseline and patched code within a disposable Docker container with all network access disabled (`--network none`).
  - Executes a bounded feedback loop (re-prompting with actual stdout/stderr) if the initial fix fails verification.

---

## 3. Provider & Model Configuration

- **Provider:** Groq API
- **Model ID:** `openai/gpt-oss-20b` (fixed for MVP)
- **Base URL:** `https://api.groq.com/openai/v1`
- **Environment Variables:**
  - `GROQ_API_KEY` or `LLM_API_KEY` in `backend/.env`
  - `LLM_BASE_URL` (defaults to Groq endpoint)
  - `LLM_MODEL` (defaults to `openai/gpt-oss-20b`)

---

## 4. Execution Sandbox & Security Boundaries

Repository code and LLM-generated tests are treated as strictly untrusted:
- Tests run inside disposable Docker containers (`github-dna-sandbox:latest` / `python:3.12-slim`).
- Network access is completely disabled (`--network none`).
- Resources are strictly capped (`--memory 256m --cpus 1.0 --pids-limit 64`).
- Host repository directories are never mutated: code is copied into a temporary scratch directory before running.
- Pycode byte generation is suppressed (`PYTHONDONTWRITEBYTECODE=1`) and permissions match the host user (`--user $(id -u):$(id -g)`).

---

## 5. Quickstart & Exhibition Demonstration

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- Docker daemon running

### 1. Configure Credentials
Copy `backend/.env.example` to `backend/.env` and insert your Groq API key:
```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set GROQ_API_KEY=your_key
```

### 2. Launch Platform
Run the unified start script:
```bash
./start.sh
```
Or start backend and frontend individually:
```bash
# Terminal 1: Backend
PYTHONPATH=backend backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

### 3. Open Dashboard
Open [http://localhost:5173](http://localhost:5173) in your browser.

- Click **retail-core-sample** preset for an instant end-to-end demonstration of bug detection, test generation, and Docker sandbox execution.
- Or input any public Python repository URL (e.g. `https://github.com/pallets/click`).

---

## 6. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check and Docker availability status |
| `POST` | `/analyze` | Validates GitHub URL and computes AST analysis |
| `POST` | `/investigate` | Deploys Planner, Investigator, Test Generator, and Sandbox |
| `GET` | `/runs/{run_id}` | Retrieves persisted run data, findings, and events |
| `POST` | `/verify` | Re-executes on-demand tests inside the container sandbox |

---

## 7. Limitations & MVP Scope

- **Language Support:** Python repositories only.
- **Repository Scope:** Public repositories up to 50MB and 300 Python files.
- **Verification Guarantee:** Passing a focused unit test validates the specific condition tested, but does not guarantee the entire repository is defect-free.
