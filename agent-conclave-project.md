# Multi-Agent Conclave Project – GCP Implementation Spec

## 1. Purpose

This document specifies a GCP-aware multi-agent "Model Conclave" system that can be orchestrated and invoked by a CLI agent or HTTP clients. It describes agents, tools, data stores, orchestration framework, configuration, and deployment on Google Cloud Run.

Pattern: **Primary Orchestrator → Research Sub-Agents (3) → Synthesizer Agent**, using MCP tools plus Firestore and Cloud SQL, orchestrated by LangGraph and ADK, with models served via LiteLLM.

---

## 2. High-Level Architecture

- **Runtime / API**
  - Containerized Python backend (FastAPI or similar) exposing HTTP endpoints and an optional CLI entrypoint.
  - Deployed on **Google Cloud Run** as a stateless service.

- **Orchestration**
  - **LangGraph StateGraph** defines the council workflow and state machine (sequential + parallel nodes).
  - **Google Agent Development Kit (ADK)**: Implemented via `vertexai.agent_engines.LangchainAgent` and `LanggraphAgent` templates.
  - **LiteLLM proxy** is the multi-model gateway for Claude, GPT-5.2, and Gemini (can also use native Vertex AI).

- **Agents**
  - ResearchAgentA (Claude), ResearchAgentB (GPT-5.2), ResearchAgentC (Gemini) – Parallel nodes in LangGraph.
  - SynthesizerAgent – Sequential node after parallel join.
  - Coordinator – Managed by the LangGraph orchestrator in `backend/graph.py`.

---

## 4. Agents and Responsibilities (Implementation Details)

- **ResearchAgentA/B/C**:
  - Defined as `LangchainAgent` in `backend/agents.py`.
  - Tools: `search_web`, `search_gcp_docs`, `record_citation`.
  - Each agent maintains independent state during the research phase.

- **SynthesizerAgent**:
  - Tools: `get_session_citations` (fetches all sources from DB).
  - Logic: Clusters sources by `source_url` and provides consensus/unique insight analysis.

---

## 14. Implementation Progress (Status: April 2026)

- [x] Phase 1: Foundation & Infrastructure (GCP & Local)
- [x] Phase 2: Data Layer & DB MCP (Cloud SQL + Firestore)
- [x] Phase 3: Search MCP Server Implementation
- [x] Phase 4: Agent Development (Google ADK / Vertex AI)
- [x] Phase 5: Orchestration Logic (LangGraph Parallel Flow)
- [x] Phase 6: Backend API (FastAPI)
- [ ] Phase 7: CLI Interface (Deferred)
- [x] Phase 8: Deployment & Validation Manifests (Cloud Build + Docker)

### Deviation Notes:
- **ADK Implementation**: The project uses the `vertexai.agent_engines` namespace (v1.112+) which is the current production-ready implementation of the Google ADK patterns.
- **Coordinator**: The coordinator logic was moved into the LangGraph state machine (`backend/graph.py`) for more robust state management compared to a standalone agent.

- **MCP Tools**
  - Search MCP (web/academic search).
  - Task/Calendar MCP (Google Calendar + task system).
  - Google Developer Knowledge MCP (GCP/dev docs search).
  - Database MCP (mediated access to Cloud SQL + Firestore).

- **Storage**
  - **Cloud SQL (Postgres)** for citation storage + vector search.
  - **Firestore (Native mode)** for session and progress state.

---

## 3. Configuration and Environment (.env)

These keys live in `.env` for local dev. In Cloud Run, configure equivalent environment variables (optionally sourced from Secret Manager).

### 3.1 Core GCP

- `GCP_PROJECT_ID` – main GCP project id.
- `GCP_REGION` – e.g., `asia-south1` (Mumbai) or `us-central1`.
- `GCP_FIRESTORE_PROJECT_ID` – usually same as `GCP_PROJECT_ID`.
- `GCP_SERVICE_ACCOUNT_EMAIL` – service account used by Cloud Run.

### 3.2 Firestore (Session State)

- `FIRESTORE_EMULATOR_HOST` – set only in local dev.
- Production Firestore access is via IAM on the service account; no password in env.

### 3.3 Cloud SQL (Postgres – Citations)

- `CLOUD_SQL_INSTANCE_CONNECTION_NAME` – `project:region:instance`.
- `CLOUD_SQL_DB_NAME` – e.g., `council_db`.
- `CLOUD_SQL_DB_USER`
- `CLOUD_SQL_DB_PASSWORD` – stored in Secret Manager and injected at runtime.
- Optional: `CLOUD_SQL_USE_PSC` (true/false) if using Private Service Connect.

