"""Product Maven Agent - ARCHIVED."""

from typing import Dict, Any, List
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from app.config.settings import settings

# This agent was retired in Dec 2025 and replaced by the Deep Research workflow.
# Preserved here for reference.

SYSTEM_PROMPT = """
You are the C1 Product Maven. Your expertise is in product specifications, 
technical gaps, and catalog intelligence.
"""

def create_product_maven():
    def product_maven(state: Dict[str, Any]):
        # Original logic involved catalog tool calls and spec comparisons
        return {"messages": [AIMessage(content="[Archived] Product Maven logic replaced by Deep Research.")]}
    return product_maven
