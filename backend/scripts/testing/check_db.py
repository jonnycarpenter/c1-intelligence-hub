import sqlite3
import os

db_path = 'backend/data/c1_corpus.db'

print(f"\nChecking {db_path}...")
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check weekly_briefings
        cursor.execute("SELECT * FROM weekly_briefings ORDER BY rowid DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            print("Latest Weekly Briefing:")
            for key in row.keys():
                print(f"  {key}: {row[key]}")
        else:
            print("No weekly briefings found.")

        # Check pre_briefings count
        count = cursor.execute("SELECT count(*) FROM pre_briefings").fetchone()[0]
        print(f"Pre-Briefings count: {count}")
            
        conn.close()
    except Exception as e:
        print(f"  Error: {e}")
else:
    print("DB not found.")
