"""
Analyze URLs to debug date extraction issues.
"""
import httpx
import re
import json
from datetime import datetime

# Test URLs from BigQuery with incorrect future dates
test_urls = [
    ('https://imarcgroup.com/aerospace-composites-market', '2026-09-11', 'research summary page'),
    ('https://www.schunk-group.com/en/glossary/fiber-composites', '2026-09-01', 'glossary page'),
    ('https://www.highergov.com/contract/HQ086024C7117/', '2026-07-02', 'govt contract page'),
    ('https://www.composites.aero/about-us', '2026-06-01', 'about-us page'),
    ('https://www.lindellyachts.com/at-the-helm/from-wood-to-vacuum-infused-core-the-evolution-of-sportfishing-yachts', '2026-06-01', 'blog article'),
    ('https://www.plasticsnet.com/doc/type-30-rovings-0001', '2026-05-15', 'product doc'),
    ('https://www.atomic-6.com/homev2-1', '2026-05-14', 'homepage variant'),
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def analyze_url(url, stored_date, notes):
    print(f'\n{"="*70}')
    print(f'URL: {url}')
    print(f'Stored date: {stored_date} | Notes: {notes}')
    print('-'*70)
    
    try:
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        html = resp.text[:20000]  # First 20k chars
        
        # Look for JSON-LD
        jsonld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        jsonld_matches = re.findall(jsonld_pattern, html, re.DOTALL | re.IGNORECASE)
        if jsonld_matches:
            print(f'JSON-LD found: {len(jsonld_matches)} blocks')
            for jld in jsonld_matches[:2]:
                try:
                    data = json.loads(jld.strip())
                    if isinstance(data, dict):
                        dp = data.get('datePublished') or data.get('dateCreated') or data.get('dateModified')
                        if dp:
                            print(f'  datePublished: {dp}')
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                dp = item.get('datePublished') or item.get('dateCreated')
                                if dp:
                                    print(f'  datePublished (in array): {dp}')
                except json.JSONDecodeError:
                    pass
        else:
            print('No JSON-LD found')
        
        # Look for meta dates
        meta_patterns = [
            (r'<meta[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', 'article:published_time'),
            (r'<meta[^>]*name=["\']date["\'][^>]*content=["\']([^"\']+)["\']', 'meta name=date'),
            (r'<meta[^>]*name=["\']DC.date["\'][^>]*content=["\']([^"\']+)["\']', 'DC.date'),
            (r'<meta[^>]*property=["\']og:updated_time["\'][^>]*content=["\']([^"\']+)["\']', 'og:updated_time'),
        ]
        for pattern, name in meta_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                print(f'Meta tag [{name}]: {match.group(1)}')
        
        # Check URL for date pattern
        url_date = re.search(r'/(\d{4})[/-](\d{2})[/-](\d{2})', url)
        if url_date:
            print(f'URL date pattern: {url_date.group(0)}')
        else:
            print('No date in URL')
        
        # Get text content and look for date patterns
        text_content = re.sub(r'<[^>]+>', ' ', html[:10000])
        text_content = ' '.join(text_content.split())
        
        # Look for specific future date patterns that might be getting extracted
        future_patterns = [
            r'(by|expected|forecast|projected|outlook|reach|grow)\s+.*?(\d{4})',
            r'market\s+.*?(202[5-9]|203\d)',
            r'\$[\d.]+\s*(billion|million|B|M)\s+by\s+(\d{4})',
        ]
        
        print(f'\nPotential future projection dates in content:')
        for pattern in future_patterns:
            matches = re.findall(pattern, text_content[:3000], re.IGNORECASE)
            if matches:
                print(f'  Pattern "{pattern[:40]}..." found: {matches[:3]}')
        
        # Look for date patterns that our extractor might be catching
        date_patterns = [
            (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}', 'Month DD, YYYY'),
            (r'\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}', 'DD Month YYYY'),
            (r'\d{4}-\d{2}-\d{2}', 'ISO date'),
        ]
        
        print(f'\nDate patterns found in first 3000 chars:')
        for pattern, name in date_patterns:
            matches = re.findall(pattern, text_content[:3000], re.IGNORECASE)
            if matches:
                # Get full matches with context
                for m in re.finditer(pattern, text_content[:3000], re.IGNORECASE):
                    start = max(0, m.start() - 30)
                    end = min(len(text_content), m.end() + 30)
                    context = text_content[start:end].replace('\n', ' ')
                    print(f'  [{name}] ...{context}...')
                    if len(matches) > 2:
                        print(f'    (and {len(matches)-1} more)')
                        break
        
        # Content preview
        print(f'\nContent preview (first 400 chars):')
        print(f'  {text_content[:400]}...')
        
    except Exception as e:
        print(f'Error fetching URL: {e}')


if __name__ == '__main__':
    for url, stored_date, notes in test_urls:
        analyze_url(url, stored_date, notes)
        print()
