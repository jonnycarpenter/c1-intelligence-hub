
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.exa_service import exa_service

async def test_enrichment():
    print("Testing Exa Service Enrichment...")
    print(f"Supply chain terms loaded: {len(exa_service.supply_chain_terms)}")
    print(f"Sample terms: {exa_service.supply_chain_terms[:5]}")
    
    results = await exa_service.search_companies_enhanced("aerospace composites manufacturers Ohio", num_results=3)
    
    for r in results:
        print(f"\nCompany: {r.company_name} ({r.domain})")
        if r.apollo_enrichment:
            print(f"  Enrichment found!")
            print(f"  Revenue: {r.apollo_enrichment.get('revenue_printed')}")
            print(f"  Tags: {r.apollo_enrichment.get('supply_chain_matches')}")
        else:
            print("  Enrichment MISSING")

if __name__ == "__main__":
    asyncio.run(test_enrichment())
