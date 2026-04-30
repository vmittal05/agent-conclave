import os
import json
import logging
from typing import AsyncGenerator
from google import genai
from google.adk.agents import BaseAgent, SequentialAgent, ParallelAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types as genai_types
from pydantic import PrivateAttr
import httpx
from langsmith import traceable

from authenticated_httpx import create_authenticated_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Registry Configuration ---
REGISTRY_URL = os.getenv("AGENT_REGISTRY_URL", "http://localhost:8012")

# Initialize GenAI client for routing decisions
genai_client = genai.Client(
    vertexai=True, 
    project=os.getenv("GCP_PROJECT_ID"), 
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
)

# --- Helper Agents ---

class RouterAgent(BaseAgent):
    """Evaluates the query to decide if web research can be bypassed."""
    @traceable(run_type="chain", name="Orchestrator_Router")
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        original_prompt = ""
        for event in ctx.session.events:
            if event.author == "user" and event.content and event.content.parts:
                original_prompt = event.content.parts[0].text
                break
        if not original_prompt:
            original_prompt = ctx.user_content.parts[0].text

        yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text="🚦 Routing: Analyzing query complexity...")]), actions=EventActions(skip_summarization=True))
        
        prompt = (
            "Analyze the following user research question. Determine if this question is 'SIMPLE' "
            "(can be answered accurately by a general LLM without live web search) or 'COMPLEX' "
            "(requires live research, current data, or multiple perspectives).\n\n"
            f"QUESTION: {original_prompt}\n\n"
            "Return only the word 'SIMPLE' or 'COMPLEX'."
        )
        
        try:
            response = genai_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )
            decision = response.text.strip().upper()
            logger.info(f"Router Decision: {decision}")

            if "SIMPLE" in decision:
                ctx.session.state["skip_research"] = True
                yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text="⚡ Fast-Path: Query is simple. Bypassing research phase.")]), actions=EventActions(skip_summarization=True))
            else:
                ctx.session.state["skip_research"] = False
                yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text="🧬 Deep-Path: Complexity detected. Initiating multi-agent research...")]), actions=EventActions(skip_summarization=True))
        except Exception as e:
            logger.error(f"Router Error: {e}")
            ctx.session.state["skip_research"] = False # Default to research on error
            yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text=f"⚠️ Router Error: {str(e)}. Falling back to Deep-Path.")]), actions=EventActions(skip_summarization=True))


class DiscoveryAgent(BaseAgent):
    """Queries the Registry to find suitable agents for the research task."""
    @traceable(run_type="chain", name="Orchestrator_Discovery")
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if ctx.session.state.get("skip_research"):
            return

        yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text="🔍 Consulting Agent Registry for specialists...")]), actions=EventActions(skip_summarization=True))
        
        try:
            async with create_authenticated_client(REGISTRY_URL) as client:
                response = await client.get(f"{REGISTRY_URL}/agents")
                if response.status_code == 200:
                    agents = response.json()
                    # Filter for research agents
                    researchers = [a for a in agents if "ResearchAgent" in a["name"]]
                    
                    # Store in session state for the next stage
                    ctx.session.state["discovered_researchers"] = researchers
                    
                    names = ", ".join([a["name"] for a in researchers])
                    yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text=f"✅ Found {len(researchers)} agents: {names}")]), actions=EventActions(skip_summarization=True))
                else:
                    yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text=f"⚠️ Registry lookup failed ({response.status_code}).")]), actions=EventActions(skip_summarization=True))
        except Exception as e:
             yield Event(author=self.name, content=genai_types.Content(parts=[genai_types.Part(text=f"❌ Error contacting registry: {str(e)}")]), actions=EventActions(skip_summarization=True))

class DynamicParallelResearch(BaseAgent):
    """Instantiates and runs RemoteA2aAgents dynamically based on DiscoveryAgent results."""
    @traceable(run_type="chain", name="Orchestrator_ParallelResearch")
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if ctx.session.state.get("skip_research"):
            return

        discovered = ctx.session.state.get("discovered_researchers", [])
        
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

    @traceable(run_type="chain", name="Orchestrator_PersonaRephraser")
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
    _skip_on_fastpath: bool = PrivateAttr()
    def __init__(self, name, text, skip_on_fastpath=False):
        super().__init__(name=name)
        self._text = text
        self._skip_on_fastpath = skip_on_fastpath

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if self._skip_on_fastpath and ctx.session.state.get("skip_research"):
            return

        yield Event(
            author=self.name,
            content=genai_types.Content(parts=[genai_types.Part(text=self._text)]),
            actions=EventActions(skip_summarization=True)
        )

# --- Orchestration ---

# The Root Pipeline is now truly dynamic and traced
root_agent = SequentialAgent(
    name="conclave_pipeline",
    description="Dynamic Model Conclave pipeline.",
    sub_agents=[
        RouterAgent(name="query_router"),

        StageNotifier("system_start", "[Stage 1/3] Discovery: Locating available research experts...", skip_on_fastpath=True),
        DiscoveryAgent(name="discovery_service"),
        
        StageNotifier("system_research", "[Stage 2/3] Research: Executing parallel multi-perspective analysis...", skip_on_fastpath=True),
        DynamicParallelResearch(name="dynamic_research_hub"),
        
        StageNotifier("system_synth", "[Stage 3/3] Synthesis: Generating grounded final report..."),
        PersonaBroadcaster("synth_broadcaster", "Synthesize all gathered data to answer:"),
        RemoteA2aAgent(
            name="SynthesizerAgent", 
            agent_card=os.environ.get("SYNTHESIZER_AGENT_CARD_URL", "http://localhost:8004/a2a/agent/.well-known/agent-card.json"),
            httpx_client=create_authenticated_client(os.environ.get("SYNTHESIZER_AGENT_CARD_URL", "http://localhost:8004/a2a/agent/.well-known/agent-card.json"))
        )
    ]
)
