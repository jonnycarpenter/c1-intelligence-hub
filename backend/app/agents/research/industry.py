from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.research.state import DeepResearchState, IndustryAgentOutput, IndustryFinding, Sentiment, Citation
from app.agents.research.progress import emit_progress_sync, ToolProgress
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
from app.config.settings import settings
from app.mcp.tools.exa_search import news_search, web_search, find_similar  # Exa for semantic search
from app.mcp.tools.corpus_query import query_corpus, get_market_signals
from app.mcp.tools.google_trends import get_google_trends
from app.mcp.tools.stocknews_api import (
    get_company_news,
    search_news_keyword,
    get_press_releases,
    get_trending_headlines,
)
from app.mcp.tools.timeseries_data import get_freight_rates
from app.utils.grounding import load_companies
import json
import time

# Composites industry trade publications for domain-filtered searches
COMPOSITES_TRADE_PUBLICATIONS = [
    "compositesworld.com",
    "reinforcedplastics.com",
    "jec-group.com",
    "compositesmanufacturingmagazine.com",
    "sae.org",
    "aviationweek.com",        # Aerospace
    "windpowermonthly.com",    # Wind energy
    "supplychain247.com",      # Supply chain
    "chemweek.com",            # Chemicals/resins
]

INDUSTRY_AGENT_SYSTEM_PROMPT = """
You are an Industry Research Agent specializing in the qualitative market reality of the composites industry. Your job is to track news, press releases, and demand signals. Based on the user's query, use the tools available to generate a response and output it in the IndustryAgentOutput schema.

## Your Responsibilities

1. MONITOR industry news, trade publications, and press releases
2. PRIORITY: Check the internal `query_corpus` FIRST for pre-ingested market intelligence
3. USE Exa.ai for semantic web search with trade publication filtering
4. USE StockNewsAPI tools for on-demand financial news retrieval:
   - `get_company_news`: News for specific public company tickers
   - `search_news_keyword`: Search by keyword for private companies, industry terms, materials
   - `get_press_releases`: Official company announcements
   - `get_trending_headlines`: Major market events with high coverage
5. USE Google Trends for demand signal validation (is interest rising/falling?)
6. TRACK competitor qualitative moves (partnerships, management changes, plant openings)
7. IDENTIFY demand signals and market sentiment
8. USE `get_freight_rates` for shipping cost spikes, logistics headwinds, and trade lane inflation
9. ANALYZE historical trends vs real-time developments

## Key Trade Publications (prioritize these sources)
- CompositesWorld, JEC Group, Reinforced Plastics (industry core)
- Aviation Week, SAE (aerospace)
- Wind Power Monthly (wind energy)
- Chemical Week (resins/materials)

## Extraction Guidelines

- Focus on QUALITATIVE shifts (new technology adoption, sustainability initiatives)
- Identify EVENT types (partnership, acquisition, facility opening, product launch)
- Gauge SENTIMENT (positive, neutral, negative)
- Note demand signals like "increasing interest in hydrogen storage" or "aerospace recovery"
- Cross-reference Google Trends data to validate "hot" topics

## Output Format
Always respond with valid JSON matching the IndustryAgentOutput schema.
"""

def _resolve_tickers_from_query(query: str, companies_df) -> List[str]:
    """
    Resolve company names in query to stock tickers using the companies database.
    Returns list of tickers found.
    """
    tickers = []
    query_lower = query.lower()
    
    for _, row in companies_df.iterrows():
        company_name = row.get('company', '').lower()
        ticker = row.get('stock_ticker', '')
        
        # Check if company name or ticker is in query
        if company_name and company_name in query_lower:
            if ticker:
                tickers.append(ticker)
        elif ticker and ticker.lower() in query_lower:
            tickers.append(ticker)
    
    return list(set(tickers))  # Deduplicate


