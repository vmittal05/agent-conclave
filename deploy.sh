#!/bin/bash

# Exit on error
set -e

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_ACCOUNT="conclave-runner@$PROJECT_ID.iam.gserviceaccount.com"

echo "Using Project: $PROJECT_ID"
echo "Using Region: $REGION"

# --- 1. Tool Servers (MCP) & Registry ---

echo "Deploying Registry Service..."
gcloud run deploy conclave-registry \
    --source . \
    --command "python" \
    --args "mcp_servers/registry_server.py" \
    --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
REGISTRY_URL=$(gcloud run services describe conclave-registry --region $REGION --format='value(status.url)')

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

echo "Deploying Code Interpreter MCP..."
gcloud run deploy conclave-mcp-code \
    --source . \
    --command "python" \
    --args "mcp_servers/code_server.py" \
    --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
CODE_MCP_URL=$(gcloud run services describe conclave-mcp-code --region $REGION --format='value(status.url)')

echo "Deploying File System MCP..."
gcloud run deploy conclave-mcp-fs \
    --source . \
    --command "python" \
    --args "mcp_servers/fs_server.py" \
    --set-env-vars "GCS_BUCKET_NAME=conclave-assets-$PROJECT_ID" \
    --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
FS_MCP_URL=$(gcloud run services describe conclave-mcp-fs --region $REGION --format='value(status.url)')

# --- 2. Research & Synthesizer Agents ---

LANGSMITH_VARS="LANGCHAIN_TRACING_V2=true,LANGCHAIN_PROJECT=agent-conclave"
COMMON_AGENT_VARS="AGENT_REGISTRY_URL=$REGISTRY_URL,MCP_DB_SERVER_URL=$DB_MCP_URL,MCP_SEARCH_SERVER_URL=$SEARCH_MCP_URL,MCP_CODE_SERVER_URL=$CODE_MCP_URL,MCP_FS_SERVER_URL=$FS_MCP_URL,GCP_PROJECT_ID=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GOOGLE_GENAI_USE_VERTEXAI=True,$LANGSMITH_VARS"

deploy_agent() {
    local name=$1
    local source=$2
    echo "Deploying $name..."
    gcloud run deploy $name --source $source \
        --set-env-vars "$COMMON_AGENT_VARS" \
        --set-secrets "LANGCHAIN_API_KEY=LANGCHAIN_API_KEY:latest" \
        --region $REGION --service-account $SERVICE_ACCOUNT --no-allow-unauthenticated
    local url=$(gcloud run services describe $name --region $REGION --format='value(status.url)')
    echo "Updating $name with PUBLIC_AGENT_URL=$url"
    gcloud run services update $name --set-env-vars "PUBLIC_AGENT_URL=$url" --region $REGION
    echo $url
}

AGENT_A_URL=$(deploy_agent "conclave-agent-a" "agents/research_a")
AGENT_B_URL=$(deploy_agent "conclave-agent-b" "agents/research_b")
AGENT_C_URL=$(deploy_agent "conclave-agent-c" "agents/research_c")
AGENT_SYNTH_URL=$(deploy_agent "conclave-agent-synth" "agents/synthesizer")

# --- 3. Orchestrator & Backend ---

echo "Deploying Orchestrator..."
gcloud run deploy conclave-orchestrator \
    --source agents/orchestrator \
    --set-env-vars "AGENT_REGISTRY_URL=$REGISTRY_URL,SYNTHESIZER_AGENT_CARD_URL=$AGENT_SYNTH_URL/a2a/agent/.well-known/agent-card.json" \
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
