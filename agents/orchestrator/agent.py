import os
import json
import asyncio
from typing import AsyncGenerator, Any
from google.adk.agents import BaseAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types as genai_types

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

# --- Custom Orchestrator ---

class ConclaveOrchestrator(BaseAgent):
    def __init__(self):
        super().__init__(name="conclave_orchestrator", description="Orchestrates Model Conclave stages.")

    async def run_async(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        def create_msg_event(text: str, author: str = "System") -> Event:
            content = genai_types.Content(parts=[genai_types.Part(text=text)])
            return Event(author=author, content=content, actions=EventActions(skip_summarization=True))

        is_mock = os.getenv("MOCK_MODE") == "true"
        
        # EXTRACT CLEAN DATA
        raw_msg = ctx.user_content.parts[0].text
        # Input format from main.py: "Session ID: {session_id}. Question: {question}"
        # We ensure it is passed correctly to sub-agents
        formatted_message = raw_msg 

        async def run_stage(agent, stage_num, agent_label):
            yield create_msg_event(f"[Stage {stage_num}/4] {agent_label} is initializing...")
            await asyncio.sleep(1)
            
            if is_mock:
                yield create_msg_event(f"Searching for live data...", author=agent.name)
                await asyncio.sleep(2)
                yield create_msg_event(f"Recording 5 mock citations...", author=agent.name)
                await asyncio.sleep(2)
            else:
                yield create_msg_event(f"Performing deep live research...", author=agent.name)
                # FIX: Pass the STRING message, not the context object
                async for event in agent.run_async(formatted_message):
                    yield event

        # Execute Stages
        async for e in run_stage(research_a, 1, "Agent A (Claude)"): yield e
        async for e in run_stage(research_b, 2, "Agent B (GPT)"): yield e
        async for e in run_stage(research_c, 3, "Agent C (Gemini)"): yield e

        # Synthesis
        yield create_msg_event("[Stage 4/4] Synthesizing final report...")
        if is_mock:
            report = "## Mock Model Conclave Report\n\nGenerated in **Mock Mode**. Data saved to SQL successfully."
            yield create_msg_event(report, author="SynthesizerAgent")
        else:
            # FIX: Pass the STRING message
            async for event in synthesizer.run_async(formatted_message):
                yield event

root_agent = ConclaveOrchestrator()
