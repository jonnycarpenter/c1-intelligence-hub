#!/usr/bin/env python
"""Test Agent 2 briefing save with the latest pre-brief."""

import asyncio
import json
import sys
import logging

# Enable verbose logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_agent2():
    from app.db.gcp_storage import BigQueryDataStorage, gcp_config
    
    storage = BigQueryDataStorage(gcp_config)
    await storage.initialize()
    
    # Get the latest pre-brief
    query = '''
        SELECT *
        FROM `<GCP_PROJECT_ID>.c1_intelligence.pre_briefings`
        ORDER BY generated_at DESC
        LIMIT 1
    '''
    
    job = storage.client.query(query)
    results = list(job.result())
    
    if not results:
        print('No pre-brief found!')
        return
    
    row = dict(results[0])
    print(f'Got pre-brief from {row["generated_at"]}')
    print(f'Article count: {row["article_count"]}')
    
    # Parse JSON fields
    pre_brief = {
        'id': row['id'],
        'period_start': row['period_start'],
        'period_end': row['period_end'],
        'article_count': row['article_count'],
        'article_ids': json.loads(row['article_ids']) if row['article_ids'] else [],
        'data': json.loads(row['data']) if row['data'] else {},
    }
    
    print(f'Parsed pre_brief with {len(pre_brief["article_ids"])} article IDs')
    print(f'Data keys: {list(pre_brief["data"].keys()) if pre_brief["data"] else "empty"}')
    
    # Now try to run Agent 2
    print('\n--- Running Agent 2 ---')
    from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
    
    try:
        agent2 = WeeklyBriefingGenerator()
        print('Agent 2 initialized, calling generate()...')
        result = await agent2.generate(pre_brief=pre_brief)
        
        if result:
            print(f'\nSUCCESS! Briefing ID: {result["id"]}')
            print(f'Title: {result.get("briefing_title")}')
            print(f'Sections: {len(result.get("sections", []))}')
        else:
            print('\nFAILED - Agent 2 returned None')
    except Exception as e:
        print(f'\nEXCEPTION during Agent 2: {e}')
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(test_agent2())
    except Exception as e:
        print(f'Top-level exception: {e}')
        import traceback
        traceback.print_exc()
