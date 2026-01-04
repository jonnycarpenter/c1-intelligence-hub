"""Debug date extraction for specific URLs."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from app.utils.date_extraction import extract_date_from_url, extract_date_from_content, extract_publication_date

DB_PATH = "data/c1_timeseries.db"

conn = sqlite3.connect(DB_PATH)

# Get sample articles that still have issues
cur = conn.execute("""
    SELECT url, summary, source_type 
    FROM articles 
    WHERE published_at LIKE '%17:33:55%'
    LIMIT 20
""")

print("Testing date extraction on problematic articles:\n")
for url, summary, source_type in cur.fetchall():
    print(f"Source: {source_type}")
    print(f"URL: {url}")
    
    url_date = extract_date_from_url(url)
    print(f"URL extraction: {url_date}")
    
    content_date = extract_date_from_content(summary or "", None)
    print(f"Content extraction: {content_date}")
    
    full_date = extract_publication_date(url, summary, None, None)
    print(f"Full extraction (with fallback=None): {full_date}")
    
    print(f"Summary preview: {(summary or '')[:200]}...")
    print("-" * 80)
    print()

conn.close()