### 3.4 LLM / LiteLLM / Models

- `LITELLM_BASE_URL` – HTTP base URL of LiteLLM proxy.
- `LITELLM_API_KEY` – key for LiteLLM itself (if protected).
- Provider keys (LiteLLM uses these under the hood):
  - `OPENAI_API_KEY` – for GPT-5.2.
  - `ANTHROPIC_API_KEY` – for Claude.
  - `GEMINI_API_KEY` or `GOOGLE_API_KEY` – for Gemini / Vertex.

Model route env vars:

- `LITELLM_ROUTE_RESEARCH_A=claude-3.7-sonnet` (example).
- `LITELLM_ROUTE_RESEARCH_B=gpt-5.2` (example).
- `LITELLM_ROUTE_RESEARCH_C=gemini-2.5-pro` (example).
- `LITELLM_ROUTE_SYNTHESIZER=gpt-5.2` (or Claude).

### 3.5 MCP Servers

- `MCP_SEARCH_SERVER_URL`
- `MCP_TASKCAL_SERVER_URL`
- `MCP_GDEV_DOCS_SERVER_URL`
- `MCP_DB_SERVER_URL`

### 3.6 App / Orchestration

- `COUNCIL_TOTAL_MODELS=3`
- `LANGGRAPH_STORE_BACKEND=firestore` (or `memory` for dev).
- `ADK_LOG_LEVEL=INFO`
- `ADK_TRACING_ENDPOINT` – optional tracing/observability.

---

## 4. Agents and Responsibilities

### 4.1 Agent Types Summary

- **Primary Orchestrator**
  - ADK: `LlmAgent` using Coordinator/Dispatcher pattern.
  - LangGraph: Sequential node at the start of the graph.

- **ResearchAgentA/B/C**
  - ADK: `LlmAgent` worker agents.
  - LangGraph: Parallel nodes in the same superstep.

- **SynthesizerAgent**
  - ADK: `LlmAgent` analyzer.
  - LangGraph: Sequential node after parallel join.

- **DB Helper (optional)**
  - ADK: non-LLM `BaseAgent` or utility.
  - LangGraph: simple sequential utility node.

### 4.2 Primary Orchestrator Agent

- Input: user question, optional `session_id`.
- Responsibilities:
  - Initialize or resume a council session in Firestore.
  - Set `progress.total_models = 3`.
  - Kick off LangGraph graph execution for the session.
  - Expose high-level status: `[2/3 models completed]`.

### 4.3 Research Sub-Agents (A/B/C)

Each research agent:

- Receives the same `user_question` + `session_id`.
- Performs independent, deep research with 30–50 citations.
- Uses MCP tools:
  - **Search MCP** for web/academic sources.
  - **Google Developer Knowledge MCP** for GCP/dev topics.
  - **Task/Calendar MCP** when the query involves scheduling or tasks.
  - **Database MCP** to write citations and update progress.
- Writes:
  - One `model_runs` row in Cloud SQL.
  - 30–50 `citations` rows linked to that `model_runs` row.
  - Short agent summary and status in Firestore (`agent_runs` subcollection).

### 4.4 Synthesizer Agent

- Triggered when all 3 research agents complete.
- Uses Database MCP to:
  - Load `model_runs` and `citations` for the `session_id`.
  - Run SQL joins on `normalized_key` to find overlapping sources.
  - Run vector similarity search to cluster related citations.
- Produces a structured Council Synthesis Report (consensus, disagreements, unique insights).
- Writes report to Firestore and returns it via API/CLI.

---

## 5. Model Assignment (Claude, GPT-5.2, Gemini)

Using LiteLLM routes:

- **ResearchAgentA (Claude seat)**
  - Model route: `process.env.LITELLM_ROUTE_RESEARCH_A` (e.g., `claude-3.7-sonnet`).
  - Provider key: `ANTHROPIC_API_KEY`.

- **ResearchAgentB (GPT-5.2 seat)**
  - Model route: `process.env.LITELLM_ROUTE_RESEARCH_B` (e.g., `gpt-5.2`).
  - Provider key: `OPENAI_API_KEY`.

- **ResearchAgentC (Gemini seat)**
  - Model route: `process.env.LITELLM_ROUTE_RESEARCH_C` (e.g., `gemini-2.5-pro`).
  - Provider key: `GEMINI_API_KEY` / `GOOGLE_API_KEY`.

