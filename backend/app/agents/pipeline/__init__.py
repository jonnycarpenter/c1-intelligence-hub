"""
Pipeline Agent Module - AI-powered prospect discovery.
"""

from .agent import pipeline_agent, PipelineAgent, get_pipeline_agent
from .state import (
    PipelineAgentState,
    PipelineAgentResponse,
    SearchBlock,
    ProspectResult,
    ContactResult,
    TriggerEventResult,
    create_initial_state,
)

__all__ = [
    "pipeline_agent",
    "PipelineAgent",
    "get_pipeline_agent",
    "PipelineAgentState",
    "PipelineAgentResponse",
    "SearchBlock",
    "ProspectResult",
    "ContactResult",
    "TriggerEventResult",
    "create_initial_state",
]
