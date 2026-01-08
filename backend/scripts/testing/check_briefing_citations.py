"""Quick check for Exa citations in briefings."""
import json
from google.cloud import bigquery

c = bigquery.Client()

query = """
    SELECT id, briefing_title, sections
    FROM `gen-lang-client-0436975498.c1_intelligence.weekly_briefings`
    ORDER BY generated_at DESC
    LIMIT 1
"""
results = list(c.query(query).result())
if results:
    r = results[0]
    print(f"Title: {r.briefing_title}")
    sections = json.loads(r.sections) if isinstance(r.sections, str) else r.sections
    
    exa_found = False
    for i, s in enumerate(sections):
        print(f"\nSection {i+1}: {s.get('header')}")
        headline = s.get('headline', {})
        text = headline.get('text', '') if isinstance(headline, dict) else str(headline)
        
        # Check for Exa in text
        if 'Exa:' in text:
            print(f"  ⚠️ FOUND 'Exa:' IN HEADLINE: {text}")
            exa_found = True
        else:
            print(f"  Headline: {text[:100]}...")
        
        # Check insights
        for j, insight in enumerate(s.get('insights', [])):
            insight_text = insight.get('text', '') if isinstance(insight, dict) else str(insight)
            if 'Exa:' in insight_text:
                print(f"  ⚠️ FOUND 'Exa:' IN INSIGHT {j+1}: {insight_text}")
                exa_found = True
        
        # Check source_articles
        sources = s.get('source_articles', [])
        print(f"  Sources: {len(sources)} articles")
        for src in sources[:3]:
            source_name = src.get('source_name', '')
            if 'exa' in source_name.lower():
                print(f"    ⚠️ FOUND 'exa' in source_name: {source_name}")
                exa_found = True
            else:
                print(f"    [{src.get('article_number')}] {source_name}")
    
    if not exa_found:
        print("\n✅ No 'Exa:' references found in briefing text!")
    else:
        print("\n❌ Still found 'Exa' references - needs more work")
