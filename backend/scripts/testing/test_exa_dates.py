"""
Test what dates Exa returns for URLs that ended up with future dates.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from exa_py import Exa

# Initialize Exa client
exa_api_key = os.getenv("EXA_API_KEY") or os.getenv("EXA_AI_API_KEY")
if not exa_api_key:
    print("ERROR: EXA_API_KEY or EXA_AI_API_KEY not set in environment")
    exit(1)

client = Exa(exa_api_key)

# Known URLs that got future dates
test_urls = [
    "https://imarcgroup.com/aerospace-composites-market",
    "https://www.schunk-group.com/en/glossary/fiber-composites",
    "https://highergov.com/contract/HQ086024C7117/",
]

print("Testing Exa's publishedDate for known problematic URLs...")
print("="*70)

# Search for content and see what publishedDate Exa returns
for url in test_urls:
    try:
        # Get contents with published date
        response = client.get_contents(
            urls=[url],
        )
        
        if response.results:
            result = response.results[0]
            print(f"\nURL: {url}")
            print(f"  Title: {result.title}")
            print(f"  Exa publishedDate (camelCase): {getattr(result, 'publishedDate', 'NOT AVAILABLE')}")
            print(f"  Exa published_date (snake_case): {getattr(result, 'published_date', 'NOT AVAILABLE')}")
            print(f"  Raw result attrs: {[a for a in dir(result) if not a.startswith('_')]}")
    except Exception as e:
        print(f"\nURL: {url}")
        print(f"  ERROR: {e}")

print("\n" + "="*70)
print("\nNow trying a search to see publishedDate in search results...")

try:
    response = client.search_and_contents(
        query="aerospace composites market analysis IMARC",
        num_results=3,
        text=True,
    )
    
    for r in response.results:
        print(f"\n  URL: {r.url}")
        print(f"  Title: {r.title}")
        print(f"  publishedDate (camel): {getattr(r, 'publishedDate', 'N/A')}")
        print(f"  published_date (snake): {getattr(r, 'published_date', 'N/A')}")
except Exception as e:
    print(f"Search error: {e}")