- **SynthesizerAgent**
  - Model route: `process.env.LITELLM_ROUTE_SYNTHESIZER` (typically your best reasoning model, e.g., GPT-5.2 or Claude).

In ADK, each `LlmAgent` is configured with its route; underlying HTTP client points to `LITELLM_BASE_URL` with `LITELLM_API_KEY`.

---

## 6. MCP Tools

### 6.1 Search MCP

- Action: `search(query: string, top_k: int)`.
- Response schema: `[{ url, title, snippet, source_type, embedding? }, ...]`.

### 6.2 Task/Calendar MCP

- Wraps Google Calendar and a task system.
- Example actions:
  - `list_events(time_range)`
  - `create_event(summary, start, end, attendees, metadata)`
  - `create_task(title, description, due_date, metadata)`

### 6.3 Google Developer Knowledge MCP

- Specialized search over Google/GCP/dev docs.
- Example actions:
  - `search_docs(query, product_filter)`
  - `get_doc(doc_id_or_url)`

### 6.4 Database MCP – Scope and Usefulness

- Provides a mediated interface to Cloud SQL and Firestore.
- Recommended scope:
  - **Allowed**:
    - Parameterized `INSERT`/`SELECT`/`UPDATE` against `model_runs` and `citations`.
    - Reading/writing `sessions` and `agent_runs` docs in Firestore.
  - **Not allowed**:
    - DDL (schema changes), destructive commands, or arbitrary table access.

Example actions:

- `sql_query(sql: string, params: dict)` – read-only.
- `sql_execute(sql: string, params: dict)` – restricted writes.
- `firestore_get(collection: string, doc_id: string)`.
- `firestore_update(collection: string, doc_id: string, data: dict)`.

**Why it is useful here:**

- Keeps DB credentials out of prompts; only MCP server holds them.
- Provides a uniform tool interface for all agents.
- Enables Synthesizer and Researchers to drive data access in a controlled way.

**Where not to use MCP:** schema migrations, high-volume ETL; those should be handled by backend migrations or ORM.

---

## 7. Data Model

### 7.1 Firestore (Session State)

Collections:

- `sessions/{sessionId}`
  - `user_id: string`
  - `status: 'pending' | 'in_progress' | 'completed' | 'error'`
  - `progress: { completed_models: int, total_models: int }`
  - `current_stage: 'research' | 'synthesis'`
  - `created_at`, `updated_at` (timestamps)

- `sessions/{sessionId}/messages/{messageId}`
  - `role: 'user' | 'agent'`
  - `agent_name?: string`
  - `content: string`
  - `created_at`

- `sessions/{sessionId}/agent_runs/{runId}`
  - `agent_name: string`
  - `model_run_id: string` (FK into Cloud SQL)
  - `status: 'pending' | 'running' | 'completed' | 'error'`
  - `summary: string`
  - `created_at`, `updated_at`

### 7.2 Cloud SQL (Postgres – Citations)

Tables:

- `model_runs`
  - `id SERIAL PRIMARY KEY`
  - `session_id VARCHAR`
  - `agent_name VARCHAR`
  - `model_id VARCHAR`
  - `created_at TIMESTAMPTZ`

- `citations`
  - `id SERIAL PRIMARY KEY`
  - `model_run_id INTEGER REFERENCES model_runs(id)`
  - `source_url TEXT`
  - `source_type VARCHAR`
  - `title TEXT`
  - `snippet TEXT`
  - `raw_citation TEXT`
  - `normalized_key TEXT`
  - `embedding VECTOR`  // via Postgres vector extension

Indices and views can be added for faster overlap/similarity queries.

---

## 8. LangGraph Orchestration

### 8.1 State Definition

```ts
interface CouncilState {
  session_id: string;
  user_question: string;
  progress: { completed_models: number; total_models: number };
  model_run_ids: string[]; // Cloud SQL model_runs IDs
  agent_summaries: Record<string, string>;
  ready_for_synthesis: boolean;
}
```

### 8.2 Nodes and Flow

1. `init_session` (Sequential)
   - Create Firestore session if needed.
   - Set `progress.total_models = 3`.
   - Save `session_id` and `user_question` in state.

