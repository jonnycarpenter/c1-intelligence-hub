"""Quick test to check what Tavily returns for published_date"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

# Import our date extraction
from app.utils.date_extraction import extract_publication_date, extract_date_from_url, extract_date_from_jsonld

api_key = os.getenv('TAVILY_API_KEY')
client = httpx.Client(timeout=30.0)

# Test with a query we know returns results
payload = {
    'api_key': api_key,
    'query': 'Vestas wind turbine orders 2025',
    'max_results': 3,
    'search_depth': 'advanced',
}

response = client.post('https://api.tavily.com/search', json=payload)
data = response.json()

print("=== Tavily API Response ===\n")
for item in data.get('results', []):
    title = item.get('title', '')[:70]
    url = item.get('url', '')
    pub_date = item.get('published_date')
    content = item.get('content', '')[:200]
    
    # Test our date extraction
    url_date = extract_date_from_url(url)
    
    # Test JSON-LD extraction (which we currently only do for PRNewswire)
    print(f"Title: {title}")
    print(f"URL: {url}")
    print(f"Tavily published_date: {pub_date}")
    print(f"URL date extraction: {url_date}")
    
    # Try JSON-LD for ALL URLs
    print("Testing JSON-LD extraction...")
    jsonld_date = extract_date_from_jsonld(url)
    print(f"JSON-LD datePublished: {jsonld_date}")
    print("---")

client.close()
