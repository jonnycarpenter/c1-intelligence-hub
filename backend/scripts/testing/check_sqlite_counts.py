import asyncio
import aiosqlite
import os
from pathlib import Path

async def check_counts():
    db_path = Path("backend/data/c1_corpus.db")
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    print(f"Checking database at {db_path}")
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT source_type, COUNT(*) as cnt FROM corpus_items GROUP BY source_type ORDER BY cnt DESC") as cursor:
            print("\nCounts by source_type in SQLite:")
            print(f"{'source_type':<20} | {'count':<5}")
            print("-" * 28)
            async for row in cursor:
                print(f"{row[0]:<20} | {row[1]:<5}")

if __name__ == "__main__":
    asyncio.run(check_counts())
