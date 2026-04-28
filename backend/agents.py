import os
import httpx
import logging
from typing import List, Dict, Any, Optional
from google import genai
from google.adk import Agent
from google.genai import types as genai_types
from dotenv import load_dotenv

from authenticated_httpx import create_authenticated_client

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP Server URLs
SEARCH_URL = os.getenv("MCP_SEARCH_SERVER_URL", "http://localhost:8011")
DB_URL = os.getenv("MCP_DB_SERVER_URL", "http://localhost:8010")

# Initialize GenAI client using Vertex AI (uses ADC in Cloud Shell/Cloud Run)
genai_client = genai.Client(
    vertexai=True, 
    project=os.getenv("GCP_PROJECT_ID"), 
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
)

# --- Common Research Tools ---

async def search_web(query: str) -> List[Dict[str, Any]]:
    """Search the web for academic and general sources."""
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

async def record_citation(
    tool_context: Any,
    model_run_id: int,
    source_url: str,
    title: str,
    snippet: str,
    source_type: str = "web"
) -> str:
    """Record a citation with embedding to the database via Database MCP."""
    try:
        # Generate embedding for the snippet
        embed_res = genai_client.models.embed_content(
            model="text-embedding-004",
            contents=snippet,
            config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        embedding = embed_res.embeddings[0].values

        sql = """
            INSERT INTO citations (model_run_id, source_url, source_type, title, snippet, embedding)
            VALUES (:model_run_id, :source_url, :source_type, :title, :snippet, :embedding)
        """
        params = {
            "model_run_id": model_run_id,
            "source_url": source_url,
            "source_type": source_type,
            "title": title,
            "snippet": snippet,
            "embedding": str(embedding)
        }
        async with create_authenticated_client(DB_URL) as client:
            response = await client.post(f"{DB_URL}/tools/sql_execute", json={"sql": sql, "params": params}, timeout=10.0)
            response.raise_for_status()
            return f"Citation recorded successfully with embedding."
    except Exception as e:
        logger.error(f"DB MCP Error: {e}")
        return f"Failed to record citation: {str(e)}"

async def get_session_citations(session_id: str) -> List[Dict[str, Any]]:
    """Fetch all citations for the current council session."""
    try:
        async with create_authenticated_client(DB_URL) as client:
            response = await client.post(f"{DB_URL}/tools/get_session_citations", json={"session_id": session_id.strip()}, timeout=30.0)
            response.raise_for_status()
            return response.json().get("results", [])
    except Exception as e:
        logger.error(f"DB MCP Error (get_session_citations): {e}")
        return []

async def semantic_citation_lookup(session_id: str, query: str) -> List[Dict[str, Any]]:
    """Search for the most semantically relevant raw citations using vector similarity."""
    try:
        embed_res = genai_client.models.embed_content(
            model="text-embedding-004",
            contents=query,
            config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
        )
        query_embedding = embed_res.embeddings[0].values

        async with create_authenticated_client(DB_URL) as client:
            payload = {
                "session_id": session_id.strip(),
                "query_embedding": query_embedding,
                "top_k": 5
            }
            response = await client.post(f"{DB_URL}/tools/semantic_search_citations", json=payload, timeout=30.0)
            response.raise_for_status()
            return response.json().get("results", [])
    except Exception as e:
        logger.error(f"Semantic Search Error: {e}")
        return []

RESEARCH_TOOLS = [search_web, search_gcp_docs, record_citation]

# --- Research Agent Definitions ---

ResearchAgentA = Agent(
    name="ResearchAgentA",
    model="gemini-2.5-flash",
    instruction=(
        "You are an expert researcher (Agent A). Gather exactly 5 high-quality citations. "
        "Record every source using 'record_citation'."
    ),
    tools=RESEARCH_TOOLS
)

ResearchAgentB = Agent(
    name="ResearchAgentB",
    model="gemini-2.5-flash",
    instruction=(
        "You are an analytical researcher (Agent B). Focus on empirical evidence. "
        "Gather exactly 5 high-quality citations. Record every source using 'record_citation'."
    ),
    tools=RESEARCH_TOOLS
)

ResearchAgentC = Agent(
    name="ResearchAgentC",
    model="gemini-2.5-pro",
    instruction=(
        "You are a technical researcher (Agent C). Focus on documentation. "
        "Gather exactly 5 high-quality citations. Record every source using 'record_citation'."
    ),
    tools=RESEARCH_TOOLS
)

SynthesizerAgent = Agent(
    name="SynthesizerAgent",
    model="gemini-2.5-pro",
    instruction=(
        "You are the Council Synthesizer. Produce a grounded report. "
        "Use 'get_session_citations' and 'semantic_citation_lookup' for evidence."
    ),
    tools=[get_session_citations, semantic_citation_lookup]
)
