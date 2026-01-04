"""Industry Watcher Agent - ARCHIVED."""

from typing import Dict, Any, List
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from app.config.settings import settings

# This agent was retired in Dec 2025 and replaced by the Deep Research workflow.
# Preserved here for reference.

SYSTEM_PROMPT = """
You are the C1 Industry Watcher. Your goal is to track qualitative industry moves, 
market trends, and competitor activity.
"""

def create_industry_watcher():
    def industry_watcher(state: Dict[str, Any]):
        # Original logic involved qualitative news search and market signals
        return {"messages": [AIMessage(content="[Archived] Industry Watcher logic replaced by Deep Research.")]}
    return industry_watcher