def _extract_keywords_for_trends(query: str, brief) -> List[str]:
    """
    Extract relevant keywords from query for Google Trends analysis.
    Returns up to 5 keywords (Google Trends limit).
    """
    keywords = []
    
    # Add entities from the research brief
    if brief and brief.entities_to_track:
        keywords.extend(brief.entities_to_track[:3])
    
    # Common composites industry terms to check if in query
    industry_terms = [
        "carbon fiber", "prepreg", "composites", "epoxy", "resin",
        "fiberglass", "wind turbine", "aerospace composites", "automotive composites",
        "hydrogen storage", "evtol", "thermoplastic", "cfrp"
    ]
    
    query_lower = query.lower()
    for term in industry_terms:
        if term in query_lower and term not in keywords:
            keywords.append(term)
            if len(keywords) >= 5:
                break
    
    return keywords[:5]  # Google Trends max


def _rank_results_by_relevance(raw_results: List[Dict], original_query: str) -> List[Dict]:
    """
    Rank raw results by relevance to the original query.
    Prioritizes: corpus > trade publications > general news.
    """
    # Priority scores by source type
    source_priority = {
        "corpus": 10,
        "exa_trade_pubs": 9,
        "market_signals": 8,
        "exa_news": 7,
        "stocknews_company": 6,
        "stocknews_press_releases": 6,
        "stocknews_keyword": 5,
        "stocknews_trending": 4,
        "google_trends": 3,
    }
    
    # Score each result
    for result in raw_results:
        source = result.get("source", "")
        base_score = source_priority.get(source, 1)
        
        # Boost if query terms appear in content
        content_str = str(result.get("content", "")).lower()
        query_terms = original_query.lower().split()
        term_matches = sum(1 for term in query_terms if term in content_str)
        
        result["_relevance_score"] = base_score + (term_matches * 0.5)
    
    # Sort by relevance score descending
    ranked = sorted(raw_results, key=lambda x: x.get("_relevance_score", 0), reverse=True)
    
    # Remove temp score field
    for r in ranked:
        r.pop("_relevance_score", None)
    
    return ranked


