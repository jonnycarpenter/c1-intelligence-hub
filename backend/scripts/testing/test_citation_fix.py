"""Quick test of the get_articles_by_ids fix."""
import asyncio
import sys
sys.path.insert(0, '.')
from app.db.gcp_storage import BigQueryDataStorage as BigQueryStore

async def test():
    store = BigQueryStore()
    # Test with known article_ids from the Feb 9 pre-briefing
    test_ids = [
        '9a8a0efa-cecf-4769-9b60-81ce8aa66371',
        '6c6e00f5-b374-446b-bd39-ee84cc16769f',
        '5e1efccf-911e-4eb1-873d-dcd565b6b5eb',
    ]
    results = await store.get_articles_by_ids(test_ids)
    found = 0
    for r in results:
        t = r.get('title', '?')[:60]
        u = r.get('url', '?')[:60]
        s = r.get('_source_table', '?')
        is_found = r.get('title') != 'Article not found'
        if is_found:
            found += 1
        print(f'  [{s}] title={t} | url={u}')
    print(f'\nTotal: {len(results)}, Found: {found}, Missing: {len(results) - found}')

asyncio.run(test())
