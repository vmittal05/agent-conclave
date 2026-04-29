import os
import json
from typing import AsyncGenerator
from google.adk.agents import BaseAgent, SequentialAgent, ParallelAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types as genai_types
from pydantic import PrivateAttr
import httpx

from authenticated_httpx import create_authenticated_client

# --- Registry Configuration ---
REGISTRY_URL = os.getenv("AGENT_REGISTRY_URL", "http://localhost:8012")

# --- Helper Agents ---

class DiscoveryAgent(BaseAgent):
    """Queries the Registry to find suitable agents for the research task."""
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text="🔍 Consulting Agent Registry for specialists...")]), actions=EventActions(skip_summarization=True))
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{REGISTRY_URL}/agents")
                if response.status_code == 200:
                    agents = response.json()
                    # Filter for agents that likely perform research (e.g. have search tools)
                    # For local dev, we just look for 'agent' or 'ResearchAgent'
                    researchers = [a for a in agents if "ResearchAgent" in a["name"]]
                    
                    # Store in context for the next stage
                    ctx.context["discovered_researchers"] = researchers
                    
                    names = ", ".join([a["name"] for a in researchers])
                    yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text=f"✅ Found {len(researchers)} agents: {names}")]), actions=EventActions(skip_summarization=True))
                else:
                    yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text="⚠️ Registry lookup failed.")]), actions=EventActions(skip_summarization=True))
        except Exception as e:
             yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text=f"❌ Error contacting registry: {str(e)}")]), actions=EventActions(skip_summarization=True))

class DynamicParallelResearch(BaseAgent):
    """Instantiates and runs RemoteA2aAgents dynamically based on DiscoveryAgent results."""
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        discovered = ctx.context.get("discovered_researchers", [])
        
        if not discovered:
            yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text="No researchers discovered. Skipping research phase.")]))
            return

        paths = []
        instructions = [
            "Analyze the high-level expert consensus and industry standards for:",
            "Search for empirical data, benchmarks, and statistical evidence regarding:",
            "Find technical documentation, API specifications, and implementation examples for:"
        ]

        for i, agent_info in enumerate(discovered):
            instr = instructions[i % len(instructions)]
            agent_well_known = f"{agent_info['url']}/.well-known/agent-card.json"
            
            remote_agent = RemoteA2aAgent(
                name=agent_info["name"],
                agent_card=agent_well_known,
                httpx_client=create_authenticated_client(agent_well_known)
            )
            
            path = SequentialAgent(name=f"dynamic_path_{i}", sub_agents=[
                PersonaBroadcaster(f"broadcaster_{i}", instr),
                remote_agent
            ])
            paths.append(path)

        parallel_block = ParallelAgent(
            name="dynamic_research_council",
            sub_agents=paths
        )
        
        async for event in parallel_block.run_async(ctx):
            yield event

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

# The Root Pipeline is now truly dynamic
root_agent = SequentialAgent(
    name="conclave_pipeline",
    description="Dynamic Model Conclave pipeline.",
    sub_agents=[
        StageNotifier("system_start", "[Stage 1/3] Discovery: Locating available research experts..."),
        DiscoveryAgent(name="discovery_service"),
        
        StageNotifier("system_research", "[Stage 2/3] Research: Executing parallel multi-perspective analysis..."),
        DynamicParallelResearch(name="dynamic_research_hub"),
        
        StageNotifier("system_synth", "[Stage 3/3] Synthesis: Generating grounded final report..."),
        # We broadcast the user prompt again to ensure synthesizer has the original intent
        PersonaBroadcaster("synth_broadcaster", "Synthesize all gathered data to answer:"),
        RemoteA2aAgent(
            name="SynthesizerAgent", 
            agent_card=os.environ.get("SYNTHESIZER_AGENT_CARD_URL", "http://localhost:8004/a2a/agent/.well-known/agent-card.json"),
            httpx_client=create_authenticated_client(os.environ.get("SYNTHESIZER_AGENT_CARD_URL", "http://localhost:8004/a2a/agent/.well-known/agent-card.json"))
        )
    ]
)