2. `research_A` / `research_B` / `research_C` (Parallel)
   - Each node:
     - Calls respective ADK `LlmAgent` (A/B/C) with `user_question`.
     - Uses MCP tools to gather sources.
     - Uses DB MCP to write `model_runs` + `citations` to Cloud SQL.
     - Uses DB MCP to increment `progress.completed_models` and update `agent_runs` in Firestore.
     - Updates `model_run_ids` and `agent_summaries` in state.

3. `check_completion` (Sequential)
   - Reads `progress` from state or Firestore.
   - If `completed_models < total_models`, halt or reschedule.
   - If complete, set `ready_for_synthesis = true`.

4. `synthesizer` (Sequential)
   - Precondition: `ready_for_synthesis = true`.
   - Uses DB MCP to:
     - Query all citations for `model_run_ids`.
     - Compute overlaps via `normalized_key` and vector similarity.
   - Calls ADK `SynthesizerAgent` with structured citation data.
   - Writes synthesis report to Firestore.

5. `finalize` (Sequential)
   - Mark session as `completed` in Firestore.

### 8.3 Execution Model

- Primary Orchestrator HTTP handler:
  - Constructs initial `CouncilState` with `session_id` and `user_question`.
  - Invokes LangGraph graph run (sync or async).
- For long-running sessions, orchestrator can:
  - Schedule background execution (e.g., Pub/Sub-triggered) while Firestore exposes progress to clients.

---

## 9. ADK Agent Definitions

- `ResearchAgentA/B/C`:
  - ADK `LlmAgent` with:
    - Role prompts enforcing independence and citation requirements.
    - Tools: Search MCP, Google Dev MCP, Task/Calendar MCP, Database MCP.
    - Model: bound to appropriate LiteLLM route.

- `SynthesizerAgent`:
  - ADK `LlmAgent` with:
    - Input: structured citation clusters/overlaps + summaries.
    - Tools: Database MCP for additional queries if needed.

- `CoordinatorAgent` (Primary Orchestrator):
  - ADK `LlmAgent` or small non-LLM controller that:
    - Delegates to Research agents and Synthesizer.
    - Implements Coordinator/Dispatcher pattern.

---

## 10. LiteLLM Integration

- Deploy LiteLLM proxy (Cloud Run or other).
- Configure routes for each research seat and synthesizer.
- Backend and ADK agents use OpenAI-compatible client with:
  - `base_url = LITELLM_BASE_URL`
  - `api_key = LITELLM_API_KEY`

LiteLLM then routes requests to Claude, GPT-5.2, and Gemini using provider keys from env.

---

## 11. CLI Agent Interface

### 11.1 Commands

- `council new-session "<question>"`
  - Creates a new session via `/council/sessions`.
  - Optionally triggers graph execution immediately.
  - Prints `session_id`.

- `council status <session_id>`
  - Calls `/council/sessions/{sessionId}`.
  - Prints status and `[x/3 models completed]`.

- `council get-report <session_id>`
  - Calls `/council/sessions/{sessionId}/report`.
  - Prints markdown or JSON of the synthesis report.

- `council list-citations <session_id>`
  - Calls `/council/sessions/{sessionId}/citations`.
  - Prints citation list.

### 11.2 CLI–Backend Mode

- Local dev: CLI can call LangGraph directly if desired.
- Deployed mode: CLI calls the Cloud Run HTTP API.

---

## 12. HTTP API Surface

- `POST /council/sessions`
  - Body: `{ "question": string }`
  - Response: `{ "session_id": string, "status": string }`

- `GET /council/sessions/{sessionId}`
  - Response: session object with progress.

- `GET /council/sessions/{sessionId}/report`
  - Response: `{ "session_id": string, "report_markdown": string }`

- `GET /council/sessions/{sessionId}/citations`
  - Response: list of citations (Cloud SQL rows).

---

## 13. Deployment (Summary)

- Build Docker image containing backend, LangGraph, ADK, and LiteLLM client.
- Deploy backend to Cloud Run with env vars from `.env` / Secret Manager.
- Provision:
  - Firestore in Native mode in `GCP_PROJECT_ID`.
  - Cloud SQL Postgres with vector extension enabled.
- Deploy LiteLLM proxy to Cloud Run.
- Deploy MCP servers (Search, Task/Calendar, Google Dev Docs, DB MCP) to Cloud Run or other compute.
- Ensure IAM roles allow Cloud Run service account to access Firestore, Cloud SQL, and any required external APIs.

This updated spec is GCP-aware, model-specific (Claude, GPT-5.2, Gemini), classifies agents by type/pattern, and clarifies when and how the Database MCP should be used.