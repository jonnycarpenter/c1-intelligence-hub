import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.ingestion.industry_queries import get_all_exa_queries_v2, get_all_tavily_queries_v2
    
    exa = get_all_exa_queries_v2()
    tavily = get_all_tavily_queries_v2()
    print(f"SUCCESS: Loaded {len(exa)} Exa queries and {len(tavily)} Tavily queries.")
except Exception as e:
    print(f"ERROR: {e}")
