import operator
from typing import Annotated, List, Dict, Any, TypedDict
from langgraph.graph import StateGraph, END, START
from backend.agents import ResearchAgentA, ResearchAgentB, ResearchAgentC, SynthesizerAgent

# --- State Definition ---
class CouncilState(TypedDict):
    session_id: str
    user_question: str
    progress: Dict[str, int]
    agent_summaries: Annotated[List[str], operator.add]
    ready_for_synthesis: bool
    final_report: str

# --- Node Implementations ---

def research_a_node(state: CouncilState):
    """Parallel node for ResearchAgentA."""
    print("--- RESEARCHING WITH AGENT A ---")
    # google-adk uses .run()
    response = ResearchAgentA.run(input=state["user_question"])
    return {"agent_summaries": [f"Agent A Summary: {response}"]}

def research_b_node(state: CouncilState):
    """Parallel node for ResearchAgentB."""
    print("--- RESEARCHING WITH AGENT B ---")
    response = ResearchAgentB.run(input=state["user_question"])
    return {"agent_summaries": [f"Agent B Summary: {response}"]}

def research_c_node(state: CouncilState):
    """Parallel node for ResearchAgentC."""
    print("--- RESEARCHING WITH AGENT C ---")
    response = ResearchAgentC.run(input=state["user_question"])
    return {"agent_summaries": [f"Agent C Summary: {response}"]}

def synthesis_node(state: CouncilState):
    """Sequential node for SynthesizerAgent."""
    print("--- SYNTHESIZING COUNCIL RESULTS ---")
    prompt = f"Synthesize report for session {state['session_id']}. Question: {state['user_question']}"
    report = SynthesizerAgent.run(input=prompt)
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
