# RIPPLE AI — Agentic Code Impact Investigator & Ask the Agent

**RIPPLE AI** is an advanced **Agentic Code Impact Analyzer** and **AI Detective** designed to analyze software repositories, track code change blast radiuses, investigate regressions/bugs using ReAct-style agentic loops, and run safe test sandboxes.

---

## 🌟 Key Features

1. **Agentic Code Impact Analyzer & Blast Radius Calculation**:
   - Calculates transitive dependency chains (`A calls B calls C`).
   - Identifies all affected functions, classes, and files when a code entity is modified.
   - Calculates deterministic **Risk Scores (0-100)** and risk levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) based on centralities and affected targets.

2. **Ask the Agent (ReAct Investigation Loop)**:
   - Powered by a ReAct (Reasoning + Acting) autonomous agent loop.
   - Iteratively calls repository inspection tools to form hypotheses, collect evidence, and determine root causes.
   - Fallback engine allows deterministic no-LLM reasoning when API limits are reached.

3. **Repository Import (Local & Remote Git Clone)**:
   - Import any local project directory or clone public Git repositories via HTTPS/SSH.
   - Automatic AST parsing and symbol extraction upon import.

4. **Interactive Code & Dependency Graph Visualizer**:
   - Built with ReactFlow for interactive graph navigation.
   - Dynamic node color coding (Classes, Functions, High-Risk Impacted Nodes).
   - Node-click inspector detailing line ranges, source code signatures, and parent modules.

5. **Evidence-Backed Reasoning & Root Cause Breakdown**:
   - Structured evidence collection across `CODE`, `GRAPH`, `GIT`, `TEST`, and `SEARCH`.
   - Clear confidence metrics (`High`, `Medium`, `Low`) and root cause confirmation status (`CONFIRMED`, `LIKELY`, `POSSIBLE`).

6. **Lightweight Ephemeral Memory Module**:
   - Stores up to 20 recent investigation results in an in-memory thread-safe `deque`.
   - Offers target lookup to retrieve prior analysis context without replacing fresh code analysis.
   - Clears memory automatically upon backend restarts without modifying persistent databases.

7. **Custom OpenRouter & Free Model Support**:
   - Flexible model switching via `.env` configuration.
   - Works with free models on OpenRouter (e.g. `minimax/minimax-m3:free`, `meta-llama/llama-3.3-70b-instruct:free`, `deepseek/deepseek-r1:free`).

---


## 🛠️ Provided Tools & Capabilities

The agent operates over an extensible toolkit defined in `backend/app/tools/agent_tools.py`:

| Tool Name | Category | Description |
| :--- | :--- | :--- |
| `get_repository_symbols` | **AST Analysis** | Extracts classes, functions, and line ranges across Python ASTs. |
| `get_dependency_graph` | **Graph** | Builds NetworkX directional dependency graphs (`CONTAINS`, `CALLS`). |
| `calculate_impact` | **Impact** | Traverses inverse call graphs to compute impact chains & risk scores. |
| `get_git_status` | **Git** | Inspects modified files, uncommitted changes, and active branch state. |
| `get_git_commit_history` | **Git** | Fetches recent commit logs, authors, and timestamps. |
| `get_git_diff` | **Git** | Visualizes exact line-by-line diffs between commits/branches. |
| `search_code` | **Search** | Performs regex & string search across the repository codebase. |
| `get_symbol_source` | **Code Inspection** | Reads full source code for a specific class or function. |
| `run_tests` | **Sandbox Test** | Runs pytest target suites in an isolated execution sandbox. |

---

## 🔄 API Flow Architecture

```
                                 ┌─────────────────────────────────┐
                                 │     React Frontend (Vite)       │
                                 └────────────────┬────────────────┘
                                                  │
                                                  │ HTTP POST /api/v1/investigate
                                                  │ WebSocket /api/v1/investigate/{repo_id}
                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                FastAPI Backend Service                                   │
│                                                                                          │
│ ┌─────────────────────────┐     ┌───────────────────────────┐    ┌─────────────────────┐ │
│ │  Repository Controller  │ ──> │   Tree-sitter AST Parser  │ ─> │ NetworkX Graph Engine│ │
│ └─────────────────────────┘     └───────────────────────────┘    └─────────────────────┘ │
│                                                                             │            │
│                                                                             ▼            │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │                        ReAct Agent Loop (RippleOrchestrator)                         │ │
│ │                                                                                      │ │
│ │  THOUGHT: Formulate query hypothesis & plan tool call.                              │ │
│ │  ACTION: Execute tool (calculate_impact / search_code / get_git_diff / run_tests)    │ │
│ │  OBSERVATION: Parse tool output & gather Evidence (CODE, GRAPH, GIT, TEST).          │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
                                ┌──────────────────────────────────┐
                                │   OpenRouter / Gemini LLM API    │
                                └──────────────────────────────────┘
```

---

## ⚙️ Environment Configuration

Users must configure their own **OpenRouter API Key** in the root `.env` file before running the agent.

1. Create or edit `.env` in the project root:
   ```ini
   # OpenRouter API Key configuration
   OPENROUTER_API_KEY=your_actual_openrouter_api_key_here
   OPENROUTER_MODEL=minimax/minimax-m3:free
   ```
2. You can generate a free API key at [openrouter.ai](https://openrouter.ai/).

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.12+ installed
- Node.js 18+ & npm installed

### 1. Install Backend Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

### 3. Bootstrap Sample Repository & Run Tests
```bash
py backend/setup_sample_repo.py
py -m pytest -v
```

### 4. Start the Application

#### Start Backend Server:
```bash
py backend/app/main.py
```
*Backend runs on `http://localhost:8000` (Swagger docs: `http://localhost:8000/docs`)*

#### Start Frontend Web UI:
On Windows PowerShell:
```powershell
cmd /c "npm run dev --prefix frontend"
```
Or inside `frontend` folder:
```powershell
cd frontend
cmd /c "npm run dev"
```
*Frontend runs on `http://localhost:5173`*

---

## 📁 Repository Structure

```
ripple-ai/
├── backend/
│   ├── app/
│   │   ├── agent/        # ReAct Orchestrator, Evidence Collector, OpenRouter client
│   │   ├── analysis/     # AST parsing, symbols, relationships, NetworkX graph & risk
│   │   ├── api/          # FastAPI routers (investigation, repositories, health)
│   │   ├── database/     # SQLite storage connection & migrations
│   │   ├── execution/    # Isolated test execution sandbox
│   │   ├── git/          # GitPython integration
│   │   ├── models/       # Pydantic schemas and response models
│   │   ├── search/       # Codebase search engine
│   │   ├── tools/        # agent_tools.py (14+ intelligence tools)
│   │   └── main.py       # FastAPI app entrypoint
│   └── setup_sample_repo.py
├── frontend/             # React 18 + TailwindCSS + ReactFlow + Framer Motion
│   ├── src/
│   │   ├── App.tsx       # Main dashboard, Ask the Agent panel, Import modal
│   │   └── index.css     # Design system & scrollbar bounds
├── sample-repositories/  # Analyzed and cloned repositories
├── tests/                # Pytest verification suite
├── demo_investigation.py # Interactive terminal CLI demo
├── requirements.txt      # Python dependencies
└── README.md             # Technical documentation
```
