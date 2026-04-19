# Multi-Agent Conclave Project

GCP-native multi-agent "Model Conclave" system.

## Demo Link
[Agent Conclave Demo](https://youtu.be/qcziDsMC8c0)

## Project Structure
- `backend/`: FastAPI application and LangGraph orchestration.
- `cli/`: Typer-based CLI for interacting with the conclave.
- `mcp_servers/`: MCP servers for database, search, and other tools.
- `migrations/`: SQL migrations for Cloud SQL.
- `infra/`: Infrastructure-as-Code and deployment configurations.
- `tests/`: Project tests.

## Setup
1. Clone the repository.
2. Install dependencies: `poetry install`.
3. Configure environment: `cp .env.example .env` and update values.
4. Run locally: `uvicorn backend.main:app --reload`.
