"""Delete test briefings from BigQuery."""
from google.cloud import bigquery

c = bigquery.Client()
q = """DELETE FROM `<GCP_PROJECT_ID>.c1_intelligence.weekly_briefings` 
       WHERE briefing_title LIKE 'DEBUG%' OR briefing_title LIKE 'Test%'"""
c.query(q).result()
print('Deleted test rows')

# Show remaining
r = list(c.query('SELECT briefing_title, generated_at FROM `<GCP_PROJECT_ID>.c1_intelligence.weekly_briefings` ORDER BY generated_at DESC').result())
print(f'\n{len(r)} briefings remaining:')
for x in r:
    print(f'  {x.generated_at}: {x.briefing_title[:50]}')
