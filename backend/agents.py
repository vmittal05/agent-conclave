import os
import httpx
from typing import List, Dict, Any
import vertexai
from vertexai import agent_engines
from dotenv import load_dotenv

load_dotenv()

# MCP Server URLs
SEARCH_URL = os.getenv("MCP_SEARCH_SERVER_URL", "http://localhost:8001")
DB_URL = os.getenv("MCP_DB_SERVER_URL", "http://localhost:8004")

# Initialize Vertex AI
vertexai.init(
    project=os.getenv("GCP_PROJECT_ID"),
    location=os.getenv("GCP_REGION", "us-central1")
)

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

def get_session_citations(session_id: str) -> List[Dict[str, Any]]:
    """Fetch and analyze all citations for the current council session."""
    try:
        response = httpx.post(f"{DB_URL}/tools/get_session_citations", json={"session_id": session_id}, timeout=30.0)
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"DB MCP Error (get_session_citations): {e}")
        return []

RESEARCH_TOOLS = [search_web, search_gcp_docs, record_citation]

# --- Research Agent Definitions (Hybrid Stack) ---

# Agent A: Llama 4 Scout (Meta MaaS)
ResearchAgentA = agent_engines.LangchainAgent(
    model=os.getenv("LITELLM_ROUTE_RESEARCH_A", "llama-4-scout-17b-16e-instruct-maas"),
    tools=RESEARCH_TOOLS,
    instruction=(
        "You are an expert researcher (Agent A). Perform exhaustive research using Llama 4 Scout. "
        "Gather 30-50 high-quality citations. Record every source using 'record_citation'."
    )
)

# Agent B: Llama 3.3 70B (Meta MaaS)
ResearchAgentB = agent_engines.LangchainAgent(
    model=os.getenv("LITELLM_ROUTE_RESEARCH_B", "llama-3.3-70b-instruct-maas"),
    tools=RESEARCH_TOOLS,
    instruction=(
        "You are a analytical researcher (Agent B). Focus on empirical evidence using Llama 3.3 70B. "
        "Gather 30-50 citations. Record every source using 'record_citation'."
    )
)

# Agent C: Gemini 2.5 Pro (Google Native)
ResearchAgentC = agent_engines.LangchainAgent(
    model=os.getenv("LITELLM_ROUTE_RESEARCH_C", "gemini-2.5-pro"),
    tools=RESEARCH_TOOLS,
    instruction=(
        "You are a technical researcher (Agent C). Focus on documentation and feasibility using Gemini 2.5 Pro. "
        "Gather 30-50 citations. Record every source using 'record_citation'."
    )
)

# Synthesizer Agent: Gemini 2.5 Pro (Google Native)
SynthesizerAgent = agent_engines.LangchainAgent(
    model=os.getenv("LITELLM_ROUTE_SYNTHESIZER", "gemini-2.5-pro"),
    tools=[get_session_citations],
    instruction=(
        "You are the Council Synthesizer. Produce a high-fidelity report based on the council's research. "
        "Use Gemini 2.5 Pro to analyze overlapping sources and unique insights."
    )
)
