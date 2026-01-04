"""Market Scout Agent - ARCHIVED."""

from typing import Dict, Any, List
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from app.config.settings import settings

# This agent was retired in Dec 2025 and replaced by the Deep Research workflow.
# Preserved here for reference.

SYSTEM_PROMPT = """
You are the C1 Market Scout. Your job is to perform deep financial and market analysis, 
focusing on numbers, trends, and projections.
"""

def create_market_scout():
    def market_scout(state: Dict[str, Any]):
        # Original logic involved financial tool calls and market data extraction
        return {"messages": [AIMessage(content="[Archived] Market Scout logic replaced by Deep Research.")]}
    return market_scout
