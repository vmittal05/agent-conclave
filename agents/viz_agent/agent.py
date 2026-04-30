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
DB_URL = os.getenv("MCP_DB_SERVER_URL", "http://localhost:8010")
CODE_URL = os.getenv("MCP_CODE_SERVER_URL", "http://localhost:8013")
FS_URL = os.getenv("MCP_FS_SERVER_URL", "http://localhost:8014")

# Initialize GenAI client
genai_client = genai.Client(
    vertexai=True, 
    project=os.getenv("GCP_PROJECT_ID"), 
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "global")
)


# --- Viz Tools ---

@traceable(run_type="tool", name="Viz_GetCitations")
async def get_session_citations(session_id: str) -> List[Dict[str, Any]]:
    """Fetch all research citations for the session to extract data for analysis."""
    try:
        async with create_authenticated_client(DB_URL) as client:
            response = await client.post(f"{DB_URL}/tools/get_session_citations", json={"session_id": session_id.strip()}, timeout=30.0)
            response.raise_for_status()
            return response.json().get("results", [])
    except Exception as e:
        logger.error(f"DB MCP Error (viz): {e}")
        return []

@traceable(run_type="tool", name="Viz_ExecutePython")
async def execute_python(code: str) -> Dict[str, Any]:
    """Execute Python code for data analysis or generating charts. Returns stdout and base64 images."""
    try:
        async with create_authenticated_client(CODE_URL) as client:
            response = await client.post(f"{CODE_URL}/tools/execute_python", json={"code": code}, timeout=60.0)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Code MCP Error (viz): {e}")
        return {"error": str(e)}

@traceable(run_type="tool", name="Viz_GCSWrite")
async def gcs_write(file_path: str, content: str, content_type: str = "image/png") -> Dict[str, Any]:
    """Upload a generated chart (base64 string) to the cloud file system."""
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
        logger.error(f"FS MCP Error (viz): {e}")
        return {"error": str(e)}

@traceable(run_type="tool", name="Viz_RecordChartURL")
async def record_chart_citation(session_id: str, chart_url: str, description: str) -> str:
    """Record the generated chart URL into the citation database."""
    try:
        async with create_authenticated_client(DB_URL) as client:
            # 1. Get model_run_id for the viz agent
            sql_ins = "INSERT INTO model_runs (session_id, agent_name, model_id) VALUES (:session_id, :agent_name, :model_id) RETURNING id"
            res_ins = await client.post(f"{DB_URL}/tools/sql_query", json={
                "sql": sql_ins,
                "params": {"session_id": session_id.strip(), "agent_name": "VisualizationAgent", "model_id": "gemini-2.5-flash"}
            })
            res_ins.raise_for_status()
            model_run_id = res_ins.json()["results"][0]["id"]

            # 2. Insert citation
            sql_cit = "INSERT INTO citations (model_run_id, source_url, source_type, title, snippet) VALUES (:model_run_id, :source_url, 'chart', :title, :snippet)"
            params_cit = {
                "model_run_id": model_run_id,
                "source_url": chart_url,
                "title": "Generated Visualization",
                "snippet": f"Visualization created for {description}"
            }
            await client.post(f"{DB_URL}/tools/sql_execute", json={"sql": sql_cit, "params": params_cit})
            return "SUCCESS: Chart URL recorded."
    except Exception as e:
        logger.error(f"DB Error (viz): {e}")
        return f"ERROR: {str(e)}"

# Visualization Agent: Gemini 2.5 Flash
VisualizationAgent = Agent(
    name="VisualizationAgent",
    model="gemini-2.5-flash",
    description="Specialist in data analysis and chart generation.",
    instruction=(
        "You are the Conclave Visualization Specialist. Your job is to create a visual chart based on research gathered by other agents.\n\n"
        "1. Identify the 'SESSION_ID' and 'QUESTION' from the prompt.\n"
        "2. Use 'get_session_citations' to retrieve the raw data gathered during the research phase.\n"
        "3. **Data Analysis**: Extract numerical data or trends from the citations.\n"
        "4. **Generation**: Use 'execute_python' to create a professional matplotlib chart. "
        "IMPORTANT: Your script MUST save the chart to a file (e.g., plt.savefig('chart.png')).\n"
        "5. **Upload**: Find the base64 string in the 'generated_images' field of the response. "
        "Use 'gcs_write' to upload it to GCS. Use a filename including the SESSION_ID (e.g. charts/SESSION_ID_viz.png).\n"
        "6. **Finalize**: Use 'record_chart_citation' to save the resulting public_url into the database so the synthesizer can find it.\n\n"
        "If the question doesn't require a chart, just state that no visualization is needed."
    ),
    tools=[get_session_citations, execute_python, gcs_write, record_chart_citation]
)

root_agent = VisualizationAgent
