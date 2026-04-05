import os
import json
from typing import AsyncGenerator
from google.adk.agents import BaseAgent, ParallelAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext

from authenticated_httpx import create_authenticated_client

# --- Callbacks ---
def create_save_output_callback(key: str):
    """Creates a callback to save the agent's final response to session state."""
    def callback(callback_context: CallbackContext, **kwargs) -> None:
        ctx = callback_context
        # Find the last event from this agent that has content
        for event in reversed(ctx.session.events):
            if event.author == ctx.agent_name and event.content and event.content.parts:
                text = event.content.parts[0].text
                if text:
                    # Initialize or update state list for summaries
                    if key == "agent_summaries":
                        if key not in ctx.state:
                            ctx.state[key] = []
                        ctx.state[key].append(f"{ctx.agent_name} Summary: {text}")
                    else:
                        ctx.state[key] = text
                    print(f"[{ctx.agent_name}] Saved output to state['{key}']")
                    return
    return callback

# --- Remote Agents ---

# Connect to ResearchAgentA (Localhost port 8001)
research_a_url = os.environ.get("RESEARCH_A_AGENT_CARD_URL", "http://localhost:8001/a2a/agent/.well-known/agent-card.json")
research_a = RemoteA2aAgent(
    name="ResearchAgentA",
    agent_card=research_a_url,
    description="An expert researcher (Agent A).",
    after_agent_callback=create_save_output_callback("agent_summaries"),
    httpx_client=create_authenticated_client(research_a_url)
)

# Connect to ResearchAgentB (Localhost port 8002)
research_b_url = os.environ.get("RESEARCH_B_AGENT_CARD_URL", "http://localhost:8002/a2a/agent/.well-known/agent-card.json")
research_b = RemoteA2aAgent(
    name="ResearchAgentB",
    agent_card=research_b_url,
    description="An analytical researcher (Agent B).",
    after_agent_callback=create_save_output_callback("agent_summaries"),
    httpx_client=create_authenticated_client(research_b_url)
)

# Connect to ResearchAgentC (Localhost port 8003)
research_c_url = os.environ.get("RESEARCH_C_AGENT_CARD_URL", "http://localhost:8003/a2a/agent/.well-known/agent-card.json")
research_c = RemoteA2aAgent(
    name="ResearchAgentC",
    agent_card=research_c_url,
    description="A technical researcher (Agent C).",
    after_agent_callback=create_save_output_callback("agent_summaries"),
    httpx_client=create_authenticated_client(research_c_url)
)

# Connect to SynthesizerAgent (Localhost port 8004)
synthesizer_url = os.environ.get("SYNTHESIZER_AGENT_CARD_URL", "http://localhost:8004/a2a/agent/.well-known/agent-card.json")
synthesizer = RemoteA2aAgent(
    name="SynthesizerAgent",
    agent_card=synthesizer_url,
    description="Produces high-fidelity reports based on the council's research.",
    httpx_client=create_authenticated_client(synthesizer_url)
)

# --- Orchestration ---

# Sequential research phase (to avoid 429 quota errors in testing)
research_sequence = SequentialAgent(
    name="research_sequence",
    description="Runs three research agents one after another.",
    sub_agents=[research_a, research_b, research_c]
)

# Sequential pipeline: Research -> Synthesis
root_agent = SequentialAgent(
    name="council_pipeline",
    description="A pipeline that researches a topic with three agents and then synthesizes the results.",
    sub_agents=[research_sequence, synthesizer]
)
