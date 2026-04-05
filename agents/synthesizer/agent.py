import os
import httpx
from typing import List, Dict, Any
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

# MCP Server URLs
DB_URL = os.getenv("MCP_DB_SERVER_URL", "http://localhost:8004")

def get_session_citations(session_id: str) -> List[Dict[str, Any]]:
    """Fetch and analyze all citations for the current council session."""
    try:
        response = httpx.post(f"{DB_URL}/tools/get_session_citations", json={"session_id": session_id}, timeout=30.0)
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"DB MCP Error (get_session_citations): {e}")
        return []

# Synthesizer Agent: Gemini 2.5 Pro
SynthesizerAgent = Agent(
    name="SynthesizerAgent",
    model="gemini-2.5-pro",
    description="Produces high-fidelity reports based on the council's research.",
    instruction=(
        "You are the Council Synthesizer. Produce a high-fidelity report based on the council's research. "
        "Call 'get_session_citations' to analyze overlapping sources and unique insights."
    ),
    tools=[get_session_citations]
)

root_agent = SynthesizerAgent
