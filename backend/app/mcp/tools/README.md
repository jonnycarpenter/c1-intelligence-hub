# MCP Agent Tools

✅ **This directory is for CONVERSATIONAL AGENT TOOLS**

## Purpose
These tools are exposed to LLM agents for interactive research, analysis, and data retrieval.

## NOT for Ingestion
If you are building a data collector for the ingestion pipeline, use `app/tools/` instead.

## Tool Categories

### Data Retrieval
- `corpus_query.py` - Query ingested articles from BigQuery
- `timeseries_data.py` - Historical data queries
- `data_management.py` - Company/material tracker CRUD

### External Search
- `exa_search.py` - Web search via Exa.ai
- `tavily_search.py` - Web search via Tavily
- `google_trends.py` - Search trends analysis
- `stocknews_api.py` - On-demand news retrieval (instrumented with retries/metrics)

### Specialized Research
- `api_ninja_earnings.py` - Earnings transcript search
- `product_intelligence.py` - Product catalog queries
- `pipeline_search.py` - Pipeline prospect search
- `document_extraction.py` - PDF/document extraction
- `image_extraction.py` - Visual content search

### Output Generation
- `visualization.py` - Chart/graph generation

## Adding New Tools
1. Create tool file: `app/mcp/tools/{tool_name}.py`
2. Implement as `@tool` decorated function or `StructuredTool`
3. Import in `app/mcp/server.py`
4. Update this README
