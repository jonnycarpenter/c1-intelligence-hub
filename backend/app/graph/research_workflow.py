from langgraph.graph import StateGraph, END
from langgraph.types import Send
from typing import List, Union, Literal
from app.agents.research.state import DeepResearchState, QueryStatus
from app.agents.research.groomer import query_grooming_node
from app.agents.research.financial import financial_research_node
from app.agents.research.industry import industry_research_node
from app.agents.research.synthesizer import synthesis_node
from app.agents.research.category import category_node
from app.agents.research.validator import validator_node
import logging

logger = logging.getLogger(__name__)


def route_after_groom(state: DeepResearchState) -> Union[List[Send], Literal["__end__"]]:
    """
    Route after grooming - either end early (clarification), or fan-out to parallel research.
    
    Returns:
        - "__end__": end workflow (needs clarification or failed)
        - List[Send]: fan-out to parallel research branches
    
    Note: We no longer loop back to "groom" - if grooming fails, we end the workflow.
    This prevents infinite loops.
    """
    brief = state.get("research_brief")
    
    # If grooming failed (no brief), end the workflow
    if not brief:
        logger.error("Grooming failed - no research_brief in state. Ending workflow.")
        logger.error(f"State errors: {state.get('errors', [])}")
        return END
        
    logger.info(f"Grooming complete. Status: {brief.status}")
    
    if brief.status == QueryStatus.NEEDS_CLARIFICATION:
        if state.get("clarification_count", 0) >= 2:
            logger.info("Max clarifications reached, forcing research")
            # Force research after 2 questions - fan out to both agents
            return [
                Send("financial_research", state),
                Send("industry_research", state),
            ]
        logger.info("Needs clarification, ending for user input")
        return END
    
    # Ready for research - fan out to both agents in parallel
    logger.info("Routing to parallel research (financial + industry)")
    return [
        Send("financial_research", state),
        Send("industry_research", state),
    ]


def create_research_workflow():
    """
    Create the Deep Research LangGraph workflow.
    
    Pipeline (Phase 3 - Parallel Execution):
    [Groomer] → [Financial + Industry (parallel)] → [Synthesizer] → [Category] → [Validator] → END
    
                          ┌─────────────────┐
                          │    Financial    │
    [Groom] ──► fan-out ──┤                 ├──► fan-in ──► [Synthesize] ──► [Category] ──► [Validate] ──► END
                          │    Industry     │
                          └─────────────────┘
    
    LangGraph Send API enables true parallel execution:
    - Both Financial and Industry agents run simultaneously 
    - Synthesizer waits for both to complete (fan-in via multiple incoming edges)
    - ~50% reduction in research phase time
    """
    workflow = StateGraph(DeepResearchState)
    
    # Add nodes
    workflow.add_node("groom", query_grooming_node)
    workflow.add_node("financial_research", financial_research_node)
    workflow.add_node("industry_research", industry_research_node)
    workflow.add_node("synthesize", synthesis_node)
    workflow.add_node("categorize", category_node)  # Phase 2: Sales intelligence layer
    workflow.add_node("validate", validator_node)   # Phase 2: Citation verification
    
    # Set entry point
    workflow.set_entry_point("groom")
    
    # --- PHASE 3: Parallel Execution with Send API ---
    # route_after_groom returns List[Send] for parallel fan-out, or END
    # Note: We removed the "groom" loop-back to prevent infinite loops
    workflow.add_conditional_edges(
        "groom",
        route_after_groom,
        {
            END: END,
            # Send targets (financial_research, industry_research) are handled dynamically by LangGraph
        }
    )
    
    # Fan-in: Both research nodes feed into synthesize
    # LangGraph automatically waits for all incoming edges before proceeding
    workflow.add_edge("financial_research", "synthesize")
    workflow.add_edge("industry_research", "synthesize")
    
    # Post-synthesis pipeline (sequential)
    workflow.add_edge("synthesize", "categorize")
    workflow.add_edge("categorize", "validate")
    workflow.add_edge("validate", END)
    
    return workflow.compile()

# Singleton instance
research_workflow = create_research_workflow()
