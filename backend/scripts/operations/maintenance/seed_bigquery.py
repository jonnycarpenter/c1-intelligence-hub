"""
Seed BigQuery tables with data from CSV files.
Run this script to populate BigQuery with the master lists data.
"""

import pandas as pd
from google.cloud import bigquery
from datetime import datetime
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ID = "<GCP_PROJECT_ID>"
DATASET_ID = "c1_intelligence"

# Path to resources files (the master source of truth)
RESOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "resources")


def get_client():
    return bigquery.Client(project=PROJECT_ID)


def seed_companies(client):
    """Load companies from CSV to BigQuery with ALL columns including new ones."""
    csv_path = os.path.join(RESOURCES_DIR, "master_company_list.csv")
    df = pd.read_csv(csv_path)
    
    print(f"Read {len(df)} companies from CSV")
    print(f"Columns in CSV: {list(df.columns)}")
    
    # Add timestamps
    now = datetime.utcnow().isoformat()
    df['created_at'] = now
    df['updated_at'] = now
    
    # Include ALL columns from CSV plus timestamps
    # New columns: website, is_c1_supplier, supplier_categories, supplier_source
    columns = ['company_id', 'company', 'type', 'stock_ticker', 
               'industries_served', 'description', 'processes_services',
               'website', 'is_c1_supplier', 'supplier_categories', 'supplier_source',
               'created_at', 'updated_at']
    
    # Only select columns that exist in the dataframe
    available_columns = [col for col in columns if col in df.columns]
    df = df[available_columns]
    
    table_id = f"{PROJECT_ID}.{DATASET_ID}.companies"
    
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,  # Let BigQuery auto-detect schema for new columns
    )
    
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    
    print(f"Loaded {len(df)} companies to BigQuery with columns: {available_columns}")


def seed_materials(client):
    """Load materials from CSV to BigQuery."""
    csv_path = os.path.join(RESOURCES_DIR, "master_materials_list.csv")
    df = pd.read_csv(csv_path)
    
    print(f"Read {len(df)} materials from CSV")
    
    # Add timestamps
    now = datetime.utcnow().isoformat()
    df['created_at'] = now
    df['updated_at'] = now
    
    # Ensure column order matches schema
    columns = ['material_proc_id', 'material_process_name', 'type',
               'est_manufacturer_margin_tier', 'industries_served', 'examples',
               'created_at', 'updated_at']
    df = df[columns]
    
    table_id = f"{PROJECT_ID}.{DATASET_ID}.materials"
    
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    
    print(f"Loaded {len(df)} materials to BigQuery")


def seed_industries(client):
    """Load industries from CSV to BigQuery.
    
    Note: The CSV has different columns than BigQuery schema, so we need to transform.
    CSV: industry_id, industry_name, description, key_materials, key_processes
    BQ:  industry, application, end_users, naics_code, naics_description, 
         industry_priority_flag, example_products
    """
    csv_path = os.path.join(RESOURCES_DIR, "master_industries_list.csv")
    df = pd.read_csv(csv_path)
    
    print(f"Read {len(df)} industries from CSV")
    
    # Transform CSV columns to BQ schema
    transformed = pd.DataFrame({
        'industry': df['industry_name'],
        'application': df['description'],
        'end_users': df['key_materials'],  # Reusing field
        'naics_code': '',
        'naics_description': '',
        'industry_priority_flag': 'Y',  # All industries are priority
        'example_products': df['key_processes'],  # Reusing field
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
    })
    
    table_id = f"{PROJECT_ID}.{DATASET_ID}.industries"
    
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    
    job = client.load_table_from_dataframe(transformed, table_id, job_config=job_config)
    job.result()
    
    print(f"Loaded {len(transformed)} industries to BigQuery")


def main():
    print("Seeding BigQuery tables...")
    client = get_client()
    
    print("\n--- Companies ---")
    seed_companies(client)
    
    print("\n--- Materials ---")
    seed_materials(client)
    
    print("\n--- Industries ---")
    seed_industries(client)
    
    print("\nDone! Verifying counts...")
    
    # Verify
    for table in ['companies', 'materials', 'industries']:
        query = f"SELECT COUNT(*) as cnt FROM `{PROJECT_ID}.{DATASET_ID}.{table}`"
        result = list(client.query(query).result())[0]
        print(f"  {table}: {result.cnt} rows")


if __name__ == "__main__":
    main()
