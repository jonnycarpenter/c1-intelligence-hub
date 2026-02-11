"""
Supply Chain Agent — LLM-Powered Supply Network Queries
=======================================================

Interprets natural language supply chain questions and uses ImportYeti
tools + BigQuery cached data to return structured answers.

Pattern: User query → Claude tool-calling loop → structured JSON result

Tools available:
  1. search_supply_chain_entity (0 credits) — find by name
  2. get_company_supply_chain (1 credit) — full supplier network
  3. get_supplier_customers (1 credit) — full buyer network
  4. query_supply_chain_db (0 credits) — query cached data

Usage:
    agent = SupplyChainAgent()
    async for event in agent.query_stream("Who are Hexcel's top suppliers?"):
        # event is {"type": "progress"|"result"|"error", ...}
"""

import json
import time
import asyncio
import logging
from typing import AsyncIterator, Dict, Any, Optional

from app.config.settings import settings
from app.utils.resilient_llm import get_resilient_async_client

logger = logging.getLogger(__name__)

# ─── Tool Definitions (Anthropic tool_use format) ────────

TOOLS = [
    {
        "name": "search_supply_chain_entity",
        "description": (
            "Search ImportYeti for a company (US importer) or supplier (overseas exporter) "
            "by name. Returns matching candidates with slugs, shipment counts, and cache status. "
            "Costs 0 API credits. ALWAYS call this first to identify the correct entity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Company or supplier name to search for (e.g., 'Hexcel', 'Toray')",
                },
                "entity_type": {
                    "type": "string",
                    "enum": ["company", "supplier", "auto"],
                    "description": "Search type. 'company' for US importers, 'supplier' for overseas exporters, 'auto' for both.",
                    "default": "auto",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_company_supply_chain",
        "description": (
            "Fetch the full supplier network for a US company. Costs 1 API credit. "
            "Results are cached in BigQuery for future free lookups. "
            "Use search_supply_chain_entity first to find the correct slug."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "ImportYeti company slug (e.g., 'hexcel-corporation'). Get from search results.",
                },
                "max_suppliers": {
                    "type": "integer",
                    "description": "Maximum suppliers to return. Default 50.",
                    "default": 50,
                },
            },
            "required": ["slug"],
        },
    },
    {
        "name": "get_supplier_customers",
        "description": (
            "Fetch the full buyer (US importer) network for an overseas supplier. "
            "Costs 1 API credit. Reveals which US companies buy from this supplier. "
            "Use search_supply_chain_entity first to find the correct slug."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "ImportYeti supplier slug (e.g., 'jushi-group-co-ltd'). Get from search results.",
                },
                "max_buyers": {
                    "type": "integer",
                    "description": "Maximum buyers to return. Default 50.",
                    "default": 50,
                },
            },
            "required": ["slug"],
        },
    },
    {
        "name": "query_supply_chain_db",
        "description": (
            "Query cached ImportYeti data in BigQuery. Costs 0 credits. "
            "Use this to check existing data before spending API credits."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": [
                        "company_suppliers", "supplier_buyers",
                        "shared_suppliers", "shared_suppliers_12m",
                        "company_profile", "supplier_profile",
                        "search_by_name", "stats",
                        "competitor_activity",
                    ],
                    "description": "Type of query to run.",
                },
                "entity_key": {
                    "type": "string",
                    "description": "ImportYeti key (e.g., 'company/hexcel-corporation'). Required for profile/relationship queries.",
                },
                "name": {
                    "type": "string",
                    "description": "Entity name for search_by_name queries.",
                },
            },
            "required": ["query_type"],
        },
    },
]

SYSTEM_PROMPT = """You are a supply chain intelligence analyst for Composites One (C1), the largest composites distributor in North America.

You have access to US customs/import data via ImportYeti to answer questions about supplier and buyer relationships.

TRACKED COMPANIES (data is pre-cached, 0 credits to query):
- Composites One (C1) — target company
- Hexcel (HXL), Toray, Solvay (SOLB), Huntsman (HUN), Owens Corning (OC)
- Gurit (GUR), Teijin, Mitsubishi Chemical, SGL Carbon, Jushi Group

WORKFLOW:
1. For tracked companies: Use query_supply_chain_db first (0 credits) — data is cached
2. For unknown companies: Use search_supply_chain_entity (0 credits) to find them, then get_company_supply_chain or get_supplier_customers (1 credit each) to fetch data
3. Always prefer cached data over API calls to conserve credits

RESPONSE FORMAT:
After gathering data, respond with a JSON object:
{
    "answer": "Natural language summary of findings",
    "entity_type": "company" or "supplier" or "general",
    "entity_name": "Resolved company/supplier name",
    "entity_key": "ImportYeti key if found",
    "relationships": [array of supplier or buyer records],
    "summary_stats": {counts, top countries, etc.},
    "not_found": false,
    "not_found_message": null
}

If the company/supplier cannot be found:
{
    "answer": null,
    "not_found": true,
    "not_found_message": "We couldn't find [name] in our supply chain database or ImportYeti trade records. This could mean they don't have significant US import/export activity."
}

IMPORTANT:
- Keep answers concise and focused on the supply chain data
- Include key metrics: supplier/buyer counts, top countries, shipment volumes
- Highlight if any relationships involve C1 or tracked competitors
- Your final message MUST be valid JSON matching the schema above"""


