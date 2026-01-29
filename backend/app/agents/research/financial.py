from typing import Dict, Any, List, Optional, Set
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.research.state import DeepResearchState, FinancialAgentOutput, FinancialFinding, ConfidenceLevel, SourceType, Citation
from app.agents.research.progress import emit_progress_sync, ToolProgress, get_tool_description
from app.utils.resilient_llm import create_resilient_llm_with_openai_fallback
from app.config.settings import settings
from app.mcp.tools.api_ninja_earnings import get_earnings_transcript_ninja, search_earnings_keywords
from app.mcp.tools.corpus_query import query_corpus
from app.mcp.tools.stocknews_api import (
    get_company_news,
    get_press_releases,
    get_analyst_ratings,
    get_sentiment_summary,
)
from app.tools.sec_filings.collector import SECFilingCollector
from app.utils.grounding import load_companies
import json
import time
import logging
import re

logger = logging.getLogger(__name__)


def _extract_urls_from_tool_output(content: str, source_type: str) -> List[str]:
    """
    Extract URLs from tool output content. Different tools return URLs in different structures.
    Returns a list of URLs found in the content.
    """
    urls = []
    if not content:
        return urls
    
    try:
        # Try to parse as JSON
        data = json.loads(content) if isinstance(content, str) else content
        
        # Handle different tool output structures
        if isinstance(data, dict):
            # StockNews API: {articles: [{url: ...}, ...]}
            articles = data.get("articles", [])
            for article in articles:
                if article.get("url"):
                    urls.append(article["url"])
            
            # Corpus query: {items: [{url: ...}, ...]} or direct list
            items = data.get("items", [])
            for item in items:
                if item.get("url"):
                    urls.append(item["url"])
            
            # Direct URL field
            if data.get("url"):
                urls.append(data["url"])
            
        elif isinstance(data, list):
            # Direct list of results (corpus query format)
            for item in data:
                if isinstance(item, dict) and item.get("url"):
                    urls.append(item["url"])
                    
    except (json.JSONDecodeError, TypeError):
        # Not JSON - try regex to extract URLs
        url_pattern = r'https?://[^\s"<>]+'
        urls = re.findall(url_pattern, str(content))
    
    return urls[:10]  # Limit to 10 URLs to avoid noise


def _enrich_raw_results_with_urls(raw_results: List[Dict]) -> List[Dict]:
    """
    Process raw_results to extract URLs from content and add them at the top level.
    This makes URLs more visible to the LLM for citation extraction.
    """
    enriched = []
    for result in raw_results:
        result_copy = result.copy()
        
        # If already has top-level URL, keep it
        if result_copy.get("url"):
            enriched.append(result_copy)
            continue
        
        # Try to extract URLs from content
        content = result_copy.get("content", "")
        urls = _extract_urls_from_tool_output(content, result_copy.get("source", ""))
        
        if urls:
            result_copy["urls"] = urls
            result_copy["url"] = urls[0]  # Primary URL for easy access
        
        enriched.append(result_copy)
    
    return enriched


def _truncate_result_content(results: list, max_chars: int = 3000) -> list:
    """Truncate content in each result to avoid exceeding token limits."""
    truncated = []
    for r in results:
        r_copy = r.copy()
        content = r_copy.get("content", "")
        if isinstance(content, str) and len(content) > max_chars:
            r_copy["content"] = content[:max_chars] + "... [truncated]"
        elif isinstance(content, (dict, list)):
            content_str = json.dumps(content, default=str)
            if len(content_str) > max_chars:
                r_copy["content"] = content_str[:max_chars] + "... [truncated]"
        truncated.append(r_copy)
    return truncated


def _repair_truncated_json(content: str) -> str:
    """Attempt to repair truncated JSON by closing brackets/braces."""
    # Count open brackets
    open_braces = content.count('{') - content.count('}')
    open_brackets = content.count('[') - content.count(']')
    
    # Check for unclosed strings (odd number of unescaped quotes)
    # Simple heuristic: if we're in a string, close it
    in_string = False
    i = 0
    while i < len(content):
        if content[i] == '"' and (i == 0 or content[i-1] != '\\'):
            in_string = not in_string
        i += 1
    
    repaired = content
    if in_string:
        repaired += '"'
    
    # Close arrays and objects
    repaired += ']' * open_brackets
    repaired += '}' * open_braces
    
    return repaired


