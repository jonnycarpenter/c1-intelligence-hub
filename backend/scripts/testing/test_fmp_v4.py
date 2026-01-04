
import asyncio
import httpx
from app.config.settings import settings

async def test_endpoint(client, name, url):
    print(f"Testing {name}: {url}...", end=" ")
    try:
        resp = await client.get(url, params={"apikey": settings.fmp_api_key, "limit": 1})
        if resp.status_code == 200:
            print("OK")
            return True
        else:
            print(f"FAILED ({resp.status_code}) - {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def main():
    if not settings.fmp_api_key:
        print("No FMP API Key found.")
        return

    base_url = "https://financialmodelingprep.com/api/v4"
    
    async with httpx.AsyncClient() as client:
        # Test v4 Stock News
        await test_endpoint(client, "v4 Stock News", f"{base_url}/stock-news-sentiments-rss?ticker=AAPL")

if __name__ == "__main__":
    asyncio.run(main())