class SupplyChainAgent:
    """LLM agent for natural language supply chain queries."""

    MAX_TOOL_ITERATIONS = 5
    TIMEOUT_SECONDS = 60

    def __init__(self):
        self.client = get_resilient_async_client(
            anthropic_api_key=settings.anthropic_api_key,
            gemini_api_key=getattr(settings, 'gemini_api_key', None),
        )

    async def query_stream(self, query: str) -> AsyncIterator[Dict[str, Any]]:
        """Stream progress events and final result for a supply chain query.

        Yields:
            {"type": "progress", "step": str, "tool": str}
            {"type": "result", "data": {...}}
            {"type": "error", "message": str}
        """
        start_time = time.time()
        logger.info(f"[SUPPLY_CHAIN_AGENT] Query START: {query[:100]}")

        messages = [{"role": "user", "content": query}]

        try:
            for iteration in range(self.MAX_TOOL_ITERATIONS):
                logger.info(f"[SUPPLY_CHAIN_AGENT] Iteration {iteration + 1}/{self.MAX_TOOL_ITERATIONS}")

                response = await asyncio.wait_for(
                    self.client.messages_create(
                        model="claude-sonnet-4-5",
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        tools=TOOLS,
                        messages=messages,
                    ),
                    timeout=self.TIMEOUT_SECONDS,
                )

                # Check if response has tool_use blocks
                tool_uses = [
                    block for block in response.content
                    if block.type == "tool_use"
                ]

                if not tool_uses:
                    # Final text response — extract JSON
                    text_blocks = [
                        block.text for block in response.content
                        if block.type == "text"
                    ]
                    final_text = " ".join(text_blocks).strip()

                    try:
                        # Try to parse JSON from the response
                        result = self._extract_json(final_text)
                        elapsed = time.time() - start_time
                        logger.info(f"[SUPPLY_CHAIN_AGENT] Query COMPLETE: {elapsed:.2f}s, found={not result.get('not_found', False)}")
                        yield {"type": "result", "data": result}
                    except Exception as parse_err:
                        logger.warning(f"[SUPPLY_CHAIN_AGENT] JSON parse error: {parse_err}")
                        # Return the raw text as the answer
                        yield {
                            "type": "result",
                            "data": {
                                "answer": final_text,
                                "entity_type": "general",
                                "not_found": False,
                            },
                        }
                    return

                # Execute tool calls
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use.name
                    tool_input = tool_use.input

                    # Emit progress event
                    step_label = self._get_step_label(tool_name, tool_input)
                    yield {"type": "progress", "step": step_label, "tool": tool_name}

                    # Execute the tool
                    logger.info(f"[SUPPLY_CHAIN_AGENT] Tool START: {tool_name}({json.dumps(tool_input)[:200]})")
                    tool_start = time.time()

                    try:
                        result_str = await self._execute_tool(tool_name, tool_input)
                        tool_elapsed = time.time() - tool_start
                        logger.info(f"[SUPPLY_CHAIN_AGENT] Tool COMPLETE: {tool_name} in {tool_elapsed:.2f}s")
                    except Exception as tool_err:
                        tool_elapsed = time.time() - tool_start
                        logger.error(f"[SUPPLY_CHAIN_AGENT] Tool FAILED: {tool_name} in {tool_elapsed:.2f}s — {tool_err}", exc_info=True)
                        result_str = json.dumps({"error": str(tool_err)})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result_str,
                    })

                # Add assistant message (with tool_use blocks) and tool results
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            # If we exhausted iterations
            elapsed = time.time() - start_time
            logger.warning(f"[SUPPLY_CHAIN_AGENT] Max iterations reached in {elapsed:.2f}s")
            yield {
                "type": "result",
                "data": {
                    "answer": "I found some information but couldn't complete the full analysis. Please try a more specific query.",
                    "entity_type": "general",
                    "not_found": False,
                },
            }

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"[SUPPLY_CHAIN_AGENT] Query TIMEOUT: {elapsed:.2f}s")
            yield {"type": "error", "message": "Search timed out. Please try again."}

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[SUPPLY_CHAIN_AGENT] Query ERROR: {e} in {elapsed:.2f}s", exc_info=True)
            yield {"type": "error", "message": str(e)}

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a supply chain MCP tool and return the string result."""
        from app.mcp.tools.supply_chain import (
            search_supply_chain_entity,
            get_company_supply_chain,
            get_supplier_customers,
            query_supply_chain_db,
        )

        if tool_name == "search_supply_chain_entity":
            return await search_supply_chain_entity.ainvoke(tool_input)
        elif tool_name == "get_company_supply_chain":
            return await get_company_supply_chain.ainvoke(tool_input)
        elif tool_name == "get_supplier_customers":
            return await get_supplier_customers.ainvoke(tool_input)
        elif tool_name == "query_supply_chain_db":
            return await query_supply_chain_db.ainvoke(tool_input)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def _get_step_label(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Human-readable progress step label."""
        name = tool_input.get("name", tool_input.get("slug", ""))
        if tool_name == "search_supply_chain_entity":
            return f"Searching for \"{name}\"..."
        elif tool_name == "get_company_supply_chain":
            return f"Fetching supplier network for {name}..."
        elif tool_name == "get_supplier_customers":
            return f"Fetching buyer network for {name}..."
        elif tool_name == "query_supply_chain_db":
            qt = tool_input.get("query_type", "")
            if qt == "company_suppliers":
                return "Looking up cached supplier data..."
            elif qt == "supplier_buyers":
                return "Looking up cached buyer data..."
            elif qt == "search_by_name":
                return f"Searching database for \"{tool_input.get('name', '')}\"..."
            else:
                return f"Querying database ({qt})..."
        return f"Running {tool_name}..."

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response text."""
        # Try parsing the whole text as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        import re
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Try finding JSON object in text
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            return json.loads(text[brace_start : brace_end + 1])

        raise ValueError("No JSON found in response")
