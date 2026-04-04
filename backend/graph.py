import operator
from typing import Annotated, List, Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from backend.agents import ResearchAgentA, ResearchAgentB, ResearchAgentC, SynthesizerAgent

# --- State Definition ---
class CouncilState(TypedDict):
    session_id: str
    user_question: str
    progress: Dict[str, int] # e.g. {"completed_models": 0, "total_models": 3}
    agent_summaries: Annotated[List[str], operator.add]
    ready_for_synthesis: bool
    final_report: str

# --- Node Implementations ---

def research_a_node(state: CouncilState):
    """Parallel node for ResearchAgentA."""
    print("--- RESEARCHING WITH AGENT A ---")
    response = ResearchAgentA.query(input=state["user_question"])
    return {"agent_summaries": [f"Agent A Summary: {response}"]}

def research_b_node(state: CouncilState):
    """Parallel node for ResearchAgentB."""
    print("--- RESEARCHING WITH AGENT B ---")
    response = ResearchAgentB.query(input=state["user_question"])
    return {"agent_summaries": [f"Agent B Summary: {response}"]}

def research_c_node(state: CouncilState):
    """Parallel node for ResearchAgentC."""
    print("--- RESEARCHING WITH AGENT C ---")
    response = ResearchAgentC.query(input=state["user_question"])
    return {"agent_summaries": [f"Agent C Summary: {response}"]}

def synthesis_node(state: CouncilState):
    """Sequential node for SynthesizerAgent."""
    print("--- SYNTHESIZING COUNCIL RESULTS ---")
    summaries = "\n\n".join(state["agent_summaries"])
    prompt = (
        f"Based on the following research summaries from the council:\n\n{summaries}\n\n"
        f"Synthesize a final report for the user's question: {state['user_question']}"
    )
    report = SynthesizerAgent.query(input=prompt)
    return {"final_report": report, "ready_for_synthesis": True}

# --- Graph Construction ---

workflow = StateGraph(CouncilState)

# Add Nodes
workflow.add_node("research_a", research_a_node)
workflow.add_node("research_b", research_b_node)
workflow.add_node("research_c", research_c_node)
workflow.add_node("synthesizer", synthesis_node)

# Set Entry Point
workflow.set_entry_point(["research_a", "research_b", "research_c"])

# Add Edges (Wait for all parallel nodes to complete before synthesis)
workflow.add_edge("research_a", "synthesizer")
workflow.add_edge("research_b", "synthesizer")
workflow.add_edge("research_c", "synthesizer")

# Final Edge
workflow.add_edge("synthesizer", END)

# Compile Graph
council_graph = workflow.compile()
