# Deployment Guide: Model Conclave on Cloud Run

This guide explains how to deploy the **Model Conclave** distributed system to Google Cloud Run. This architecture follows the Google ADK microservices pattern, where each agent and tool is an independent, scalable service.

## 1. Architecture Overview
The system consists of **8 independent services**:
*   **Backend API** (Gateway & UI)
*   **Orchestrator Agent** (Workflow Manager)
*   **Research Agents A, B, C** (Parallel researchers)
*   **Synthesizer Agent** (Report generator)
*   **Database MCP** (Postgres/Firestore tool)
*   **Search MCP** (Tavily/Google Search tool)

---

## 2. Prerequisites & Infrastructure
Before deploying, ensure the following are set up in your GCP project (`apac-h2s`):

### Enable APIs
```bash
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com \
    firestore.googleapis.com \
    sqladmin.googleapis.com
```

### Database & IAM
1.  **Firestore**: Ensure it is in **Native Mode**.
2.  **Cloud SQL**: PostgreSQL 15 instance named `postgres` with database `conclave_db`.
3.  **Service Account**: `conclave-runner` with roles:
    *   `roles/datastore.user` (Firestore)
    *   `roles/cloudsql.client` (Cloud SQL)
    *   `roles/aiplatform.user` (Vertex AI)
    *   `roles/secretmanager.secretAccessor` (Secrets)

---

## 3. Deployment Steps

### Step 1: Deploy MCP Servers
Deploy the tool servers first so agents can connect to them.

**Database MCP:**
```bash
gcloud run deploy conclave-mcp-db \
    --source . \
    --command "python" \
    --args "mcp_servers/db_server.py" \
    --set-env-vars "CLOUD_SQL_INSTANCE_CONNECTION_NAME=apac-h2s:us-central1:postgres,CLOUD_SQL_DB_NAME=conclave_db,CLOUD_SQL_DB_USER=postgres" \
    --set-secrets "CLOUD_SQL_DB_PASSWORD=CLOUD_SQL_DB_PASSWORD:latest" \
    --region us-central1 --no-allow-unauthenticated
```

**Search MCP:**
```bash
gcloud run deploy conclave-mcp-search \
    --source . \
    --command "python" \
    --args "mcp_servers/search_server.py" \
    --set-secrets "TAVILY_API_KEY=TAVILY_API_KEY:latest" \
    --region us-central1 --no-allow-unauthenticated
```

### Step 2: Deploy Research & Synthesizer Agents
Deploy the five ADK microservices. Note down the URLs generated for each.

```bash
# Research Agent A
gcloud run deploy conclave-agent-a --source agents/research_a --region us-central1 --no-allow-unauthenticated

# Research Agent B
gcloud run deploy conclave-agent-b --source agents/research_b --region us-central1 --no-allow-unauthenticated

# Research Agent C
gcloud run deploy conclave-agent-c --source agents/research_c --region us-central1 --no-allow-unauthenticated

# Synthesizer Agent
gcloud run deploy conclave-agent-synth --source agents/synthesizer --region us-central1 --no-allow-unauthenticated
```

### Step 3: Deploy Orchestrator
The Orchestrator needs the URLs of the sub-agents. Replace `<URL>` with the actual Cloud Run URLs from Step 2.

```bash
gcloud run deploy conclave-orchestrator \
    --source agents/orchestrator \
    --set-env-vars "RESEARCH_A_AGENT_CARD_URL=https://<AGENT_A_URL>/a2a/agent/.well-known/agent-card.json" \
    --set-env-vars "RESEARCH_B_AGENT_CARD_URL=https://<AGENT_B_URL>/a2a/agent/.well-known/agent-card.json" \
    --set-env-vars "RESEARCH_C_AGENT_CARD_URL=https://<AGENT_C_URL>/a2a/agent/.well-known/agent-card.json" \
    --set-env-vars "SYNTHESIZER_AGENT_CARD_URL=https://<AGENT_SYNTH_URL>/a2a/agent/.well-known/agent-card.json" \
    --region us-central1 --no-allow-unauthenticated
```

### Step 4: Deploy Backend API (Main Entry Point)
Finally, deploy the main application that serves the UI.

```bash
gcloud run deploy conclave-backend \
    --source . \
    --set-env-vars "ORCHESTRATOR_URL=https://<ORCHESTRATOR_URL>" \
    --set-env-vars "GCP_PROJECT_ID=apac-h2s" \
    --region us-central1 --allow-unauthenticated
```

---

## 4. Connecting the Distributed Services
For the services to talk to each other securely, ensure all services are using the `conclave-runner` service account:
`--service-account conclave-runner@apac-h2s.iam.gserviceaccount.com`

### Environment Variable Mapping
The following table summarizes the critical links:

| Target Service | Environment Variable | Points To |
| :--- | :--- | :--- |
| **Orchestrator** | `RESEARCH_A_AGENT_CARD_URL` | Agent A URL + `/a2a/agent/.well-known/agent-card.json` |
| **Orchestrator** | `SYNTHESIZER_AGENT_CARD_URL` | Synth Agent URL + `/a2a/agent/.well-known/agent-card.json` |
| **Backend** | `ORCHESTRATOR_URL` | The root URL of the Orchestrator Cloud Run service |
| **All Agents** | `MCP_DB_SERVER_URL` | The Cloud Run URL of `conclave-mcp-db` |
| **All Agents** | `MCP_SEARCH_SERVER_URL` | The Cloud Run URL of `conclave-mcp-search` |

---

## 5. Testing
1. Open the URL of the `conclave-backend` service in your browser.
2. Enter a research query.
3. Monitor the **Council Activity Log** to see real-time pings from the distributed Cloud Run services.
4. Verify results are saved in the Cloud SQL `citations` table.
