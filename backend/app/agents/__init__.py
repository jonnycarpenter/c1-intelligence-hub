"""Agents module."""

# New multi-agent research workflow is located in the 'research' sub-package
# Legacy agents (industry_watcher, market_scout, product_maven) have been retired.

from .research.state import SynthesisAgentOutput
from .research.groomer import query_grooming_node
from .research.financial import financial_research_node
from .research.industry import industry_research_node
from .research.synthesizer import synthesis_node

__all__ = [
    "query_grooming_node",
    "financial_research_node",
    "industry_research_node",
    "synthesis_node",
    "SynthesisAgentOutput",
]
