"""Update podcast URL to use API endpoint."""

from google.cloud import bigquery

client = bigquery.Client(project='gen-lang-client-0436975498')

briefing_id = 'c21f6cdc-1b55-4d1b-9a89-51aff8aa905f'
# Use the backend API endpoint for the podcast URL
podcast_url = f'/api/podcast/briefing/{briefing_id}'

update_query = f"""
UPDATE `gen-lang-client-0436975498.c1_intelligence.weekly_briefings`
SET podcast_url = '{podcast_url}'
WHERE id = '{briefing_id}'
"""

client.query(update_query).result()
print(f'✅ Updated podcast URL to: {podcast_url}')

# Verify
verify = """
SELECT id, podcast_url, podcast_duration_seconds 
FROM `gen-lang-client-0436975498.c1_intelligence.weekly_briefings`
WHERE id = 'c21f6cdc-1b55-4d1b-9a89-51aff8aa905f'
"""
result = list(client.query(verify).result())[0]
print(f'Verified URL: {result.podcast_url}')
print(f'Duration: {result.podcast_duration_seconds}s')
