# MCP Agent Tools

✅ **This directory is for CONVERSATIONAL AGENT TOOLS**

## Purpose
These tools are exposed to LLM agents for interactive research, analysis, and data retrieval.

## NOT for Ingestion
If you are building a data collector for the ingestion pipeline, use `app/tools/` instead.

## Tool Categories

### Data Retrieval
- `corpus_query.py` - Query ingested articles from BigQuery
- `corpus_visuals.py` - Search article_images for charts, graphs, and visual assets (used by Visual Research agent)
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
- `pipeline_search.py` - Pipeline prospect search tools:
  - `search_companies` - Exa.ai semantic/broad company search
  - `find_similar_companies` - Exa.ai lookalike targeting
  - `search_companies_filtered` - **Apollo.io structured firmographic search** (location, employees, revenue filters)
  - `find_company_contacts` - Apollo.io contact discovery
  - `reveal_contact` - Apollo.io contact email reveal (1 credit)
- `document_extraction.py` - PDF/document extraction
- `image_extraction.py` - Visual content search
- `datasheets.py` - Product spec sheets from BigQuery
- `fmp_premium_news.py` - Premium financial news (Bloomberg, Benzinga, WSJ)

### Output Generation
- `visualization.py` - Chart/graph generation

## Adding New Tools
1. Create tool file: `app/mcp/tools/{tool_name}.py`
2. Implement as `@tool` decorated function or `StructuredTool`
3. Import in `app/mcp/server.py`
4. Update this README
