#!/bin/bash

# Exit on error
set -e

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_ACCOUNT="conclave-runner@$PROJECT_ID.iam.gserviceaccount.com"

echo "Using Project: $PROJECT_ID"
echo "Using Region: $REGION"

# --- 1. Tool Servers (MCP) ---

echo "Deploying Database MCP..."
gcloud run deploy conclave-mcp-db \
    --source . \
    --command "python" \
    --args "mcp_servers/db_server.py" \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,CLOUD_SQL_INSTANCE_CONNECTION_NAME=$PROJECT_ID:$REGION:postgres,CLOUD_SQL_DB_NAME=conclave_db,CLOUD_SQL_DB_USER=postgres" \
    --set-secrets "CLOUD_SQL_DB_PASSWORD=CLOUD_SQL_DB_PASSWORD:latest" \
    --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
DB_MCP_URL=$(gcloud run services describe conclave-mcp-db --region $REGION --format='value(status.url)')

echo "Deploying Search MCP..."
gcloud run deploy conclave-mcp-search \
    --source . \
    --command "python" \
    --args "mcp_servers/search_server.py" \
    --set-secrets "TAVILY_API_KEY=TAVILY_API_KEY:latest" \
    --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
SEARCH_MCP_URL=$(gcloud run services describe conclave-mcp-search --region $REGION --format='value(status.url)')

# --- 2. Research & Synthesizer Agents ---

COMMON_AGENT_VARS="MCP_DB_SERVER_URL=$DB_MCP_URL,MCP_SEARCH_SERVER_URL=$SEARCH_MCP_URL,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_GENAI_USE_VERTEXAI=True"

echo "Deploying Research Agent A..."
gcloud run deploy conclave-agent-a --source agents/research_a --set-env-vars "$COMMON_AGENT_VARS" --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
AGENT_A_URL=$(gcloud run services describe conclave-agent-a --region $REGION --format='value(status.url)')

echo "Deploying Research Agent B..."
gcloud run deploy conclave-agent-b --source agents/research_b --set-env-vars "$COMMON_AGENT_VARS" --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
AGENT_B_URL=$(gcloud run services describe conclave-agent-b --region $REGION --format='value(status.url)')

echo "Deploying Research Agent C..."
gcloud run deploy conclave-agent-c --source agents/research_c --set-env-vars "$COMMON_AGENT_VARS" --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
AGENT_C_URL=$(gcloud run services describe conclave-agent-c --region $REGION --format='value(status.url)')

echo "Deploying Synthesizer Agent..."
gcloud run deploy conclave-agent-synth --source agents/synthesizer --set-env-vars "$COMMON_AGENT_VARS" --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
AGENT_SYNTH_URL=$(gcloud run services describe conclave-agent-synth --region $REGION --format='value(status.url)')

# --- 3. Orchestrator & Backend ---

echo "Deploying Orchestrator..."
gcloud run deploy conclave-orchestrator \
    --source agents/orchestrator \
    --set-env-vars "RESEARCH_A_AGENT_CARD_URL=$AGENT_A_URL/a2a/agent/.well-known/agent-card.json" \
    --set-env-vars "RESEARCH_B_AGENT_CARD_URL=$AGENT_B_URL/a2a/agent/.well-known/agent-card.json" \
    --set-env-vars "RESEARCH_C_AGENT_CARD_URL=$AGENT_C_URL/a2a/agent/.well-known/agent-card.json" \
    --set-env-vars "SYNTHESIZER_AGENT_CARD_URL=$AGENT_SYNTH_URL/a2a/agent/.well-known/agent-card.json" \
    --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
ORCHESTRATOR_URL=$(gcloud run services describe conclave-orchestrator --region $REGION --format='value(status.url)')

echo "Deploying Backend Gateway..."
gcloud run deploy conclave-backend \
    --source . \
    --set-env-vars "ORCHESTRATOR_URL=$ORCHESTRATOR_URL,GCP_PROJECT_ID=$PROJECT_ID" \
    --region $REGION --service-account $SERVICE_ACCOUNT --allow-unauthenticated

echo "--------------------------------------------------------"
echo "DEPLOYMENT COMPLETE!"
echo "Backend URL: $(gcloud run services describe conclave-backend --region $REGION --format='value(status.url)')"
echo "--------------------------------------------------------"
