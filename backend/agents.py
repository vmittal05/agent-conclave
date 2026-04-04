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

# --- Research Agent Definitions ---

ResearchAgentA = agent_engines.LangchainAgent(
    model=os.getenv("LITELLM_ROUTE_RESEARCH_A", "gemini-1.5-pro"),
    tools=RESEARCH_TOOLS,
    instruction=(
        "You are an expert researcher (Agent A). Perform exhaustive research. "
        "Gather 30-50 high-quality citations using 'search_web' and 'search_gcp_docs'. "
        "Record every source using 'record_citation'. Note: You must provide a valid model_run_id."
    )
)

ResearchAgentB = agent_engines.LangchainAgent(
    model=os.getenv("LITELLM_ROUTE_RESEARCH_B", "gemini-1.5-pro"),
    tools=RESEARCH_TOOLS,
    instruction=(
        "You are a analytical researcher (Agent B). Focus on empirical evidence. "
        "Gather 30-50 citations. Record every source using 'record_citation'. Note: You must provide a valid model_run_id."
    )
)

ResearchAgentC = agent_engines.LangchainAgent(
    model=os.getenv("LITELLM_ROUTE_RESEARCH_C", "gemini-1.5-pro"),
    tools=RESEARCH_TOOLS,
    instruction=(
        "You are a technical researcher (Agent C). Focus on GCP documentation and feasibility. "
        "Gather 30-50 citations. Record every source using 'record_citation'. Note: You must provide a valid model_run_id."
    )
)

SynthesizerAgent = agent_engines.LangchainAgent(
    model=os.getenv("LITELLM_ROUTE_SYNTHESIZER", "gemini-1.5-pro"),
    tools=[get_session_citations],
    instruction=(
        "You are the Council Synthesizer. Your primary goal is to produce a high-fidelity report "
        "based on the research findings of three independent models. "
        "1. Start by calling 'get_session_citations' with the provided session_id to see all sources. "
        "2. Focus on citations with high 'model_overlap_count' (consensus). "
        "3. Identify 'unique insights'—valuable sources cited by only one model. "
        "4. Highlight any 'disagreements' where models cited different facts for the same topic. "
        "5. Final output must be a professional Markdown report."
    )
)