def _resolve_all_tickers(queries: List[str], companies_df) -> Set[str]:
    """
    Resolve all company names mentioned across queries to stock tickers.
    Returns set of unique tickers found.
    """
    tickers = set()
    
    for q in queries:
        query_lower = q.lower()
        for _, row in companies_df.iterrows():
            company_name = row.get('company', '').lower()
            ticker = row.get('stock_ticker', '')
            
            if company_name and company_name in query_lower:
                if ticker:
                    tickers.add(ticker)
            elif ticker and ticker.lower() in query_lower:
                tickers.add(ticker)
    
    return tickers


def _has_specific_company_mention(original_query: str, entities_to_track: Optional[List[str]], companies_df) -> bool:
    """
    Determine if the user's query mentions specific companies/suppliers/OEMs.
    
    Used to gate external earnings API calls - we only fetch new transcripts
    if the user is asking about specific companies, not generic industry queries.
    
    Returns True if:
    - entities_to_track contains company names that match our master list
    - Original query mentions a known company name or ticker
    
    Returns False for generic queries like "wind energy trends" or "market outlook"
    """
    query_lower = original_query.lower()
    
    # Check entities extracted by groomer
    if entities_to_track:
        for entity in entities_to_track:
            entity_lower = entity.lower()
            # Check if entity matches a known company
            for _, row in companies_df.iterrows():
                company_name = row.get('company', '').lower()
                ticker = row.get('stock_ticker', '').lower()
                if company_name and (company_name in entity_lower or entity_lower in company_name):
                    return True
                if ticker and ticker == entity_lower:
                    return True
    
    # Check original query directly for company/ticker mentions
    for _, row in companies_df.iterrows():
        company_name = row.get('company', '').lower()
        ticker = row.get('stock_ticker', '').lower()
        if company_name and len(company_name) > 3 and company_name in query_lower:
            return True
        if ticker and len(ticker) >= 2 and ticker in query_lower.split():
            return True
    
    return False


def _classify_query_type(original_query: str, brief) -> dict:
    """
    Classify the query type to guide intelligent tool selection.
    
    Returns a dict with boolean flags indicating what type of research is needed:
    - needs_company_financials: User asking about specific companies' financials
    - needs_industry_outlook: User wants broad industry/market outlook
    - needs_competitive_intel: User wants competitive comparisons
    - needs_recent_news: User wants recent developments/news
    - needs_analyst_views: User asking about analyst ratings/sentiment
    
    This enables smart tool selection to avoid running every tool for every query.
    """
    query_lower = original_query.lower()
    entities = brief.entities_to_track if brief else []
    
    result = {
        "needs_company_financials": False,
        "needs_industry_outlook": False,
        "needs_competitive_intel": False,
        "needs_recent_news": False,
        "needs_analyst_views": False,
    }
    
    # Company-specific financial queries
    company_financial_keywords = [
        "revenue", "earnings", "profit", "margin", "guidance", "forecast",
        "10-k", "10-q", "8-k", "sec filing", "annual report", "quarterly",
        "eps", "ebitda", "cash flow", "balance sheet", "income statement",
        "capex", "capital expenditure", "dividend", "buyback"
    ]
    if any(kw in query_lower for kw in company_financial_keywords):
        result["needs_company_financials"] = True
    
    # Industry/market outlook queries
    outlook_keywords = [
        "outlook", "forecast", "projection", "trend", "market size",
        "industry", "sector", "growth rate", "cagr", "demand", "supply",
        "2025", "2026", "2027", "q1", "q2", "q3", "q4", "next year",
        "future", "expected", "anticipated", "predict"
    ]
    if any(kw in query_lower for kw in outlook_keywords):
        result["needs_industry_outlook"] = True
    
    # Competitive intelligence queries
    competitive_keywords = [
        "competitor", "competitive", "versus", "vs", "compare", "comparison",
        "market share", "position", "ranking", "leader", "player",
        "who is", "which company", "best", "top"
    ]
    if any(kw in query_lower for kw in competitive_keywords):
        result["needs_competitive_intel"] = True
    
    # Recent news/developments queries
    news_keywords = [
        "recent", "latest", "news", "announcement", "update", "new",
        "this week", "this month", "today", "yesterday", "breaking",
        "development", "happening", "current"
    ]
    if any(kw in query_lower for kw in news_keywords):
        result["needs_recent_news"] = True
    
    # Analyst views queries
    analyst_keywords = [
        "analyst", "rating", "upgrade", "downgrade", "price target",
        "recommendation", "buy", "sell", "hold", "sentiment", "opinion",
        "wall street", "coverage"
    ]
    if any(kw in query_lower for kw in analyst_keywords):
        result["needs_analyst_views"] = True
    
    # Default: If no specific type detected, enable broad research
    if not any(result.values()):
        result["needs_industry_outlook"] = True
        result["needs_recent_news"] = True
    
    return result


