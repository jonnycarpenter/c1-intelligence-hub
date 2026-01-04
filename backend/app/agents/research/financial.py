from typing import Dict, Any, List, Optional, Set
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.research.state import DeepResearchState, FinancialAgentOutput, FinancialFinding, ConfidenceLevel, SourceType, Citation
from app.config.settings import settings
from app.mcp.tools.api_ninja_earnings import get_earnings_transcript_ninja
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

FINANCIAL_AGENT_SYSTEM_PROMPT = """
You are a Financial Research Agent specializing in the composites industry. Your job is to extract specific, data-driven financial insights from SEC filings, earnings calls, and financial news.

## Your Responsibilities

1. ANALYZE financial documents (SEC 10-K, 10-Q, 8-K, and Earnings Call Transcripts)
2. PRIORITY: Check the internal `query_corpus` FIRST for pre-ingested financial data and earnings
3. USE SEC filings for official metrics and risk factors
4. USE StockNewsAPI tools for real-time news, analyst ratings, and sentiment:
   - `get_company_news`: Recent news for specific tickers
   - `get_press_releases`: Official company announcements
   - `get_analyst_ratings`: Upgrades, downgrades, price targets (Wall Street perspective)
   - `get_sentiment_summary`: Aggregated news sentiment
5. EXTRACT key metrics, strategic outlooks, and financial headwinds
6. ATTRIBUTE every finding with a precise citation
7. EVALUATE the confidence and relevance of each finding

## Key Composites Industry Tickers
- Composites: HXL (Hexcel), OC (Owens Corning), TRYIY (Toray), SOLVY (Solvay), TPIC (TPI Composites)
- Aerospace: BA (Boeing), EADSY (Airbus), RTX, LMT, NOC, GE, GD
- Wind: VWDRY (Vestas), GEV (GE Vernova)

## Extraction Guidelines

- Focus on QUANTITATIVE metrics (revenue growth, margins, capital expenditure)
- Identify STRATEGIC commentary (M&A activity, facility expansions, new contract wins)
- Note RISK factors and headwinds (supply chain constraints, raw material pricing)
- Look for industry-specific mentions (e.g., carbon fiber pricing, aerospace demand cycles)
- Extract GUIDANCE and OUTLOOK statements from earnings calls

## Confidence Scores
- HIGH: Direct quote with specific metrics from an official SEC filing or earnings transcript
- MEDIUM: Strong inference or qualitative statement from analyst ratings/news
- LOW: Ambiguous statement, single-source, or potentially outdated information

## Output Format
Always respond with valid JSON matching the FinancialAgentOutput schema.
"""

