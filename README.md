# Multi-Agent Conclave Project

GCP-native multi-agent "Model Conclave" system.

## Demo Link
[Agent Conclave Demo](https://youtu.be/qcziDsMC8c0)

## Project Structure
- `agents/`: Microservices for individual agents (`orchestrator`, `research_a`, `research_b`, `research_c`, `synthesizer`) built with Google ADK.
- `backend/`: FastAPI application and orchestration.
- `cli/`: Typer-based CLI for interacting with the conclave.
- `frontend/`: Web interface (HTML/JS/CSS).
- `infra/`: Infrastructure-as-Code and deployment configurations.
- `mcp_servers/`: MCP servers for database, search, and other tools.
- `migrations/`: SQL migrations for Cloud SQL.
- `shared/`: Shared utilities and code across microservices.
- `tests/`: Project tests.

## Setup
1. Clone the repository.
2. Install dependencies: `poetry install` (and ensure `uv` is installed for agent microservices).
3. Configure environment: `cp .env.example .env` and update values.
4. Run locally: Execute `./run_local.sh` to start all MCP servers, agent microservices, and the backend API.