def _rank_financial_results(raw_results: List[Dict], original_query: str) -> List[Dict]:
    """
    Rank raw results by relevance for financial research.
    Prioritizes: SEC filings > earnings calls > analyst ratings > news.
    """
    source_priority = {
        "sec_10k": 10,
        "sec_10q": 10,
        "sec_8k": 9,
        "earnings_call": 9,
        "earnings_call_quotes": 10,  # High priority for keyword-matched quotes
        "corpus_earnings": 8,
        "stocknews_analyst_ratings": 7,
        "stocknews_sentiment": 6,
        "stocknews_press_releases": 5,
        "stocknews_company": 4,
    }
    
    for result in raw_results:
        source = result.get("source", "")
        base_score = source_priority.get(source, 1)
        
        # Boost if query terms appear in content
        content_str = str(result.get("content", "")).lower()
        query_terms = original_query.lower().split()
        term_matches = sum(1 for term in query_terms if term in content_str)
        
        result["_relevance_score"] = base_score + (term_matches * 0.5)
    
    ranked = sorted(raw_results, key=lambda x: x.get("_relevance_score", 0), reverse=True)
    
    for r in ranked:
        r.pop("_relevance_score", None)
    
    return ranked


def _extract_quote_keywords(original_query: str, financial_queries: Optional[List[str]]) -> List[str]:
    """
    Extract key topics from the user query for targeted earnings call keyword search.
    
    Returns a list of keywords that are likely to yield valuable executive quotes:
    - Industry/market terms (aerospace, wind, automotive)
    - Financial terms (revenue, margin, guidance)
    - Strategic terms (expansion, acquisition, capacity)
    - Material terms (carbon fiber, composites, resin)
    """
    keywords = []
    
    # Combine original query and financial queries for analysis
    all_text = original_query.lower()
    if financial_queries:
        all_text += " " + " ".join(q.lower() for q in financial_queries)
    
    # High-value keyword categories for executive quote extraction
    keyword_categories = {
        # Industry/market terms
        "aerospace": ["aerospace", "aircraft", "aviation", "narrowbody", "widebody", "commercial aircraft"],
        "wind": ["wind", "wind energy", "wind turbine", "renewable"],
        "automotive": ["automotive", "ev", "electric vehicle", "battery"],
        "defense": ["defense", "military", "dod"],
        # Financial terms
        "guidance": ["guidance", "outlook", "forecast", "expect", "projection"],
        "revenue": ["revenue", "sales", "growth", "quarterly", "annual"],
        "margin": ["margin", "profit", "profitability", "operating income"],
        "capex": ["capex", "capital expenditure", "investment", "capacity"],
        # Strategic terms
        "expansion": ["expansion", "facility", "new plant", "capacity"],
        "demand": ["demand", "orders", "backlog", "customer"],
        "competition": ["competition", "market share", "competitor"],
        # Material terms
        "carbon fiber": ["carbon fiber", "carbon fibre", "prepreg"],
        "composites": ["composite", "composites", "advanced materials"],
        "pricing": ["pricing", "price", "cost", "raw material"],
        "supply chain": ["supply chain", "supply", "manufacturing"],
    }
    
    # Find matching categories
    for category, terms in keyword_categories.items():
        if any(term in all_text for term in terms):
            # Add the matched term(s) as keywords
            for term in terms:
                if term in all_text and term not in keywords:
                    keywords.append(term)
                    break  # One term per category is enough
    
    # Add any company names mentioned (single words, >3 chars)
    words = all_text.split()
    company_indicators = ["hexcel", "toray", "solvay", "owens", "tpi", "boeing", "airbus", "vestas"]
    for word in words:
        if word in company_indicators and word not in keywords:
            keywords.append(word)
    
    # Fallback: If no specific keywords found, use generic financial terms
    if not keywords:
        keywords = ["guidance", "outlook", "demand", "growth"]
    
    return keywords[:8]  # Limit to 8 keywords

