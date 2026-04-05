import os
import httpx
from typing import List, Dict, Any
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

# MCP Server URLs
SEARCH_URL = os.getenv("MCP_SEARCH_SERVER_URL", "http://localhost:8001")
DB_URL = os.getenv("MCP_DB_SERVER_URL", "http://localhost:8004")

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

def record_citation(
    model_run_id: int,
    source_url: str,
    title: str,
    snippet: str,
    source_type: str = "web"
) -> str:
    """Record a citation to the database via Database MCP."""
    sql = """
        INSERT INTO citations (model_run_id, source_url, source_type, title, snippet)
        VALUES (:model_run_id, :source_url, :source_type, :title, :snippet)
    """
    params = {
        "model_run_id": model_run_id,
        "source_url": source_url,
        "source_type": source_type,
        "title": title,
        "snippet": snippet
    }
    try:
        response = httpx.post(f"{DB_URL}/tools/sql_execute", json={"sql": sql, "params": params}, timeout=10.0)
        response.raise_for_status()
        return f"Citation recorded successfully."
    except Exception as e:
        print(f"DB MCP Error: {e}")
        return "Failed to record citation"

RESEARCH_TOOLS = [search_web, search_gcp_docs, record_citation]

# --- Research Agent Definitions (Working ADK Pattern) ---

# Agent C: Gemini 2.5 Pro
ResearchAgentC = Agent(
    name="ResearchAgentC",
    model="gemini-2.5-pro",
    description="A technical researcher (Agent C).",
    instruction=(
        "You are a technical researcher (Agent C). Focus on documentation and feasibility using Gemini 2.5 Pro. "
        "Gather 30-50 citations. Record every source using 'record_citation'."
    ),
    tools=RESEARCH_TOOLS
)

root_agent = ResearchAgentC
