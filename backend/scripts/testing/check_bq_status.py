from google.cloud import bigquery
from datetime import datetime
import os

PROJECT_ID = "<GCP_PROJECT_ID>"
DATASET = "c1_intelligence"
TODAY = datetime.utcnow().date()

def check_bq():
    print(f"Checking BigQuery for {TODAY}...")
    try:
        client = bigquery.Client(project=PROJECT_ID)
        
        # Check Pre-Briefings
        query_pre = f"""
        SELECT COUNT(*) as cnt 
        FROM `{PROJECT_ID}.{DATASET}.pre_briefings` 
        WHERE DATE(generated_at) = CURRENT_DATE()
        """
        job_pre = client.query(query_pre)
        pre_count = list(job_pre.result())[0].cnt
        print(f"Pre-Briefings (Today): {pre_count}")
        
        # Check Weekly Briefings
        query_weekly = f"""
        SELECT COUNT(*) as cnt 
        FROM `{PROJECT_ID}.{DATASET}.weekly_briefings` 
        WHERE DATE(generated_at) = CURRENT_DATE()
        """
        job_weekly = client.query(query_weekly)
        weekly_count = list(job_weekly.result())[0].cnt
        print(f"Weekly Briefings (Today): {weekly_count}")
        
        return pre_count, weekly_count
        
    except Exception as e:
        print(f"Error checking BigQuery: {e}")
        return 0, 0

if __name__ == "__main__":
    check_bq()
