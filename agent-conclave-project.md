# Multi-Agent Conclave Project – GCP Implementation Spec

## 1. Purpose

This document specifies a GCP-native multi-agent "Model Conclave" system that follows a distributed microservices architecture using the Google Agent Development Kit (ADK). The system provides deep, multi-perspective research by orchestrating independent agents that perform live web research, data visualization, and synthesize findings into a grounded consensus report.

Pattern: **Main Orchestrator (Router + Discovery) → Parallel Research Conclave (3) → Visualization Specialist → Synthesizer Microservice**, using Tavily Search, Cloud SQL (pgvector), and GCS, orchestrated via ADK A2A protocol.

---

## 2. High-Level Architecture

### 2.1 Microservices (Cloud Run)
The system is decomposed into **12 independent services**:
- **Backend API**: The gateway and streaming user interface (FastAPI + Vanilla JS).
- **Conclave Orchestrator**: The "Brain". Handles complexity routing (Fast-Path), dynamic agent discovery, and pipeline management.
- **Agent Registry**: The control plane where agents self-register their capabilities.
- **Research Agents (A, B, C)**: Specialized agents performing parallel research through different "Lenses" (**Expert**, **Analytical**, and **Technical**).
- **Visualization Agent**: A specialist that generates charts (Matplotlib) and persists them to GCS.
- **Synthesizer Agent**: An advanced reasoning agent that performs Vector RAG to generate the final report.
- **Database MCP**: Mediates access to Cloud SQL (Postgres + pgvector) and Firestore.
- **Search MCP**: Provides live web search via Tavily API.
- **Code Interpreter MCP**: Sandboxed Python environment for data analysis.
- **File System MCP**: Google Cloud Storage interface for persistent asset management.

### 2.2 Orchestration
- **Google ADK**: All agents are built using the `google.adk` framework.
- **Intelligence Routing**: A `RouterAgent` evaluates query complexity to decide between a "Fast-Path" (direct answer) or "Deep-Path" (full conclave).
- **Dynamic Discovery**: Orchestrator uses a `DiscoveryAgent` to locate researchers at runtime via the Registry.
- **Parallel Execution**: Research is executed in parallel using ADK `ParallelAgent` to reduce latency by ~60%.

---

## 3. Data & Storage Model

### 3.1 AlloyDB (Primary) / Cloud SQL (Current)
- **Database Engine**: **AlloyDB for PostgreSQL** is the primary choice for the production architecture due to its superior performance for analytical and vector workloads.
- **Cost Disclaimer**: **Cloud SQL (Postgres + pgvector)** is currently utilized for the prototype and hackathon phase to minimize costs due to limited cloud credits.
- **Schema**:
    - **model_runs**: Tracks each agent's execution for a specific session.
    - **citations**: Stores granular findings with **768-dimensional embeddings** (`text-embedding-004`) for semantic retrieval.
- **Vector Search**: Enabled via cosine distance (`<=>`) for grounded synthesis.

### 3.2 Object Storage (GCS)
- **conclave-assets-[PROJECT_ID]**: A publicly reachable bucket for storing generated visualizations and large datasets.

### 3.3 Firestore (Session State)
- Stores global session metadata, user questions, and final report markdown for persistence and audit trails.

---

## 4. Implementation Details

### 4.1 Research & Analysis
- **Research Agents**: Focus purely on gathering high-quality web citations and recording them in the vector database.
- **Visualization Agent**: Triggered after research; analyzes gathered data, executes Python code to generate charts, and uploads binary PNGs to GCS.

### 4.2 Synthesis & Grounding
- **Synthesizer Agent**: Uses `gemini-2.5-pro` for high-quality reasoning.
- **Vector RAG**: Performs semantic lookups in the citations database to find evidence for specific claims.
- **Real-time Streaming**: Backend streams markdown chunks to the UI as they are generated for a responsive UX.

---

## 5. Deployment & Infrastructure

### 5.1 Environment Configuration
- `GOOGLE_CLOUD_LOCATION`: Set to `global` to access the latest Gemini 3.x models.
- `AGENT_REGISTRY_URL`: Central endpoint for dynamic service discovery.
- `PUBLIC_AGENT_URL`: Required for agents to register reachable endpoints in Cloud Run.

### 5.2 Observability
- **LangSmith**: Integrated across all 12 microservices for full-chain tracing, latency monitoring, and prompt debugging.

---
