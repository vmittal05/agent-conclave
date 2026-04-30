# 🏛️ Model Conclave

**Model Conclave** is a production-grade, GCP-native multi-agent intelligence mesh designed to transform complex research questions into grounded, visualized reports. Built on the **Google Agent Development Kit (ADK)**, it orchestrates a "Council of Experts" to provide deep, multi-perspective analysis with full semantic grounding.

## 🚀 Key Features

*   **Intelligence Routing (Fast-Path)**: Instantly classifies queries. Simple questions receive direct answers in seconds, while complex ones trigger the full multi-agent research pipeline.
*   **Parallel Research Conclave**: Deploys three specialized personas (**Expert**, **Analytical**, and **Technical**) simultaneously to scour the web, reducing total latency by ~60%.
*   **Dynamic Agent Discovery**: Uses a central **Registry Service** for runtime service discovery, allowing the conclave to scale horizontally with new specialized agents.
*   **Automated Visualization Pipeline**: A dedicated **Visualization Agent** uses a sandboxed **Code Interpreter** to generate trend charts and comparisons, persisted to Google Cloud Storage.
*   **Semantic Grounding (Vector RAG)**: findings are stored as 768-dim vectors in **Cloud SQL (pgvector)**. The final report is synthesized using semantic search to ensure 100% data-driven citations.
*   **Full-Chain Observability**: Deep integration with **LangSmith** for real-time tracing of every agent interaction, tool call, and token cost.

## 🏗️ Architecture

The system operates as a distributed mesh of **12 independent microservices** on Google Cloud Run:

### Agents (Reasoning)
- `orchestrator`: The central manager handling routing and discovery.
- `research_a/b/c`: Specialists for Strategy, Data, and Technical implementations.
- `viz_agent`: Specialist for data analysis and Matplotlib chart generation.
- `synthesizer`: Advanced reasoning agent that performs the final RAG-based report generation.

### MCP Servers (Tooling)
- `conclave-registry`: The control plane for agent registration and lookup.
- `conclave-mcp-db`: Interface for Cloud SQL (pgvector) and Firestore.
- `conclave-mcp-search`: Live web search integration via Tavily.
- `conclave-mcp-code`: Sandboxed Python environment for analytical execution.
- `conclave-mcp-fs`: Google Cloud Storage interface for binary assets.

## 📂 Project Structure

```text
├── agents/              # ADK Agent Microservices (A, B, C, Viz, Orchestrator, Synth)
├── backend/             # FastAPI Gateway & Real-time SSE Streamer
├── frontend/            # Vanilla JS Web UI with Reasoning Trace panel
├── mcp_servers/         # Tool servers (DB, Search, Code, File System, Registry)
├── shared/              # Cross-service OIDC Auth and A2A utilities
├── infra/               # Cloud Build CI/CD and Deployment specs
├── deploy.sh            # Master rollout script for all 12 services
└── run_local.sh         # Local development environment starter
```

## 🛠️ Local Setup

### Prerequisites
- Python 3.11+
- [Poetry](https://python-poetry.org/)
- [uv](https://github.com/astral-sh/uv) (for high-speed agent execution)
- Google Cloud SDK (authenticated)

### Installation
1.  **Clone & Install**:
    ```bash
    git clone https://github.com/your-repo/agent-conclave.git
    cd agent-conclave
    poetry install
    ```
2.  **Environment**:
    ```bash
    cp .env.example .env
    # Update with your GCP_PROJECT_ID and TAVILY_API_KEY
    ```
3.  **Run Conclave**:
    ```bash
    ./run_local.sh
    ```
    Open `http://localhost:8080` to access the UI.

## ☁️ Cloud Deployment

The project is optimized for **Google Cloud Run**.

1.  **Grant Permissions**: Ensure your service account has `roles/run.invoker`, `roles/aiplatform.user`, and `roles/storage.admin`.
2.  **Rollout**:
    ```bash
    chmod +x deploy.sh
    ./deploy.sh
    ```

## 📈 Observability

Traces are automatically sent to LangSmith if the `LANGCHAIN_API_KEY` is provided in Secret Manager or your `.env` file. You can monitor agent "thought" trees and tool latencies at [smith.langchain.com](https://smith.langchain.com).

---
Built with ❤️ using Google ADK and Vertex AI.
