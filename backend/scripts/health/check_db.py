import sqlite3
import os

db_path = 'data/c1_corpus.db'
print('DB exists:', os.path.exists(db_path))

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print('Tables:', tables)
    
    # Check corpus_items count
    if 'corpus_items' in tables:
        cur.execute('SELECT COUNT(*) FROM corpus_items')
        print('Corpus items count:', cur.fetchone()[0])
        
        # Check recent articles
        cur.execute('SELECT id, title, published_at FROM corpus_items ORDER BY published_at DESC LIMIT 5')
        print('\nRecent articles:')
        for row in cur.fetchall():
            print(f"  - {row[1][:60]}... ({row[2]})")
    
    # Check digests table
    if 'digests' in tables:
        cur.execute('SELECT COUNT(*) FROM digests')
        count = cur.fetchone()[0]
        print('\nDigest count:', count)
        
        if count > 0:
            cur.execute('SELECT id, generated_at FROM digests ORDER BY generated_at DESC LIMIT 3')
            print('\nExisting digests:')
            for row in cur.fetchall():
                print(f"  - ID: {row[0][:20]}... ({row[1]})")
    
    # Check briefing_summaries
    if 'briefing_summaries' in tables:
        cur.execute('SELECT COUNT(*) FROM briefing_summaries')
        count = cur.fetchone()[0]
        print('\nBriefing count:', count)
        
        if count > 0:
            cur.execute('SELECT category, headline, generated_at FROM briefing_summaries ORDER BY generated_at DESC')
            print('\nExisting briefings:')
            for row in cur.fetchall():
                print(f"  - [{row[0]}] {row[1][:60]}... ({row[2]})")
    else:
        print('\nbriefing_summaries table does not exist')
    
    conn.close()
