"""Quick test to verify Anthropic API connectivity."""
import asyncio
import sys
from anthropic import AsyncAnthropic
from app.config.settings import settings
import time


async def test_anthropic_api():
    """Test if Anthropic API is responding."""
    try:
        print("🔍 Testing Anthropic API connectivity...")
        
        if not settings.anthropic_api_key:
            print("❌ No ANTHROPIC_API_KEY configured in settings")
            return False
            
        # Create client
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        
        # Simple ping with fast model
        start = time.time()
        response = await client.messages.create(
            model="claude-3-5-haiku-20241022",  # Fast, cheap model
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        elapsed = time.time() - start
        
        # Success!
        print(f"✅ Anthropic API is UP and responding!")
        print(f"   Status: 200 OK")
        print(f"   Model: {response.model}")
        print(f"   Latency: {elapsed:.2f}s")
        print(f"   Response: {response.content[0].text}")
        print(f"   Tokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
        return True
        
    except Exception as e:
        print(f"❌ Anthropic API test FAILED")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_anthropic_api())
    sys.exit(0 if success else 1)
