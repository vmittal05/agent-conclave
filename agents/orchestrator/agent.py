import os
import json
from typing import AsyncGenerator
from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext

from authenticated_httpx import create_authenticated_client

# --- Remote Agents ---

# Connect to ResearchAgentA (Localhost port 8001)
research_a_url = os.environ.get("RESEARCH_A_AGENT_CARD_URL", "http://localhost:8001/a2a/agent/.well-known/agent-card.json")
research_a = RemoteA2aAgent(
    name="ResearchAgentA",
    agent_card=research_a_url,
    description="An expert researcher (Agent A).",
    httpx_client=create_authenticated_client(research_a_url)
)

# Connect to ResearchAgentB (Localhost port 8002)
research_b_url = os.environ.get("RESEARCH_B_AGENT_CARD_URL", "http://localhost:8002/a2a/agent/.well-known/agent-card.json")
research_b = RemoteA2aAgent(
    name="ResearchAgentB",
    agent_card=research_b_url,
    description="An analytical researcher (Agent B).",
    httpx_client=create_authenticated_client(research_b_url)
)

# Connect to ResearchAgentC (Localhost port 8003)
research_c_url = os.environ.get("RESEARCH_C_AGENT_CARD_URL", "http://localhost:8003/a2a/agent/.well-known/agent-card.json")
research_c = RemoteA2aAgent(
    name="ResearchAgentC",
    agent_card=research_c_url,
    description="A technical researcher (Agent C).",
    httpx_client=create_authenticated_client(research_c_url)
)

# Connect to SynthesizerAgent (Localhost port 8004)
synthesizer_url = os.environ.get("SYNTHESIZER_AGENT_CARD_URL", "http://localhost:8004/a2a/agent/.well-known/agent-card.json")
synthesizer = RemoteA2aAgent(
    name="SynthesizerAgent",
    agent_card=synthesizer_url,
    description="Synthesizes research findings into a report.",
    httpx_client=create_authenticated_client(synthesizer_url)
)

# --- Custom Orchestrator ---

class ConclaveOrchestrator(BaseAgent):
    """Custom orchestrator that passes the same prompt to all agents sequentially."""
    
    def __init__(self):
        super().__init__(
            name="conclave_orchestrator",
            description="Orchestrates research and synthesis stages."
        )

    async def run_async(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # Extract the original user message
        user_message = ctx.user_content.parts[0].text
        
        # 1. Research Agent A
        yield Event(author=self.name, content="[Stage 1/4] Research Agent A (Claude perspective) is starting...", actions=EventActions(skip_summarization=True))
        async for event in research_a.run_async(user_message):
            yield event
            
        # 2. Research Agent B
        yield Event(author=self.name, content="[Stage 2/4] Research Agent B (GPT perspective) is starting...", actions=EventActions(skip_summarization=True))
        async for event in research_b.run_async(user_message):
            yield event
            
        # 3. Research Agent C
        yield Event(author=self.name, content="[Stage 3/4] Research Agent C (Gemini perspective) is starting...", actions=EventActions(skip_summarization=True))
        async for event in research_c.run_async(user_message):
            yield event
            
        # 4. Synthesis
        yield Event(author=self.name, content="[Stage 4/4] Generating Model Council Synthesis Report...", actions=EventActions(skip_summarization=True))
        # We pass the same original message (which contains the Session ID) to the synthesizer
        async for event in synthesizer.run_async(user_message):
            yield event

root_agent = ConclaveOrchestrator()
