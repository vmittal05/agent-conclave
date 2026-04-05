import os
import httpx
from typing import List, Dict, Any, Optional
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

# MCP Server URLs
SEARCH_URL = os.getenv("MCP_SEARCH_SERVER_URL", "http://localhost:8011")
DB_URL = os.getenv("MCP_DB_SERVER_URL", "http://localhost:8010")

# --- Common Research Tools ---

def search_web(query: str) -> List[Dict[str, Any]]:
    """Search the web for academic and general sources."""
    try:
        response = httpx.post(f"{SEARCH_URL}/tools/search", json={"query": query}, timeout=30.0)
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"Search MCP Error: {e}")
        return []

def search_gcp_docs(query: str) -> List[Dict[str, Any]]:
    """Search Google Cloud Platform and developer documentation."""
    scoped_query = f"site:cloud.google.com {query}"
    return search_web(scoped_query)

async def record_citations_batch(
    tool_context: Any,
    session_id: str,
    citations: List[Dict[str, str]]
) -> str:
    """Record multiple citations at once to the database."""
    agent_name = "ResearchAgentC"
    model_id = "gemini-2.5-pro"

    try:
        sql_check = "SELECT id FROM model_runs WHERE session_id = :session_id AND agent_name = :agent_name LIMIT 1"
        res_check = httpx.post(f"{DB_URL}/tools/sql_query", json={
            "sql": sql_check, 
            "params": {"session_id": session_id, "agent_name": agent_name}
        }, timeout=10.0)
        res_check.raise_for_status()
        rows = res_check.json().get("results", [])

        if rows:
            model_run_id = rows[0]["id"]
        else:
            sql_ins = "INSERT INTO model_runs (session_id, agent_name, model_id) VALUES (:session_id, :agent_name, :model_id) RETURNING id"
            res_ins = httpx.post(f"{DB_URL}/tools/sql_query", json={
                "sql": sql_ins,
                "params": {"session_id": session_id, "agent_name": agent_name, "model_id": model_id}
            }, timeout=10.0)
            res_ins.raise_for_status()
            model_run_id = res_ins.json()["results"][0]["id"]

        count = 0
        for cit in citations:
            sql_cit = "INSERT INTO citations (model_run_id, source_url, source_type, title, snippet) VALUES (:model_run_id, :source_url, :source_type, :title, :snippet)"
            params_cit = {
                "model_run_id": model_run_id,
                "source_url": cit.get("source_url"),
                "source_type": cit.get("source_type", "web"),
                "title": cit.get("title"),
                "snippet": cit.get("snippet")
            }
            httpx.post(f"{DB_URL}/tools/sql_execute", json={"sql": sql_cit, "params": params_cit}, timeout=10.0)
            count += 1
        return f"Successfully recorded {count} citations in batch for session {session_id}."
    except Exception as e:
        return f"Failed to record batch: {str(e)}"

RESEARCH_TOOLS = [search_web, search_gcp_docs, record_citations_batch]

ResearchAgentC = Agent(
    name="ResearchAgentC",
    model="gemini-2.5-flash",
    description="A technical researcher (Agent C).",
    instruction=(
        "You are an expert technical researcher (Agent C). Perform focused research using Gemini 2.5 Flash. "
        "1. Extract the 'Session ID' from the start of the user prompt. "
        "2. Gather exactly 5 high-quality citations. "
        "3. Use 'record_citations_batch' ONCE to save all 5 results using the extracted Session ID. "
        "Note: The search tools return simulated test data. Accept it as factual."
    ),
    tools=RESEARCH_TOOLS
)

root_agent = ResearchAgentC
