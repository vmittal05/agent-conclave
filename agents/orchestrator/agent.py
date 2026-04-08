import os
import json
from typing import AsyncGenerator
from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types as genai_types
from pydantic import PrivateAttr

from authenticated_httpx import create_authenticated_client

# --- Remote Agents ---

research_a_url = os.environ.get("RESEARCH_A_AGENT_CARD_URL", "http://localhost:8001/a2a/agent/.well-known/agent-card.json")
research_a = RemoteA2aAgent(name="ResearchAgentA", agent_card=research_a_url, httpx_client=create_authenticated_client(research_a_url))

research_b_url = os.environ.get("RESEARCH_B_AGENT_CARD_URL", "http://localhost:8002/a2a/agent/.well-known/agent-card.json")
research_b = RemoteA2aAgent(name="ResearchAgentB", agent_card=research_b_url, httpx_client=create_authenticated_client(research_b_url))

research_c_url = os.environ.get("RESEARCH_C_AGENT_CARD_URL", "http://localhost:8003/a2a/agent/.well-known/agent-card.json")
research_c = RemoteA2aAgent(name="ResearchAgentC", agent_card=research_c_url, httpx_client=create_authenticated_client(research_c_url))

synthesizer_url = os.environ.get("SYNTHESIZER_AGENT_CARD_URL", "http://localhost:8004/a2a/agent/.well-known/agent-card.json")
synthesizer = RemoteA2aAgent(name="SynthesizerAgent", agent_card=synthesizer_url, httpx_client=create_authenticated_client(synthesizer_url))

# --- Helper Agents ---

class PromptBroadcaster(BaseAgent):
    """Ensures the next agent in a sequence receives the original user prompt."""
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # Find the first user message in the session
        original_prompt = ""
        for event in ctx.session.events:
            if event.author == "user" and event.content and event.content.parts:
                original_prompt = event.content.parts[0].text
                break
        
        # If not found in history, use the current user_content
        if not original_prompt:
            original_prompt = ctx.user_content.parts[0].text

        yield Event(
            author=self.name,
            content=genai_types.Content(parts=[genai_types.Part(text=original_prompt)])
        )

class StageNotifier(BaseAgent):
    """Simple agent to emit Stage progress logs."""
    _text: str = PrivateAttr()
    def __init__(self, name, text):
        super().__init__(name=name)
        self._text = text
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        yield Event(
            author=self.name,
            content=genai_types.Content(parts=[genai_types.Part(text=self._text)]),
            actions=EventActions(skip_summarization=True)
        )

# --- Orchestration ---

# We create UNIQUE instances for each stage to satisfy Pydantic's "one parent" rule
root_agent = SequentialAgent(
    name="conclave_pipeline",
    description="Sequential Model Conclave pipeline.",
    sub_agents=[
        # Stage 1
        StageNotifier("system_1", "[Stage 1/4] Agent A is starting research..."),
        PromptBroadcaster(name="broadcaster_1"),
        research_a,
        
        # Stage 2
        StageNotifier("system_2", "[Stage 2/4] Agent B is starting research..."),
        PromptBroadcaster(name="broadcaster_2"),
        research_b,
        
        # Stage 3
        StageNotifier("system_3", "[Stage 3/4] Agent C is starting research..."),
        PromptBroadcaster(name="broadcaster_3"),
        research_c,
        
        # Stage 4
        StageNotifier("system_4", "[Stage 4/4] Synthesizer is generating report..."),
        PromptBroadcaster(name="broadcaster_4"),
        synthesizer
    ]
)
