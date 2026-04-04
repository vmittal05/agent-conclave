# Multi-Agent Conclave – Deployment and Testing Guide

This document explains how to deploy and test the Multi-Agent Conclave project locally and on Google Cloud Platform.

## 1. Local Development and Testing

### Prerequisites
- Python 3.11+
- Poetry (`pip install poetry`)
- gcloud CLI (`gcloud components install gcloud`)
- [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/connect-auth-proxy) (for local DB access)
- [Firestore Emulator](https://cloud.google.com/firestore/docs/emulator) (optional, or use a real project)

### Setup
1. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Update values in .env for your GCP project and LLM routes
   ```

2. **Install Dependencies**:
   ```bash
   poetry install
   ```

3. **Database Setup**:
   - Run the initial migration (`migrations/001_initial_schema.sql`) on your Postgres instance.

4. **Run MCP Servers (Local)**:
   - Run Search Server: `python mcp/search_server.py` (Port 8001)
   - Run Database Server: `python mcp/db_server.py` (Port 8004)

5. **Run Backend API**:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
   ```

## 2. GCP Deployment (Cloud Run)

### Using Cloud Build
1. **Activate APIs**:
   ```bash
   gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com
   ```

2. **Deploy using Cloud Build**:
   ```bash
   gcloud builds submit --config infra/cloudbuild.yaml
   ```

### Post-Deployment Check
1. Go to **Cloud Run** console.
2. Verify the `conclave-backend` service is active.
3. Grant the service account the required IAM roles as described in Phase 2.

## 3. Testing the API

You can test the API using `curl` or tools like Postman.

### A. Create a Research Session
```bash
curl -X POST "https://[BACKEND_URL]/council/sessions" \
     -H "Content-Type: application/json" \
     -d '{"question": "How to implement a vector search in Cloud SQL using pgvector?"}'
```
*   **Response**: `{"session_id": "...", "status": "pending", "created_at": "..."}`

### B. Track Status
```bash
curl -X GET "https://[BACKEND_URL]/council/sessions/[SESSION_ID]"
```
*   **Response**: Shows `"status": "in_progress"` or `"status": "completed"`.

### C. Retrieve Synthesis Report
```bash
curl -X GET "https://[BACKEND_URL]/council/sessions/[SESSION_ID]/report"
```
*   **Response**: Returns the Markdown synthesis report once the status is `completed`.

---

## 4. Verification Steps for Synthesis
1. **Parallel Execution**: Check logs to see `--- RESEARCHING WITH AGENT A/B/C ---` running concurrently.
2. **Citations**: Query the `citations` table to ensure 30+ sources were gathered per model.
3. **Synthesis**: Verify the final report contains a section for consensus and unique insights.
