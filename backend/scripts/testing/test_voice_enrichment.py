"""Test voice enrichment data availability in BigQuery."""
import asyncio
import sys
sys.path.insert(0, '.')
from app.db.gcp_storage import BigQueryDataStorage

async def test():
    store = BigQueryDataStorage()
    
    # Companies from the Feb 9 briefing sections
    companies = ["Hexcel", "BASF", "Evonik", "Dow Chemical", "Toray", "Vestas"]
    
    print("=== SEC Filing Nuggets ===")
    for company in companies[:4]:
        try:
            nuggets = await store.get_sec_filing_nuggets(search_query=company, min_relevance=0.3, limit=3)
            print(f"  {company}: {len(nuggets)} nuggets")
            if nuggets:
                for n in nuggets[:1]:
                    print(f"    -> {n.get('ticker', '?')} / {n.get('filing_type', '?')}: {str(n.get('text', ''))[:80]}")
        except Exception as e:
            print(f"  {company}: ERROR - {e}")
    
    print("\n=== Earnings Quotes ===")
    for company in companies[:4]:
        try:
            quotes = await store.get_earnings_quotes(search_query=company, quotable_only=True, min_relevance=0.3, limit=3)
            print(f"  {company}: {len(quotes)} quotes")
            if quotes:
                for q in quotes[:1]:
                    print(f"    -> {q.get('company', '?')} ({q.get('ticker', '?')}): {str(q.get('text', ''))[:80]}")
        except Exception as e:
            print(f"  {company}: ERROR - {e}")
    
    print("\n=== Podcast Quotes ===")
    try:
        quotes = await store.get_podcast_quotes(themes=["carbon_fiber", "hydrogen", "aerospace"], days=90, limit=5)
        print(f"  By themes: {len(quotes)} quotes")
        for q in quotes[:2]:
            print(f"    -> {q.get('speaker', '?')} at {q.get('company', '?')}: {str(q.get('text', ''))[:80]}")
    except Exception as e:
        print(f"  By themes: ERROR - {e}")
    
    try:
        quotes = await store.get_podcast_quotes(search_query="Hexcel", days=90, limit=5)
        print(f"  By company 'Hexcel': {len(quotes)} quotes")
    except Exception as e:
        print(f"  By company: ERROR - {e}")
    
    # Check table row counts
    from google.cloud import bigquery
    c = bigquery.Client(project='gen-lang-client-0436975498')
    for table in ['sec_filing_nuggets', 'earnings_quotes', 'podcast_quotes']:
        try:
            r = list(c.query(f'SELECT COUNT(*) as cnt FROM `gen-lang-client-0436975498.c1_intelligence.{table}`'))
            print(f"\n{table}: {r[0].cnt} total rows")
        except Exception as e:
            print(f"\n{table}: TABLE NOT FOUND or ERROR - {e}")

asyncio.run(test())
