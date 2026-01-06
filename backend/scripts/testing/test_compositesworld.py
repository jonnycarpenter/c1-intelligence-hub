"""Test date extraction from compositesworld.com"""
from app.utils.date_extraction import extract_publication_date, extract_date_from_jsonld

# Test the full extraction function
url = 'https://www.compositesworld.com/articles/revolutionizing-space-composites-a-new-era-of-satellite-materials'

print("=== Testing extract_publication_date ===")
print(f"URL: {url}")

result = extract_publication_date(
    url=url,
    content=None,
    api_date=None,
    fallback=None,
    fetch_jsonld=True
)

print(f"Extracted date: {result}")
print(f"Type: {type(result)}")

# Also test some other URLs
print("\n=== Testing other URLs ===")
test_urls = [
    'https://www.reuters.com/business/aerospace-defense/',
    'https://www.cnbc.com/2025/12/28/stock-market-news.html',
]

for test_url in test_urls:
    print(f"\nURL: {test_url[:60]}...")
    try:
        date = extract_publication_date(url=test_url, api_date=None, fallback=None, fetch_jsonld=True)
        print(f"Extracted: {date}")
    except Exception as e:
        print(f"Error: {e}")
