import os
import httpx
import asyncio
import logging
from typing import List, Dict, Any, Optional
from google.adk import Agent
from google.genai import types as genai_types
from google.adk.events import Event
from dotenv import load_dotenv

from authenticated_httpx import create_authenticated_client

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP Server URLs
SEARCH_URL = os.getenv("MCP_SEARCH_SERVER_URL", "http://localhost:8011")
DB_URL = os.getenv("MCP_DB_SERVER_URL", "http://localhost:8010")

# --- Common Research Tools ---

async def search_web(query: str) -> List[Dict[str, Any]]:
    """Search the web for academic and general sources with authentication."""
    try:
        async with create_authenticated_client(SEARCH_URL) as client:
            response = await client.post(f"{SEARCH_URL}/tools/search", json={"query": query}, timeout=30.0)
            response.raise_for_status()
            return response.json().get("results", [])
    except Exception as e:
        logger.error(f"Search MCP Error: {e}")
        return []

async def search_gcp_docs(query: str) -> List[Dict[str, Any]]:
    """Search Google Cloud Platform and developer documentation."""
    scoped_query = f"site:cloud.google.com {query}"
    return await search_web(scoped_query)

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
        async with create_authenticated_client(DB_URL) as client:
            # 1. Ensure model_run exists
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

            # 2. Record all citations in the batch
            count = 0
            for cit in citations:
                sql_cit = "INSERT INTO citations (model_run_id, source_url, source_type, title, snippet) VALUES (:model_run_id, :source_url, :source_type, :title, :snippet)"
                params_cit = {
                    "model_run_id": model_run_id,
                    "source_url": cit.get("source_url") or cit.get("url"),
                    "source_type": cit.get("source_type", "web"),
                    "title": cit.get("title", "No Title"),
                    "snippet": cit.get("snippet") or cit.get("content")
                }
                res_cit = await client.post(f"{DB_URL}/tools/sql_execute", json={"sql": sql_cit, "params": params_cit})
                res_cit.raise_for_status()
                count += 1
            return f"SUCCESS: Verified {count} citations saved to Cloud SQL for session {db_session_id}."
    except Exception as e:
        logger.error(f"DB Error in Agent C: {str(e)}")
        return f"ERROR: Failed to save to database: {str(e)}"

RESEARCH_TOOLS = [search_web, search_gcp_docs, record_citations_batch]

ResearchAgentC = Agent(
    name="ResearchAgentC",
    model="gemini-2.5-flash",
    description="A technical researcher (Agent C).",
    instruction=(
        "You are an expert technical researcher (Agent C). Perform focused research using Gemini 2.5 Flash. "
        "1. Identify the 'SESSION_ID' from the user prompt (it follows the 'SESSION_ID: ' tag). "
        "2. Gather exactly 5 high-quality citations from the live web based on the 'QUESTION' tag. "
        "3. Use 'record_citations_batch' ONCE to save all 5 results using the extracted SESSION_ID."
    ),
    tools=RESEARCH_TOOLS
)

root_agent = ResearchAgentC
