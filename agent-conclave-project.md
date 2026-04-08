# Multi-Agent Conclave Project – GCP Implementation Spec

## 1. Purpose

This document specifies a GCP-native multi-agent "Model Conclave" system that follows a distributed microservices architecture using the Google Agent Development Kit (ADK). The system provides deep, multi-perspective research by orchestrating independent agents that perform live web research and synthesize findings into a consensus report.

Pattern: **Main Orchestrator → Distributed Research Microservices (3) → Synthesizer Microservice**, using Tavily Search and Cloud SQL, orchestrated via ADK A2A (Agent-to-Agent) protocol.

---

## 2. High-Level Architecture

### 2.1 Microservices (Cloud Run)
The system is decomposed into **8 independent services**:
- **Backend API**: The gateway and user interface (FastAPI + Vanilla JS).
- **Conclave Orchestrator**: The workflow manager that handles the 4-stage research lifecycle.
- **Research Agents (A, B, C)**: Specialized agents performing parallel/sequential research.
- **Synthesizer Agent**: An advanced reasoning agent that generates the final report.
- **Database MCP**: A tool server mediating access to Cloud SQL and Firestore.
- **Search MCP**: A tool server providing live web search via Tavily.

### 2.2 Orchestration
- **Google ADK (Agent Development Kit)**: All agents are built using the `google.adk` framework.
- **A2A Protocol**: Inter-agent communication is handled via the Agent-to-Agent protocol over authenticated HTTP.
- **Sequential Research**: Research is executed sequentially to ensure stability and stay within Vertex AI quota limits.

---

## 3. Data & Storage Model

### 3.1 Cloud SQL (Postgres + pgvector)
- **model_runs**: Tracks each agent's execution for a specific session.
- **citations**: Stores granular research findings (URL, snippet, title) with foreign keys to model runs.
- **Vector Search**: Enabled via `pgvector` for future citation clustering and deduplication.

### 3.2 Firestore (Session State)
- Stores global session metadata, user questions, and final report markdown.
- Managed by the Backend API and monitored via the UI.

---

## 4. Implementation Details

### 4.1 Research Phase (Stages 1-3)
Each research agent (ResearchAgentA, B, and C):
- Receives a unified prompt: `SESSION_ID: [UUID] | QUESTION: [Text]`.
- Uses the **Search MCP** to fetch live results from the web.
- Uses the **record_citations_batch** tool to save all findings in a single database transaction for efficiency.
- Operates independently to ensure diverse perspectives (Claude, GPT, and Gemini seats).

### 4.2 Synthesis Phase (Stage 4)
The Synthesizer Agent:
- Extracts the `SESSION_ID` from the orchestrator prompt.
- Calls the **Database MCP** (`get_session_citations`) to retrieve all citations gathered in previous stages.
- Performs comparative analysis to identify consensus, disagreements, and unique discoveries.
- Generates a markdown report strictly following the `@model-council-sim.md` schema.

---

## 5. Deployment & Infrastructure

### 5.1 Environment Configuration (.env)
- `GCP_PROJECT_ID`: Target project (`apac-h2s`).
- `CLOUD_SQL_INSTANCE_CONNECTION_NAME`: The Unix socket/connection string for Postgres.
- `TAVILY_API_KEY`: Credentials for live web research.
- `ORCHESTRATOR_URL`: The entry point for the agent network.

### 5.2 IAM Roles
The `conclave-runner` service account requires:
- `roles/datastore.user`
- `roles/cloudsql.client`
- `roles/aiplatform.user`
- `roles/secretmanager.secretAccessor`
- `roles/serviceusage.serviceUsageConsumer`

---