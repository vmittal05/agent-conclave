import operator
import uuid
from typing import Annotated, List, Dict, Any, TypedDict
from langgraph.graph import StateGraph, END, START
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types
from backend.agents import ResearchAgentA, ResearchAgentB, ResearchAgentC, SynthesizerAgent

# --- State Definition ---
class CouncilState(TypedDict):
    session_id: str
    user_question: str
    progress: Dict[str, int]
    agent_summaries: Annotated[List[str], operator.add]
    ready_for_synthesis: bool
    final_report: str

def query_agent(agent, question: str) -> str:
    """Helper to synchronously query an ADK LlmAgent."""
    runner = InMemoryRunner(agent=agent)
    message = genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=question)])
    # Use a random session ID to isolate conversations
    events = runner.run(user_id="council_user", session_id=str(uuid.uuid4()), new_message=message)
    response = ""
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response += part.text
    return response

# --- Node Implementations ---

def research_a_node(state: CouncilState):
    """Parallel node for ResearchAgentA."""
    print("--- RESEARCHING WITH AGENT A ---")
    response = query_agent(ResearchAgentA, state["user_question"])
    return {"agent_summaries": [f"Agent A Summary: {response}"]}

def research_b_node(state: CouncilState):
    """Parallel node for ResearchAgentB."""
    print("--- RESEARCHING WITH AGENT B ---")
    response = query_agent(ResearchAgentB, state["user_question"])
    return {"agent_summaries": [f"Agent B Summary: {response}"]}

def research_c_node(state: CouncilState):
    """Parallel node for ResearchAgentC."""
    print("--- RESEARCHING WITH AGENT C ---")
    response = query_agent(ResearchAgentC, state["user_question"])
    return {"agent_summaries": [f"Agent C Summary: {response}"]}

def synthesis_node(state: CouncilState):
    """Sequential node for SynthesizerAgent."""
    print("--- SYNTHESIZING COUNCIL RESULTS ---")
    prompt = f"Synthesize report for session {state['session_id']}. Question: {state['user_question']}\n\nSummaries:\n" + "\n".join(state["agent_summaries"])
    report = query_agent(SynthesizerAgent, prompt)
    return {"final_report": report, "ready_for_synthesis": True}

# --- Graph Construction ---

workflow = StateGraph(CouncilState)

workflow.add_node("research_a", research_a_node)
workflow.add_node("research_b", research_b_node)
workflow.add_node("research_c", research_c_node)
workflow.add_node("synthesizer", synthesis_node)

workflow.add_edge(START, "research_a")
workflow.add_edge(START, "research_b")
workflow.add_edge(START, "research_c")

workflow.add_edge("research_a", "synthesizer")
workflow.add_edge("research_b", "synthesizer")
workflow.add_edge("research_c", "synthesizer")

workflow.add_edge("synthesizer", END)

council_graph = workflow.compile()
