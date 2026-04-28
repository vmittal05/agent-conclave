import os
import json
from typing import AsyncGenerator
from google.adk.agents import BaseAgent, SequentialAgent, ParallelAgent
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

class PersonaBroadcaster(BaseAgent):
    """Enriches the user prompt with persona-specific research instructions."""
    _instruction: str = PrivateAttr()
    def __init__(self, name, instruction):
        super().__init__(name=name)
        self._instruction = instruction

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        original_prompt = ""
        for event in ctx.session.events:
            if event.author == "user" and event.content and event.content.parts:
                original_prompt = event.content.parts[0].text
                break
        if not original_prompt:
            original_prompt = ctx.user_content.parts[0].text

        enriched_prompt = f"{self._instruction} Regarding: {original_prompt}"
        yield Event(
            author=self.name,
            content=genai_types.Content(parts=[genai_types.Part(text=enriched_prompt)])
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

# Phase 1: Parallel Research with Persona-Driven Rephrasing
research_council = ParallelAgent(
    name="research_council",
    description="Executes specialized research agents in parallel with distinct focal points.",
    sub_agents=[
        SequentialAgent(name="path_a", sub_agents=[
            PersonaBroadcaster("broadcaster_a", "Analyze the high-level expert consensus and industry standards for:"),
            research_a
        ]),
        SequentialAgent(name="path_b", sub_agents=[
            PersonaBroadcaster("broadcaster_b", "Search for empirical data, benchmarks, and statistical evidence regarding:"),
            research_b
        ]),
        SequentialAgent(name="path_c", sub_agents=[
            PersonaBroadcaster("broadcaster_c", "Find technical documentation, API specifications, and implementation examples for:"),
            research_c
        ])
    ]
)

# Phase 2: Synthesis
root_agent = SequentialAgent(
    name="conclave_pipeline",
    description="Model Conclave pipeline with Parallel Research.",
    sub_agents=[
        StageNotifier("system_start", "[Stage 1/2] Research Council is starting parallel analysis..."),
        # Initial broadcast to set context
        PersonaBroadcaster("input_broadcaster", "Coordinate a multi-perspective analysis on:"),
        research_council,
        StageNotifier("system_synth", "[Stage 2/2] Synthesizer is generating grounded report..."),
        # Final broadcast to ensure synthesizer has the original intent
        PersonaBroadcaster("synth_broadcaster", "Synthesize all gathered data to answer:"),
        synthesizer
    ]
)
