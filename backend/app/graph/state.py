"""Graph state definitions."""

from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langchain_core.messages import BaseMessage
import operator


class GraphState(TypedDict):
    """Main state for the agent workflow graph."""
    
    # Message history
    messages: Annotated[List[BaseMessage], operator.add]
    
    # Current user query
    query: str
    
    # Active agent/tab
    agent_type: str
    
    # User preferences for grounding
    preferences: Dict[str, Any]
    
    # Supply chain context
    supply_chain: str
    
    # Output chunks for streaming
    output_chunks: List[str]
    
    # Current step for UI
    current_step: Optional[str]
    
    # Whether we're done
    is_complete: bool
    
    # Error if any
    error: Optional[str]


class AgentState(TypedDict):
    """State for individual agents."""
    
    # Message history
    messages: Annotated[List[BaseMessage], operator.add]
    
    # Current query being processed
    query: str
    
    # Agent type identifier
    agent_type: str
    
    # Grounding context
    companies: List[str]
    materials: List[str]
    industries: List[str]
    exclusions: List[str]
    supply_chain: str
    
    # Intermediate results
    tool_results: List[Dict[str, Any]]
    
    # Final output
    response: Optional[str]
