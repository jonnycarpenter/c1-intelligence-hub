
import sys
import os
import asyncio
from dotenv import load_dotenv

sys.path.append(os.getcwd())
# Load env from backend/.env
load_dotenv(os.path.join(os.getcwd(), 'backend', '.env'))

async def test_connection():
    try:
        from app.ingestion.importyeti import ImportYetiClient
        
        api_key = os.getenv("IMPORTYETI_API_KEY")
        print(f"API Key present: {bool(api_key)}")
        if api_key:
            print(f"API Key length: {len(api_key)}")
            print(f"API Key start: {api_key[:5]}...")
        
        # Use default config
        print("Testing with configured client...")
        client = ImportYetiClient()
        print("Testing BOL lookup (known good)...")
        # status = await client.get_database_updated()
        status = await client.get_bol("CCLLMILS17011590")
        print(f"Status success: {status.success}")
        if status.success:
            print(f"Data keys: {status.data.keys() if status.data else 'None'}")
        else:
            print(f"Error: {status.error}")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
