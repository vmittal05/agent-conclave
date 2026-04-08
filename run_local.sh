#!/bin/bash

# Kill any existing processes on these ports
echo "Stopping any existing processes on ports 8001-8005, 8010-8011, and 8080..."
fuser -k 8001/tcp 8002/tcp 8003/tcp 8004/tcp 8005/tcp 8010/tcp 8011/tcp 8080/tcp 2>/dev/null

# Set common environment variables
export GCP_PROJECT_ID=$(gcloud config get-value project)
export GOOGLE_CLOUD_PROJECT=$GCP_PROJECT_ID
export GOOGLE_CLOUD_LOCATION="us-central1"
export GOOGLE_GENAI_USE_VERTEXAI="True"

echo "Starting Database MCP Server on port 8010..."
export PORT=8010
poetry run python mcp_servers/db_server.py &
DB_MCP_PID=$!

echo "Starting Search MCP Server on port 8011..."
export PORT=8011
poetry run python mcp_servers/search_server.py &
SEARCH_MCP_PID=$!

# Update MCP URLs for agents
export MCP_DB_SERVER_URL=http://localhost:8010
export MCP_SEARCH_SERVER_URL=http://localhost:8011

# IMPORTANT: We run adk_app.py from the AGENTS directory so the loader finds the subfolders correctly.
# Each command starts a service containing ONE agent.

echo "Starting Research Agent A on port 8001..."
pushd agents
uv run adk_app.py --host 0.0.0.0 --port 8001 --a2a research_a &
RESEARCH_A_PID=$!
popd

echo "Starting Research Agent B on port 8002..."
pushd agents
uv run adk_app.py --host 0.0.0.0 --port 8002 --a2a research_b &
RESEARCH_B_PID=$!
popd

echo "Starting Research Agent C on port 8003..."
pushd agents
uv run adk_app.py --host 0.0.0.0 --port 8003 --a2a research_c &
RESEARCH_C_PID=$!
popd

echo "Starting Synthesizer Agent on port 8004..."
pushd agents
uv run adk_app.py --host 0.0.0.0 --port 8004 --a2a synthesizer &
SYNTHESIZER_PID=$!
popd

# Environment variables for Orchestrator to find sub-agents
# Note: The app name in the URL matches the folder name
export RESEARCH_A_AGENT_CARD_URL=http://localhost:8001/a2a/research_a/.well-known/agent-card.json
export RESEARCH_B_AGENT_CARD_URL=http://localhost:8002/a2a/research_b/.well-known/agent-card.json
export RESEARCH_C_AGENT_CARD_URL=http://localhost:8003/a2a/research_c/.well-known/agent-card.json
export SYNTHESIZER_AGENT_CARD_URL=http://localhost:8004/a2a/synthesizer/.well-known/agent-card.json

echo "Starting Orchestrator Agent on port 8005..."
pushd agents
uv run adk_app.py --host 0.0.0.0 --port 8005 orchestrator &
ORCHESTRATOR_PID=$!
popd

echo "Waiting 25 seconds for all services to initialize..."
sleep 25

echo "Starting Backend API on port 8080..."
export ORCHESTRATOR_URL=http://localhost:8005
poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8080 &
BACKEND_PID=$!

echo "All agents, MCP servers, and backend started!"
echo "Backend API: http://localhost:8080"
echo "Press Ctrl+C to stop all processes."

trap "kill $DB_MCP_PID $SEARCH_MCP_PID $RESEARCH_A_PID $RESEARCH_B_PID $RESEARCH_C_PID $SYNTHESIZER_PID $ORCHESTRATOR_PID $BACKEND_PID; exit" INT
wait
