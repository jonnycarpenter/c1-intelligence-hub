from google.cloud import bigquery
import json
import datetime

def serialize(obj):
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    return str(obj)

try:
    client = bigquery.Client(project="<GCP_PROJECT_ID>")
    table_id = "<GCP_PROJECT_ID>.c1_intelligence.digest_items"

    # Get schema
    table = client.get_table(table_id)
    schema = [{"name": f.name, "type": f.field_type, "mode": f.mode} for f in table.schema]

    # Get count
    count_query = f"SELECT COUNT(*) as cnt FROM `{table_id}`"
    count_job = client.query(count_query)
    count = list(count_job.result())[0].cnt
    print(f"TOTAL_ROWS: {count}")

    # Get example rows
    query = f"SELECT id, title, industries FROM `{table_id}` ORDER BY ingested_at DESC LIMIT 50"

    query_job = client.query(query)
    results = query_job.result()
    
    rows = []
    for row in results:
        row_dict = dict(row.items())
        serialized_row = {k: serialize(v) if not isinstance(v, (str, int, float, bool, type(None))) else v for k, v in row_dict.items()}
        rows.append(serialized_row)

    output = {
        "schema": schema,
        "sample_rows": rows
    }

    
    with open("bq_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print("SUCCESS")
except Exception as e:
    with open("bq_results.json", "w") as f:
        json.dump({"error": str(e)}, f, indent=2)
    print("FAILED")

