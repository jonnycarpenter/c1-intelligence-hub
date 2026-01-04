
import asyncio
import httpx
from app.config.settings import settings

async def main():
    if not settings.fmp_api_key:
        print("No FMP API Key found.")
        return

    base_url = "https://financialmodelingprep.com/api/v3"
    
    async with httpx.AsyncClient() as client:
        # Test General News
        url = f"{base_url}/fmp/articles"
        print(f"Testing {url}...", end=" ")
        try:
            resp = await client.get(url, params={"apikey": settings.fmp_api_key, "limit": 1})
            if resp.status_code == 200:
                print("OK")
            else:
                print(f"FAILED ({resp.status_code}) - {resp.text[:100]}")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
