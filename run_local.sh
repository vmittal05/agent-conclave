#!/bin/bash

# Kill any existing processes on these ports
echo "Stopping any existing processes on ports 8001-8005 and 8080..."
lsof -ti:8001,8002,8003,8004,8005,8080 | xargs kill -9 2>/dev/null

# Set common environment variables for local development
export GCP_PROJECT_ID=$(gcloud config get-value project)
export GOOGLE_CLOUD_PROJECT=$GCP_PROJECT_ID
export GOOGLE_CLOUD_LOCATION="us-central1"
export GOOGLE_GENAI_USE_VERTEXAI="True"

echo "Starting Research Agent A on port 8001..."
pushd agents/research_a
uv run adk_app.py --host 0.0.0.0 --port 8001 --a2a . &
RESEARCH_A_PID=$!
popd

echo "Starting Research Agent B on port 8002..."
pushd agents/research_b
uv run adk_app.py --host 0.0.0.0 --port 8002 --a2a . &
RESEARCH_B_PID=$!
popd

echo "Starting Research Agent C on port 8003..."
pushd agents/research_c
uv run adk_app.py --host 0.0.0.0 --port 8003 --a2a . &
RESEARCH_C_PID=$!
popd

echo "Starting Synthesizer Agent on port 8004..."
pushd agents/synthesizer
uv run adk_app.py --host 0.0.0.0 --port 8004 --a2a . &
SYNTHESIZER_PID=$!
popd

export RESEARCH_A_AGENT_CARD_URL=http://localhost:8001/a2a/agent/.well-known/agent-card.json
export RESEARCH_B_AGENT_CARD_URL=http://localhost:8002/a2a/agent/.well-known/agent-card.json
export RESEARCH_C_AGENT_CARD_URL=http://localhost:8003/a2a/agent/.well-known/agent-card.json
export SYNTHESIZER_AGENT_CARD_URL=http://localhost:8004/a2a/agent/.well-known/agent-card.json

echo "Starting Orchestrator Agent on port 8005..."
pushd agents/orchestrator
uv run adk_app.py --host 0.0.0.0 --port 8005 . &
ORCHESTRATOR_PID=$!
popd

# Wait a bit for them to start up
sleep 5

echo "Starting Backend API on port 8080..."
export ORCHESTRATOR_URL=http://localhost:8005
# Note: Original backend used poetry, but let's assume environment is ready or use poetry run
poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8080 &
BACKEND_PID=$!

echo "All agents and backend started!"
echo "Research A: http://localhost:8001"
echo "Research B: http://localhost:8002"
echo "Research C: http://localhost:8003"
echo "Synthesizer: http://localhost:8004"
echo "Orchestrator: http://localhost:8005"
echo "Backend API: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop all processes."

# Wait for all processes
trap "kill $RESEARCH_A_PID $RESEARCH_B_PID $RESEARCH_C_PID $SYNTHESIZER_PID $ORCHESTRATOR_PID $BACKEND_PID; exit" INT
wait
