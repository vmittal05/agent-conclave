import os
import httpx
from typing import List, Dict, Any, Optional
from google.adk import Agent
from google.adk.agents.invocation_context import InvocationContext
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

async def record_citation(
    ctx: InvocationContext,
    source_url: str,
    title: str,
    snippet: str,
    source_type: str = "web"
) -> str:
    """Record a citation to the database via Database MCP.
    Note: model_run_id is handled internally using the session ID.
    """
    # 1. Ensure we have a model_run record for this agent/session
    session_id = ctx.session.id
    agent_name = "ResearchAgentA"
    model_id = "gemini-2.5-flash"

    try:
        # Check if model_run exists
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
            # Create new model_run
            sql_ins = "INSERT INTO model_runs (session_id, agent_name, model_id) VALUES (:session_id, :agent_name, :model_id) RETURNING id"
            # Note: sql_execute doesn't always return rows, so we use sql_query for RETURNING
            res_ins = httpx.post(f"{DB_URL}/tools/sql_query", json={
                "sql": sql_ins,
                "params": {"session_id": session_id, "agent_name": agent_name, "model_id": model_id}
            }, timeout=10.0)
            res_ins.raise_for_status()
            model_run_id = res_ins.json()["results"][0]["id"]

        # 2. Record the citation
        sql_cit = """
            INSERT INTO citations (model_run_id, source_url, source_type, title, snippet)
            VALUES (:model_run_id, :source_url, :source_type, :title, :snippet)
        """
        params_cit = {
            "model_run_id": model_run_id,
            "source_url": source_url,
            "source_type": source_type,
            "title": title,
            "snippet": snippet
        }
        res_cit = httpx.post(f"{DB_URL}/tools/sql_execute", json={"sql": sql_cit, "params": params_cit}, timeout=10.0)
        res_cit.raise_for_status()
        return f"Citation recorded successfully for {title}."
    except Exception as e:
        print(f"DB MCP Error in record_citation: {e}")
        return f"Failed to record citation: {str(e)}"

RESEARCH_TOOLS = [search_web, search_gcp_docs, record_citation]

# --- Research Agent Definitions (Working ADK Pattern) ---

# Agent A: Gemini 2.5 Flash
ResearchAgentA = Agent(
    name="ResearchAgentA",
    model="gemini-2.5-flash",
    description="An expert researcher (Agent A).",
    instruction=(
        "You are an expert researcher (Agent A). Perform focused research using Gemini 2.5 Flash. "
        "Gather 5-10 high-quality citations (do not exceed 10). "
        "Use ONLY the 'record_citation' tool to save each source. Do NOT use any other name for this tool."
    ),
    tools=RESEARCH_TOOLS
)

root_agent = ResearchAgentA
