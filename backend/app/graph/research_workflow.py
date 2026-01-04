from langgraph.graph import StateGraph, END
from app.agents.research.state import DeepResearchState, QueryStatus
from app.agents.research.groomer import query_grooming_node
from app.agents.research.financial import financial_research_node
from app.agents.research.industry import industry_research_node
from app.agents.research.synthesizer import synthesis_node

def should_continue_to_research(state: DeepResearchState) -> str:
    """Check if we should proceed to research or wait for clarification."""
    if not state["research_brief"]:
        return "groom"
        
    if state["research_brief"].status == QueryStatus.NEEDS_CLARIFICATION:
        if state["clarification_count"] >= 2:
            return "research" # Force research after 2 questions
        return END
        
    return "research"

def create_research_workflow():
    """Create the Deep Research LangGraph workflow."""
    workflow = StateGraph(DeepResearchState)
    
    # Add nodes
    workflow.add_node("groom", query_grooming_node)
    workflow.add_node("financial_research", financial_research_node)
    workflow.add_node("industry_research", industry_research_node)
    workflow.add_node("synthesize", synthesis_node)
    
    # Set entry point
    workflow.set_entry_point("groom")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "groom",
        should_continue_to_research,
        {
            "groom": "groom",
            "research": "financial_research",
            "end": END
        }
    )
    
    # Financial and Industry research run "in parallel" conceptually 
    # (actually sequentially in this simple LangGraph implementation 
    # unless we use a more complex branch/join)
    # Let's branch them
    workflow.add_edge("financial_research", "industry_research")
    workflow.add_edge("industry_research", "synthesize")
    workflow.add_edge("synthesize", END)
    
    return workflow.compile()

# Singleton instance
research_workflow = create_research_workflow()