FINANCIAL_AGENT_SYSTEM_PROMPT = """
You are a Financial Research Agent specializing in the composites industry. Your job is to extract specific, data-driven financial insights AND verbatim executive quotes that ground those insights.

## Your Responsibilities

1. ANALYZE financial documents (SEC 10-K, 10-Q, 8-K, and Earnings Call Transcripts)
2. PRIORITY: Check the internal `query_corpus` FIRST for pre-ingested financial data and earnings
3. USE SEC filings for official metrics and risk factors
4. USE StockNewsAPI tools for real-time news, analyst ratings, and sentiment
5. EXTRACT key metrics, strategic outlooks, and financial headwinds
6. ATTRIBUTE every finding with a precise citation
7. **ALWAYS INCLUDE EXECUTIVE QUOTES** - The reader wants proof, not just summaries

## EXECUTIVE QUOTES ARE YOUR MOST VALUABLE OUTPUT

**Why Quotes Matter:**
Executive quotes from earnings calls are the "source of truth" that ground your analysis. They allow readers to:
- Verify your claims with the CEO's/CFO's exact words
- Understand context and nuance that summaries miss
- Quote executives in their own communications

**For EVERY company you analyze, extract 2-4 HIGH-IMPACT quotes:**

1. **Guidance/Outlook Quote** - What does the CEO expect going forward?
   > "We're raising our full-year revenue guidance to $2.1-2.2 billion, reflecting strong demand..."
   
2. **Market Demand Quote** - What are they seeing from customers?
   > "Build rates at Boeing continue to improve. We're now at 38 MAX aircraft per month..."
   
3. **Risk/Headwind Quote** - What concerns them?
   > "Raw material costs remain elevated, though we're seeing stabilization in Q4..."
   
4. **Strategic Priority Quote** - Where are they investing?
   > "We're accelerating our capacity expansion in wind, with the new facility coming online in Q2..."

**Quote Format in Citations:**
```json
{
  "direct_quote": "We continue to see strong demand across our Aerospace platform, particularly in narrowbody production which is up 15% year-over-year. — Nick Stanage, CEO, Hexcel Q3 2025 Earnings Call"
}
```

## Key Composites Industry Tickers
- Composites: HXL (Hexcel), OC (Owens Corning), TRYIY (Toray), SOLVY (Solvay), TPIC (TPI Composites)
- Aerospace: BA (Boeing), EADSY (Airbus), RTX, LMT, NOC, GE, GD
- Wind: VWDRY (Vestas), GEV (GE Vernova)

## Extraction Guidelines

- Focus on QUANTITATIVE metrics (revenue growth, margins, capital expenditure)
- Identify STRATEGIC commentary (M&A activity, facility expansions, new contract wins)
- Note RISK factors and headwinds (supply chain constraints, raw material pricing)
- **EVERY finding backed by earnings data should have a direct_quote in the citation**
- Findings without quotes are still valid if from SEC filings or news

## Confidence Scores
- HIGH: Has direct_quote from earnings call OR specific metrics from SEC filing
- MEDIUM: Paraphrased from earnings call, OR from analyst ratings/news
- LOW: Ambiguous statement, single-source, or potentially outdated information

## Output Format
Always respond with valid JSON matching the FinancialAgentOutput schema.
"""