async def financial_research_node(state: DeepResearchState) -> DeepResearchState:
    """
    Financial research node. Executes queries against SEC filings, earnings calls,
    and StockNewsAPI tools for comprehensive financial intelligence.
    
    Improvements:
    - Batch ticker resolution from all queries upfront
    - Relevance-ranked results before LLM truncation
    - Enhanced extraction prompt with research context
    """
    start_time = time.time()
    llm = ChatAnthropic(
        model="claude-opus-4-5",
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0,
    )
    
    brief = state["research_brief"]
    if not brief or not brief.financial_agent_queries:
        state["current_status"] = "financial_research_skipped"
        return state
        
    queries_executed = []
    raw_results = []
    
    # Load companies for ticker resolution
    companies_df = load_companies()
    
    # =========================================================================
    # STEP 1: Batch Ticker Resolution
    # Resolve all tickers mentioned across all queries upfront for efficient API usage
    # =========================================================================
    all_tickers = _resolve_all_tickers(brief.financial_agent_queries, companies_df)
    
    # =========================================================================
    # STEP 2: Execute Corpus Queries (Query-Specific)
    # Check internal corpus first for pre-ingested earnings and financial data
    # =========================================================================
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
    # STEP 3: Batch SEC Filings and Earnings Calls (Per Ticker)
    # Execute SEC and earnings queries per resolved ticker to avoid duplicates
    # =========================================================================
    for ticker in all_tickers:
        # SEC Filings - official 10-K, 10-Q, 8-K filings
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
            state["errors"].append({"node": "financial_research", "ticker": ticker, "error": f"SEC: {str(e)}"})
        
        # Earnings Call Transcripts - management commentary and guidance
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
            state["errors"].append({"node": "financial_research", "ticker": ticker, "error": f"Earnings: {str(e)}"})
    
    # =========================================================================
    # STEP 4: StockNewsAPI Calls (Batched by Ticker List)
    # Real-time financial news, analyst ratings, press releases, sentiment
    # =========================================================================
    ticker_list = list(all_tickers)
    if ticker_list:
        # Company news - recent headlines and developments
        try:
            news_result = get_company_news.invoke({"tickers": ticker_list, "days": 30, "items": 20})
            if news_result:
                raw_results.append({"query": "Company news", "source": "stocknews_company", "content": news_result})
        except Exception as e:
            state["errors"].append({"node": "financial_research", "error": f"StockNews company: {str(e)}"})
        
        # Press releases - official company announcements
        try:
            pr_result = get_press_releases.invoke({"tickers": ticker_list, "days": 60, "items": 15})
            if pr_result:
                raw_results.append({"query": "Press releases", "source": "stocknews_press_releases", "content": pr_result})
        except Exception as e:
            state["errors"].append({"node": "financial_research", "error": f"StockNews PR: {str(e)}"})
        
        # Analyst ratings - upgrades, downgrades, price targets
        try:
            ratings_result = get_analyst_ratings.invoke({"tickers": ticker_list, "items": 15})
            if ratings_result:
                raw_results.append({"query": "Analyst ratings", "source": "stocknews_analyst_ratings", "content": ratings_result})
        except Exception as e:
            state["errors"].append({"node": "financial_research", "error": f"StockNews ratings: {str(e)}"})
        
        # Sentiment summary - per ticker (must be called individually)
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
    
    # =========================================================================
    # STEP 5: Relevance Ranking & LLM Extraction
    # Rank results by source priority, then send to LLM for structured extraction
    # =========================================================================
    ranked_results = _rank_financial_results(raw_results, brief.original_query)
    
    # Take top 15 results by relevance (SEC filings > earnings > analyst > news)
    top_results = ranked_results[:15]
    
    # Prepare research context for the extraction prompt
    research_context = f"""
## Research Context
- **Original Query**: {brief.original_query}
- **Research Intent**: {brief.research_intent or 'Financial intelligence gathering'}
- **Key Entities**: {', '.join(brief.key_entities) if brief.key_entities else 'Not specified'}
- **Resolved Tickers**: {', '.join(all_tickers) if all_tickers else 'No tickers resolved'}
- **Time Period**: {brief.time_period or 'Recent'}

## Financial Queries Being Addressed:
{chr(10).join(f'- {q}' for q in brief.financial_agent_queries)}
"""
    
    extraction_prompt = f"""
{research_context}

Based on the following ranked research results, extract structured financial findings.
Focus on:
1. QUANTITATIVE metrics (revenue, margins, growth rates, CapEx)
2. STRATEGIC developments (M&A, facility expansions, new contracts)
3. RISK factors and headwinds mentioned in filings
4. ANALYST perspective (ratings changes, price targets)
5. GUIDANCE and forward-looking statements

Prioritize findings from SEC filings and earnings calls as HIGH confidence.
Analyst ratings and news should be MEDIUM confidence unless corroborated.

RAW RESULTS (ranked by source priority):
{json.dumps(top_results, indent=2, default=str)[:50000]}

Respond ONLY with a JSON object matching the FinancialAgentOutput schema.
Include specific citations with URLs where available.
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
            
        output_data = json.loads(content)
        financial_output = FinancialAgentOutput(**output_data)
        
        # Add execution metadata
        financial_output.execution_time_seconds = time.time() - start_time
        financial_output.queries_executed = queries_executed
        
        state["financial_output"] = financial_output
        state["current_status"] = "financial_research_complete"
        
    except Exception as e:
        state["errors"].append({"node": "financial_research_synthesis", "error": str(e)})
        state["current_status"] = "financial_research_failed"
        
    return state