async def industry_research_node(state: DeepResearchState) -> Dict[str, Any]:
    """
    Industry research node. Executes queries against news and market signal tools.
    
    Returns PARTIAL STATE dict with only the fields this node updates.
    This is required for LangGraph's Send API parallel execution.
    
    Tool execution order:
    1. Internal corpus (fastest, pre-classified)
    2. Exa web search with trade publication filtering
    3. Exa news search for current events
    4. StockNewsAPI for financial news
    5. Google Trends for demand signal validation
    """
    start_time = time.time()
    llm = create_resilient_llm_with_openai_fallback(
        primary_model=settings.deep_research_industry_model,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        temperature=0,
    )
    
    brief = state["research_brief"]
    if not brief or not brief.industry_agent_queries:
        return {
            "current_status": "industry_research_skipped",
            "errors": [],
        }
    
    # Load companies for ticker resolution
    companies_df = load_companies()
    
    queries_executed = []
    raw_results = []
    errors = []  # Local errors list for partial state return
    
    # Collect all tickers mentioned across queries for batch processing
    all_resolved_tickers = set()
    
    for q in brief.industry_agent_queries:
        queries_executed.append(q)
        
        # Resolve company names to tickers
        resolved_tickers = _resolve_tickers_from_query(q, companies_df)
        all_resolved_tickers.update(resolved_tickers)
        
        # 1. CORPUS QUERY (Priority - check internal intelligence first)
        emit_progress_sync(ToolProgress(tool_name="corpus", message="Searching internal intelligence", query=q[:50]))
        try:
            results = query_corpus.invoke({"query": q, "limit": 15, "hours": 8760})
            raw_results.append({"query": q, "source": "corpus", "content": results})
        except Exception as e:
            errors.append({"node": "industry_research", "query": q, "error": f"Corpus query: {str(e)}"})
        
        # 2. EXA WEB SEARCH - Trade publications (domain-filtered for high-quality industry content)
        emit_progress_sync(ToolProgress(tool_name="exa_trade_pubs", message="Searching trade publications"))
        try:
            trade_pub_results = web_search.invoke({
                "query": q,
                "max_results": 10,
                "search_depth": "advanced",
                "time_range": "month",
                "include_domains": COMPOSITES_TRADE_PUBLICATIONS,
            })
            raw_results.append({"query": q, "source": "exa_trade_pubs", "content": trade_pub_results})
        except Exception as e:
            errors.append({"node": "industry_research", "query": q, "error": f"Exa trade pubs: {str(e)}"})
        
        # 3. EXA NEWS SEARCH (general news with reliable dates)
        emit_progress_sync(ToolProgress(tool_name="exa_news", message="Searching recent news"))
        try:
            news_results = news_search.invoke({"query": q, "max_results": 10, "time_range": "week"})
            raw_results.append({"query": q, "source": "exa_news", "content": news_results})
        except Exception as e:
            errors.append({"node": "industry_research", "query": q, "error": f"Exa news: {str(e)}"})
        
        # 4. MARKET SIGNALS (aggregated signals from corpus)
        emit_progress_sync(ToolProgress(tool_name="market_signals", message="Analyzing market signals"))
        try:
            industry_filter = None
            for ind in ["aerospace", "automotive", "wind", "marine", "defense"]:
                if ind in q.lower():
                    industry_filter = ind
                    break
            results = get_market_signals.invoke({"industry": industry_filter})
            raw_results.append({"query": q, "source": "market_signals", "content": results})
        except Exception as e:
            pass  # Non-critical
        
        # 5. STOCKNEWS KEYWORD SEARCH (for industry terms, private companies)
        emit_progress_sync(ToolProgress(tool_name="stocknews_keyword", message="Searching news by keyword"))
        try:
            keyword_result = search_news_keyword.invoke({"keyword": q, "days": 60, "items": 15})
            raw_results.append({"query": q, "source": "stocknews_keyword", "content": keyword_result})
        except Exception as e:
            errors.append({"node": "industry_research", "query": q, "error": f"StockNews keyword: {str(e)}"})
    
    # 6. STOCKNEWS COMPANY NEWS (batch for all resolved tickers)
    all_tickers = list(all_resolved_tickers)
    if all_tickers:
        emit_progress_sync(ToolProgress(tool_name="stocknews_company", message=f"Fetching company news for {', '.join(all_tickers[:3])}{'...' if len(all_tickers) > 3 else ''}"))
        try:
            company_news = get_company_news.invoke({"tickers": all_tickers[:10], "days": 30, "items": 20})
            raw_results.append({"query": "resolved_tickers", "source": "stocknews_company", "content": company_news, "tickers": all_tickers[:10]})
        except Exception as e:
            errors.append({"node": "industry_research", "error": f"StockNews company news: {str(e)}"})
        
        emit_progress_sync(ToolProgress(tool_name="stocknews_press_releases", message="Fetching press releases"))
        try:
            pr_result = get_press_releases.invoke({"tickers": all_tickers[:10], "days": 60, "items": 15})
            raw_results.append({"query": "resolved_tickers", "source": "stocknews_press_releases", "content": pr_result, "tickers": all_tickers[:10]})
        except Exception as e:
            errors.append({"node": "industry_research", "error": f"StockNews press releases: {str(e)}"})
    
    # 7. GOOGLE TRENDS (demand signal validation)
    emit_progress_sync(ToolProgress(tool_name="google_trends", message="Checking Google Trends for demand signals"))
    try:
        trends_keywords = _extract_keywords_for_trends(brief.original_query, brief)
        if trends_keywords:
            trends_result = get_google_trends.invoke({
                "keywords": trends_keywords,
                "timeframe": "today 3-m",
                "geo": "US"
            })
            raw_results.append({"query": brief.original_query, "source": "google_trends", "content": trends_result, "keywords": trends_keywords})
    except Exception as e:
        errors.append({"node": "industry_research", "error": f"Google Trends: {str(e)}"})
    
    # 8. TRENDING HEADLINES (once, not per query)
    try:
        trending_result = get_trending_headlines.invoke({"items": 10})
        raw_results.append({"query": "trending", "source": "stocknews_trending", "content": trending_result})
    except Exception as e:
        pass  # Non-critical
    
    # 9. FREIGHT INTELLIGENCE (if query mentions shipping, logistics, freight, ports, containers)
    if any(kw in brief.original_query.lower() for kw in ["ship", "freight", "logistics", "port", "container", "cost", "lane"]):
        try:
            # Check for specific lanes mentioned
            target_lane = None
            for lane in ["Shanghai", "Rotterdam", "Genoa", "Los Angeles", "New York"]:
                if lane.lower() in brief.original_query.lower():
                    target_lane = lane
                    break
            
            freight_result = get_freight_rates.invoke({"lane": target_lane, "days": 60})
            raw_results.append({"query": "freight_intelligence", "source": "freight_rates", "content": freight_result})
        except Exception as e:
            pass  # Non-critical
    
    # Rank results by relevance before truncation
    ranked_results = _rank_results_by_relevance(raw_results, brief.original_query)
    
    # Take top results (now ranked by relevance, not arbitrary order)
    top_results = ranked_results[:15]
    
    # Ask LLM to synthesize industry findings
    extraction_prompt = f"""
Based on the following raw research results for the query '{brief.original_query}', 
extract structured industry findings and demand signals.

RESEARCH CONTEXT:
- Original Query: {brief.original_query}
- Clarified Intent: {brief.clarified_intent}
- Timeframe: {brief.timeframe}
- Entities to Track: {brief.entities_to_track}

RAW RESULTS (ranked by relevance):
{json.dumps(top_results, indent=2, default=str)}

INSTRUCTIONS:
1. Prioritize findings from trade publications and internal corpus
2. Cross-reference Google Trends data to validate demand signals
3. Note any conflicting information in the warnings field
4. Include tickers resolved: {list(all_resolved_tickers) if all_resolved_tickers else 'None'}

Respond ONLY with a JSON object matching this EXACT schema:

{{
  "status": "complete" | "partial" | "failed",
  "queries_executed": ["list of query strings executed"],
  "findings": [
    {{
      "finding_id": "ind_001",
      "finding": "Specific finding statement with details",
      "event_type": "market_expansion|new_product|partnership|regulatory|contract|supply_chain|demand_signal|competitive_move|technology_trend",
      "sentiment": "positive" | "neutral" | "negative",
      "confidence": "high" | "medium" | "low",
      "relevance_score": 0.0 to 1.0,
      "citation": {{
        "source_type": "trade_publication|industry_news|press_release|earnings_call|sec_10k|sec_10q|financial_news",
        "source_title": "Article or document title",
        "source_url": "URL if available or null",
        "source_date": "YYYY-MM-DD or null",
        "page_or_section": "Section reference or null",
        "direct_quote": "Exact quote if available or null"
      }},
      "entities_mentioned": ["Company", "Product", "Technology"],
      "is_historical": false,
      "importance": "high" | "medium" | "low"
    }}
  ],
  "demand_signals": {{
    "signal_name": "description of signal and evidence"
  }} or null,
  "competitive_landscape_shifts": ["List of competitive changes observed"],
  "data_gaps": ["List of information that could not be found"],
  "warnings": ["List of any data quality or reliability concerns"]
}}

IMPORTANT:
- Each finding MUST have finding_id (e.g., "ind_001", "ind_002")
- sentiment MUST be lowercase: "positive", "neutral", or "negative"
- confidence and importance MUST be lowercase: "high", "medium", or "low"
- relevance_score MUST be a decimal between 0.0 and 1.0
- is_historical MUST be a boolean (true/false)
- All lists MUST be arrays, even if empty []
"""
    
    messages = [
        SystemMessage(content=INDUSTRY_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=extraction_prompt)
    ]
    
    response = await llm.ainvoke(messages)
    
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        output_data = json.loads(content)
        industry_output = IndustryAgentOutput(**output_data)
        
        industry_output.queries_executed = queries_executed
        
        # Return PARTIAL STATE - only fields this node updates
        # This is required for LangGraph's Send API parallel merge
        return {
            "industry_output": industry_output,
            "current_status": "industry_research_complete",
            "errors": errors,
        }
        
    except Exception as e:
        errors.append({"node": "industry_research_synthesis", "error": str(e)})
        # Return PARTIAL STATE on failure
        return {
            "current_status": "industry_research_failed",
            "errors": errors,
        }
