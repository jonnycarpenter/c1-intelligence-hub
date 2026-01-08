#!/usr/bin/env python
"""Simple test of the resilient LLM client."""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test():
    from app.utils.resilient_llm import get_resilient_async_client
    from app.config.settings import settings
    
    print(f"Anthropic API key present: {bool(settings.anthropic_api_key)}")
    print(f"OpenAI API key present: {bool(getattr(settings, 'openai_api_key', None))}")
    
    client = get_resilient_async_client(
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=getattr(settings, 'openai_api_key', None),
    )
    
    print('Testing LLM call with simple prompt...')
    try:
        response = await client.messages_create(
            model='claude-sonnet-4-5',
            max_tokens=100,
            messages=[{'role': 'user', 'content': 'Say hello'}],
        )
        print(f'SUCCESS! Response: {response.content[0].text}')
    except Exception as e:
        print(f'FAILED: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
