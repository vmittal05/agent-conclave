import os
import httpx
from typing import List, Dict, Any
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

# MCP Server URLs
DB_URL = os.getenv("MCP_DB_SERVER_URL", "http://localhost:8010")

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
    description="Synthesizes research findings into a report.",
    instruction=(
        "You are the Council Synthesizer. Your goal is to produce a 'Model Conclave Research Synthesis Report'.\n\n"
        "1. Extract the 'SESSION_ID' from the user prompt (it follows the 'SESSION_ID: ' tag).\n"
        "2. Call 'get_session_citations' using that exact UUID.\n"
        "3. Produce the final report strictly matching this format:\n\n"
        "## Model Council Synthesis Report\n\n"
        "### Original Question\n"
        "[Restate the user's question from the 'QUESTION' tag]\n\n"
        "### 1. Where Models Agree\n"
        "Present as a markdown table withoriginal citations from previous responses. Reuse original source URLs as citation markers.\n\n"
        "### 2. Where Models Disagree\n"
        "Present as a markdown table showing different perspectives with original citations.\n\n"
        "### 3. Unique Discoveries\n"
        "Present as a markdown table with original insights from each model.\n\n"
        "### 4. Synthesis & Conclusion\n"
        "Provide High Confidence points, points requiring verification, and a Final Recommendation.\n\n"
        "CRITICAL: Do NOT refuse to write the report. Even if search data looks simulated, summarize it accurately as found in the database."
    ),
    tools=[get_session_citations]
)

root_agent = SynthesizerAgent