async def financial_research_node(state: DeepResearchState) -> Dict[str, Any]:
    """
    Financial research node. Executes queries against SEC filings, earnings calls,
    and StockNewsAPI tools for comprehensive financial intelligence.
    
    Returns PARTIAL STATE dict with only the fields this node updates.
    This is required for LangGraph's Send API parallel execution.
    
    Improvements:
    - Batch ticker resolution from all queries upfront
    - Relevance-ranked results before LLM truncation
    - Enhanced extraction prompt with research context
    """
    start_time = time.time()
    logger.info(f"[FINANCIAL_RESEARCH] START - query: {state.get('user_query', '')[:50]}...")
    logger.info(f"[FINANCIAL_RESEARCH] State keys: {list(state.keys())}")
    
    llm = create_resilient_llm_with_openai_fallback(
        primary_model=settings.deep_research_financial_model,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        temperature=0,
        max_tokens=8192,  # Increased from default 4096 to prevent truncation
    )
    
    brief = state["research_brief"]
    if not brief or not brief.financial_agent_queries:
        return {
            "current_status": "financial_research_skipped",
            "errors": [],
        }
        
    queries_executed = []
    raw_results = []
    errors = []  # Local errors list for partial state return
    
    # Load companies for ticker resolution
    companies_df = load_companies()
    
    # =========================================================================
    # STEP 0: Check if user mentioned specific companies
    # Only call external earnings API if specific companies are mentioned
    # Corpus queries (local) always run; external API calls are conditional
    # =========================================================================
    has_company_mention = _has_specific_company_mention(
        brief.original_query,
        brief.entities_to_track,
        companies_df
    )
    if has_company_mention:
        logger.info(f"Financial agent: Specific company mentioned - will fetch external earnings transcripts")
    else:
        logger.info(f"Financial agent: Generic query - skipping external earnings API, using corpus only")
    
    # =========================================================================
    # STEP 0b: Classify query type for intelligent tool selection
    # This guides which tools to run based on what the user is actually asking
    # =========================================================================
    query_type = _classify_query_type(brief.original_query, brief)
    logger.info(f"Financial agent: Query type classification: {query_type}")
    
    # =========================================================================
    # STEP 1: Batch Ticker Resolution
    # Resolve all tickers mentioned across all queries upfront for efficient API usage
    # =========================================================================
    all_tickers = _resolve_all_tickers(brief.financial_agent_queries, companies_df)
    
    # =========================================================================
    # STEP 2: Execute Corpus Queries (Query-Specific)
    # Check internal corpus first for pre-ingested earnings and financial data
    # =========================================================================
    emit_progress_sync(ToolProgress(tool_name="corpus_earnings", message="Searching internal earnings data..."))
    for q in brief.financial_agent_queries:
        queries_executed.append(q)
        
        # Query local corpus for earnings data (1 year lookback for deep research)
        try:
            corpus_res = query_corpus.invoke({"query": q, "category": "earnings", "limit": 10, "hours": 8760})
            if corpus_res and str(corpus_res).strip():
                raw_results.append({"query": q, "source": "corpus_earnings", "content": corpus_res})
        except Exception as e:
            pass  # Corpus miss is not critical
    
    # =========================================================================
    # STEP 3: SEC Filings and External Earnings Calls (Per Ticker)
    # - SEC filings: Always fetch for resolved tickers
    # - External Earnings API: Only if user mentioned specific companies
    #   (Corpus already queried in Step 2 - that's always allowed)
    # =========================================================================
    for ticker in all_tickers:
        # SEC Filings - official 10-K, 10-Q, 8-K filings (always fetch)
        emit_progress_sync(ToolProgress(tool_name="sec_filings", message=f"Fetching SEC filings for {ticker}", ticker=ticker))
        try:
            collector = SECFilingCollector()
            sec_results = collector.collect_for_company(company_id=ticker, ticker=ticker)
            for f in sec_results:
                content = f"TICKER: {ticker} | Form {f.form_type} filed at {f.filed_at}\n"
                if f.sections:
                    for s_id, s_text in f.sections.items():
                        content += f"Section {s_id}: {s_text[:2000]}...\n"
                elif f.full_text:
                    content += f.full_text[:5000]
                raw_results.append({
                    "query": f"SEC filings for {ticker}",
                    "source": f"sec_{f.form_type.lower()}",
                    "content": content,
                    "url": f.filing_url,
                    "ticker": ticker
                })
        except Exception as e:
            errors.append({"node": "financial_research", "ticker": ticker, "error": f"SEC: {str(e)}"})
        
        # External Earnings Call Transcripts API - ONLY if user mentioned specific companies
        # This gates expensive external API calls for generic industry queries
        # The corpus (Step 2) already provides 40+ pre-ingested transcripts for common companies
        if has_company_mention:
            emit_progress_sync(ToolProgress(tool_name="earnings_call", message=f"Retrieving earnings transcript for {ticker}", ticker=ticker))
            try:
                result = get_earnings_transcript_ninja.invoke({"ticker": ticker})
                if result and str(result).strip():
                    raw_results.append({
                        "query": f"Earnings call for {ticker}",
                        "source": "earnings_call",
                        "content": result,
                        "ticker": ticker
                    })
            except Exception as e:
                errors.append({"node": "financial_research", "ticker": ticker, "error": f"Earnings: {str(e)}"})
            
            # STEP 3b: Keyword-based earnings search for targeted quote extraction
            # Search for relevant sections with speaker attribution
            emit_progress_sync(ToolProgress(tool_name="earnings_keywords", message=f"Searching earnings for key topics ({ticker})", ticker=ticker))
            try:
                # Extract key topics from the original query and brief
                search_keywords = _extract_quote_keywords(brief.original_query, brief.financial_agent_queries)
                if search_keywords:
                    keyword_result = search_earnings_keywords.invoke({
                        "ticker": ticker,
                        "keywords": search_keywords[:5],  # Limit to top 5 keywords
                    })
                    if keyword_result and str(keyword_result).strip():
                        raw_results.append({
                            "query": f"Earnings keyword search for {ticker}",
                            "source": "earnings_call_quotes",
                            "content": keyword_result,
                            "ticker": ticker,
                            "note": "Contains speaker-attributed quotes matching key topics"
                        })
            except Exception as e:
                # Non-critical - keyword search is supplementary
                logger.debug(f"Earnings keyword search failed for {ticker}: {e}")
    
    # =========================================================================
    # STEP 4: StockNewsAPI Calls (Batched by Ticker List)
    # INTELLIGENT GATING: Only run tools that match the query type
    # - Company news: Run if recent_news or company_financials needed
    # - Press releases: Run if recent_news or company_financials needed  
    # - Analyst ratings: Run ONLY if analyst_views explicitly requested
    # - Sentiment: Run ONLY if analyst_views explicitly requested
    # =========================================================================
    ticker_list = list(all_tickers)
    if ticker_list:
        # Company news - recent headlines and developments
        # Run if: user wants recent news OR specific company financials
        if query_type["needs_recent_news"] or query_type["needs_company_financials"]:
            emit_progress_sync(ToolProgress(tool_name="company_news", message=f"Fetching company news for {', '.join(ticker_list[:3])}{'...' if len(ticker_list) > 3 else ''}"))
            try:
                news_result = get_company_news.invoke({"tickers": ticker_list, "days": 30, "items": 20})
                if news_result:
                    raw_results.append({"query": "Company news", "source": "stocknews_company", "content": news_result})
            except Exception as e:
                errors.append({"node": "financial_research", "error": f"StockNews company: {str(e)}"})
        else:
            logger.info("Financial agent: Skipping company news (not needed for query type)")
        
        # Press releases - official company announcements
        # Run if: user wants recent news OR specific company financials
        if query_type["needs_recent_news"] or query_type["needs_company_financials"]:
            emit_progress_sync(ToolProgress(tool_name="press_releases", message="Fetching press releases"))
            try:
                pr_result = get_press_releases.invoke({"tickers": ticker_list, "days": 60, "items": 15})
                if pr_result:
                    raw_results.append({"query": "Press releases", "source": "stocknews_press_releases", "content": pr_result})
            except Exception as e:
                errors.append({"node": "financial_research", "error": f"StockNews PR: {str(e)}"})
        else:
            logger.info("Financial agent: Skipping press releases (not needed for query type)")
        
        # Analyst ratings - upgrades, downgrades, price targets
        # Run ONLY if: user explicitly wants analyst views
        if query_type["needs_analyst_views"]:
            emit_progress_sync(ToolProgress(tool_name="analyst_ratings", message="Getting analyst ratings"))
            try:
                ratings_result = get_analyst_ratings.invoke({"tickers": ticker_list, "items": 15})
                if ratings_result:
                    raw_results.append({"query": "Analyst ratings", "source": "stocknews_analyst_ratings", "content": ratings_result})
            except Exception as e:
                errors.append({"node": "financial_research", "error": f"StockNews ratings: {str(e)}"})
        else:
            logger.info("Financial agent: Skipping analyst ratings (not explicitly requested)")
        
        # Sentiment summary - per ticker (must be called individually)
        # Run ONLY if: user explicitly wants analyst views/sentiment
        if query_type["needs_analyst_views"]:
            for ticker in ticker_list[:5]:  # Limit to top 5 to avoid rate limits
                try:
                    sentiment_result = get_sentiment_summary.invoke({"ticker": ticker, "days": 30})
                    if sentiment_result:
                        raw_results.append({
                            "query": f"Sentiment for {ticker}",
                            "source": "stocknews_sentiment",
                            "content": sentiment_result,
                            "ticker": ticker
                        })
                except Exception as e:
                    pass  # Sentiment miss is not critical
        else:
            logger.info("Financial agent: Skipping sentiment analysis (not explicitly requested)")
    
    # =========================================================================
    # STEP 5: Relevance Ranking & LLM Extraction
    # Rank results by source priority, then send to LLM for structured extraction
    # =========================================================================
    ranked_results = _rank_financial_results(raw_results, brief.original_query)
    
    # Enrich results with top-level URLs extracted from content for easier LLM access
    enriched_results = _enrich_raw_results_with_urls(ranked_results[:8])
    
    # Take top 8 results by relevance and truncate content to prevent token overflow
    # Reduced from 15 to avoid LLM output truncation causing JSON parse errors
    top_results = _truncate_result_content(enriched_results, max_chars=3000)
    
    # Prepare research context for the extraction prompt
    research_context = f"""
## Research Context
- **Original Query**: {brief.original_query}
- **Research Intent**: {brief.clarified_intent or 'Financial intelligence gathering'}
- **Key Entities**: {', '.join(brief.entities_to_track) if brief.entities_to_track else 'Not specified'}
- **Resolved Tickers**: {', '.join(all_tickers) if all_tickers else 'No tickers resolved'}
- **Time Period**: {brief.timeframe or 'Recent'}

## Financial Queries Being Addressed:
{chr(10).join(f'- {q}' for q in brief.financial_agent_queries)}
"""
    
    extraction_prompt = f"""
{research_context}

Based on the following ranked research results, extract structured financial findings.

## PRIORITY 1: EXECUTIVE QUOTES (Most Important)
For each company in the results, extract 2-4 verbatim quotes from earnings calls:
- **Guidance Quote**: CEO/CFO statement on revenue/earnings outlook
- **Demand Quote**: What they're seeing from customers, order book, backlog
- **Risk Quote**: Any headwinds, challenges, or concerns mentioned
- **Strategy Quote**: Capital allocation, facility expansion, M&A plans

Format each quote in the `direct_quote` field as:
"[Exact words in quotes] — [Name], [Title], [Company] [Quarter] Earnings Call"

Example:
"We're raising full-year guidance to $2.1-2.2 billion, driven by strong aerospace demand. — Nick Stanage, CEO, Hexcel Q3 2025 Earnings Call"

## PRIORITY 2: Quantitative Metrics
- Revenue growth, margins, CapEx figures
- Use `metrics` field: {{"revenue": "$2.1B", "margin": "18.5%"}}

## PRIORITY 3: Other Financial Intelligence
- M&A, facility expansions, new contracts
- Risk factors from SEC filings
- Analyst ratings and price targets

## Confidence Rules
- HIGH: Has direct_quote from earnings OR specific metrics from SEC filing
- MEDIUM: Paraphrased earnings commentary OR analyst/news sources
- LOW: Single source, outdated, or ambiguous

RAW RESULTS (ranked by source priority):
{json.dumps(top_results, indent=2, default=str)[:50000]}

Respond ONLY with a JSON object matching this EXACT schema:

{{
  "status": "complete" | "partial" | "failed",
  "queries_executed": ["list of query strings executed"],
  "sources_searched": 0,
  "sources_with_results": 0,
  "execution_time_seconds": 0.0,
  "findings": [
    {{
      "finding_id": "fin_001",
      "finding": "Specific finding statement with details",
      "finding_type": "revenue|margin|growth|capex|guidance|risk|contract|m_and_a|expansion|analyst_rating",
      "confidence": "high" | "medium" | "low",
      "relevance_score": 0.0 to 1.0,
      "citation": {{
        "source_type": "sec_10k|sec_10q|sec_8k|earnings_call|investor_presentation|financial_news|press_release",
        "source_title": "Document or article title",
        "source_url": "COPY the 'url' field from the raw result - REQUIRED for clickable links",
        "source_date": "YYYY-MM-DD or null",
        "page_or_section": "Section reference or null",
        "direct_quote": "Exact quote if available or null"
      }},
      "entities_mentioned": ["Company", "Person", "Product"],
      "metrics": {{"metric_name": "value"}} or null
    }}
  ],
  "key_metrics_summary": {{"revenue": "value", "margin": "value"}} or null,
  "failed_sources": [{{"source": "name", "error": "reason"}}],
  "data_gaps": ["List of information that could not be found"],
  "warnings": ["List of any data quality or reliability concerns"]
}}

IMPORTANT:
- Each finding MUST have finding_id (e.g., "fin_001", "fin_002")
- confidence MUST be lowercase: "high", "medium", or "low"
- relevance_score MUST be a decimal between 0.0 and 1.0
- All lists (findings, failed_sources, data_gaps, warnings) MUST be arrays, even if empty []
- CRITICAL: For source_url, COPY the exact "url" field from each raw result - users need clickable links!
- Each raw result above has a "url" field - use it in your citation's source_url
"""
    
    messages = [
        SystemMessage(content=FINANCIAL_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=extraction_prompt)
    ]
    
    response = await llm.ainvoke(messages)
    
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Try to parse JSON, with repair attempt if truncated
        try:
            output_data = json.loads(content)
        except json.JSONDecodeError as parse_err:
            logger.warning(f"[FINANCIAL_RESEARCH] JSON parse error, attempting repair: {parse_err}")
            repaired_content = _repair_truncated_json(content)
            output_data = json.loads(repaired_content)
            logger.info("[FINANCIAL_RESEARCH] JSON repair successful")
            
        financial_output = FinancialAgentOutput(**output_data)
        
        # Add execution metadata
        financial_output.execution_time_seconds = time.time() - start_time
        financial_output.queries_executed = queries_executed
        
        elapsed = time.time() - start_time
        logger.info(f"[FINANCIAL_RESEARCH] COMPLETE in {elapsed:.1f}s - findings: {len(financial_output.findings)}")
        
        # Return PARTIAL STATE - only fields this node updates
        # This is required for LangGraph's Send API parallel merge
        return {
            "financial_output": financial_output,
            "current_status": "financial_research_complete",
            "errors": errors,
        }
        
    except Exception as e:
        errors.append({"node": "financial_research_synthesis", "error": str(e)})
        # Return PARTIAL STATE on failure
        return {
            "current_status": "financial_research_failed",
            "errors": errors,
        }
