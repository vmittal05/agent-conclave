import os
import httpx
import asyncio
import logging
from typing import List, Dict, Any, Optional
from google import genai
from google.adk import Agent
from google.genai import types as genai_types
from google.adk.events import Event
from langsmith import traceable
from dotenv import load_dotenv

from authenticated_httpx import create_authenticated_client

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP Server URLs
SEARCH_URL = os.getenv("MCP_SEARCH_SERVER_URL", "http://localhost:8011")
DB_URL = os.getenv("MCP_DB_SERVER_URL", "http://localhost:8010")
CODE_URL = os.getenv("MCP_CODE_SERVER_URL", "http://localhost:8013")
FS_URL = os.getenv("MCP_FS_SERVER_URL", "http://localhost:8014")

# Initialize GenAI client using Vertex AI (uses ADC in Cloud Shell/Cloud Run)
genai_client = genai.Client(
    vertexai=True, 
    project=os.getenv("GCP_PROJECT_ID"), 
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
)

# --- Common Research Tools ---

@traceable(run_type="tool", name="AgentC_WebSearch")
async def search_web(query: str) -> List[Dict[str, Any]]:
    """Search the web for academic and general sources with authentication."""
    try:
        # Use authenticated client for Cloud Run service-to-service
        async with create_authenticated_client(SEARCH_URL) as client:
            response = await client.post(f"{SEARCH_URL}/tools/search", json={"query": query}, timeout=30.0)
            response.raise_for_status()
            return response.json().get("results", [])
    except Exception as e:
        logger.error(f"Search MCP Error: {e}")
        return []

@traceable(run_type="tool", name="AgentC_GCPDocs")
async def search_gcp_docs(query: str) -> List[Dict[str, Any]]:
    """Search Google Cloud Platform and developer documentation."""
    scoped_query = f"site:cloud.google.com {query}"
    return await search_web(scoped_query)

@traceable(run_type="tool", name="AgentC_ExecutePython")
async def execute_python(code: str) -> Dict[str, Any]:
    """Execute Python code for data analysis or generating charts. Returns stdout/stderr."""
    try:
        async with create_authenticated_client(CODE_URL) as client:
            response = await client.post(f"{CODE_URL}/tools/execute_python", json={"code": code}, timeout=60.0)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Code MCP Error: {e}")
        return {"error": str(e)}

@traceable(run_type="tool", name="AgentC_GCSWrite")
async def gcs_write(file_path: str, content: str, content_type: str = "text/plain") -> Dict[str, Any]:
    """Write data or generated images to the cloud file system."""
    try:
        async with create_authenticated_client(FS_URL) as client:
            response = await client.post(f"{FS_URL}/tools/gcs_write", json={
                "file_path": file_path,
                "content": content,
                "content_type": content_type
            })
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"FS MCP Error: {e}")
        return {"error": str(e)}

@traceable(run_type="tool", name="AgentC_RecordCitations")
async def record_citations_batch(
    tool_context: Any,
    session_id: str,
    citations: List[Dict[str, str]]
) -> str:
    """Record multiple citations at once to the database with authentication."""
    if os.getenv("MOCK_MODE") == "true":
        return f"[MOCK] Recorded {len(citations)} citations for session {session_id}."

    db_session_id = session_id.strip()
    agent_name = "ResearchAgentC"
    model_id = "gemini-2.5-flash"

    try:
        # 1. Generate embeddings for all snippets first
        snippets = [cit.get("snippet") or cit.get("content") or "" for cit in citations]
        embeddings = []
        if snippets:
            embed_res = genai_client.models.embed_content(
                model="text-embedding-004",
                contents=snippets,
                config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
            )
            embeddings = [e.values for e in embed_res.embeddings]

        # Use authenticated client for Cloud Run service-to-service
        async with create_authenticated_client(DB_URL) as client:
            # 2. Ensure model_run exists
            sql_check = "SELECT id FROM model_runs WHERE session_id = :session_id AND agent_name = :agent_name LIMIT 1"
            res_check = await client.post(f"{DB_URL}/tools/sql_query", json={
                "sql": sql_check, 
                "params": {"session_id": db_session_id, "agent_name": agent_name}
            })
            res_check.raise_for_status()
            rows = res_check.json().get("results", [])

            if rows:
                model_run_id = rows[0]["id"]
            else:
                sql_ins = "INSERT INTO model_runs (session_id, agent_name, model_id) VALUES (:session_id, :agent_name, :model_id) RETURNING id"
                res_ins = await client.post(f"{DB_URL}/tools/sql_query", json={
                    "sql": sql_ins,
                    "params": {"session_id": db_session_id, "agent_name": agent_name, "model_id": model_id}
                })
                res_ins.raise_for_status()
                model_run_id = res_ins.json()["results"][0]["id"]

            # 3. Record all citations in the batch with embeddings
            count = 0
            for i, cit in enumerate(citations):
                sql_cit = """
                    INSERT INTO citations (model_run_id, source_url, source_type, title, snippet, embedding)
                    VALUES (:model_run_id, :source_url, :source_type, :title, :snippet, :embedding)
                """
                params_cit = {
                    "model_run_id": model_run_id,
                    "source_url": cit.get("source_url") or cit.get("url"),
                    "source_type": cit.get("source_type", "web"),
                    "title": cit.get("title", "No Title"),
                    "snippet": cit.get("snippet") or cit.get("content"),
                    "embedding": str(embeddings[i]) if i < len(embeddings) else None
                }
                res_cit = await client.post(f"{DB_URL}/tools/sql_execute", json={"sql": sql_cit, "params": params_cit})
                res_cit.raise_for_status()
                count += 1

            return f"SUCCESS: Verified {count} citations saved to Cloud SQL for session {db_session_id}."
    except Exception as e:
        logger.error(f"DB Error in Agent C: {str(e)}")
        return f"ERROR: Failed to save to database: {str(e)}"

RESEARCH_TOOLS = [search_web, search_gcp_docs, execute_python, gcs_write, record_citations_batch]

ResearchAgentC = Agent(
    name="ResearchAgentC",
    model="gemini-2.5-flash",
    description="A technical researcher (Agent C).",
    instruction=(
        "You are a technical researcher (Agent C). Perform focused research using Gemini 2.5 Flash.\n"
        "1. Identify the 'SESSION_ID' from the user prompt (it follows the 'SESSION_ID: ' tag).\n"
        "2. Gather exactly 5 high-quality citations from the live web based on the 'QUESTION' tag.\n"
        "3. If the user asks for data analysis, trends, or visualizations, use 'execute_python' to generate charts (using matplotlib) and 'gcs_write' to save them. Use the SESSION_ID in the filename (e.g., charts/{session_id}_trend.png).\n"
        "4. Use 'record_citations_batch' ONCE to save all 5 results and any generated file URLs using the extracted SESSION_ID."
    ),
    tools=RESEARCH_TOOLS
)

root_agent = ResearchAgentC
