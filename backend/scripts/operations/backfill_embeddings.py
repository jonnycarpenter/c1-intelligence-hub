"""
Backfill Semantic Embeddings for Quote/Nugget Tables
=====================================================

Adds vector embeddings to existing rows in earnings_quotes, sec_filing_nuggets,
and podcast_quotes tables that don't have embeddings yet.

This enables semantic (vector) search so MCP tools can find results from
natural-language queries like "any themes related to hexcel" instead of
requiring exact substring matches.

Prerequisites:
    - BigQuery tables must already have 'embedding' and 'embedding_model' columns.
      If they don't, run the ALTER TABLE commands below first:

      ALTER TABLE `project.dataset.earnings_quotes` ADD COLUMN IF NOT EXISTS embedding ARRAY<FLOAT64>;
      ALTER TABLE `project.dataset.earnings_quotes` ADD COLUMN IF NOT EXISTS embedding_model STRING;

      (Same for sec_filing_nuggets and podcast_quotes)

Usage:
    cd backend
    python scripts/operations/backfill_embeddings.py                    # All 3 tables
    python scripts/operations/backfill_embeddings.py --table earnings   # Just earnings
    python scripts/operations/backfill_embeddings.py --table sec        # Just SEC nuggets
    python scripts/operations/backfill_embeddings.py --table podcast    # Just podcasts
    python scripts/operations/backfill_embeddings.py --batch-size 100   # Custom batch
    python scripts/operations/backfill_embeddings.py --stats            # Show stats only
    python scripts/operations/backfill_embeddings.py --alter-tables     # Add columns first
"""

import asyncio
import argparse
import logging
import sys
import os
import time
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, str(BACKEND_DIR))

# Load .env BEFORE importing app modules that read env vars at import time
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

from app.db.gcp_storage import get_storage, gcp_config
from app.db.semantic_search import get_semantic_searcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_embeddings")


# =========================================================================
# Alter tables (add embedding columns to existing tables)
# =========================================================================

async def alter_tables():
    """Add embedding columns to existing tables via ALTER TABLE."""
    from google.cloud import bigquery
    client = bigquery.Client(project=gcp_config.project_id)
    dataset = gcp_config.full_dataset_id

    tables = ["earnings_quotes", "sec_filing_nuggets", "podcast_quotes"]

    for table_name in tables:
        table_id = f"{dataset}.{table_name}"
        for col_name, col_type in [("embedding", "ARRAY<FLOAT64>"), ("embedding_model", "STRING")]:
            sql = f"ALTER TABLE `{table_id}` ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
            try:
                client.query(sql).result()
                logger.info(f"✅ Added {col_name} to {table_name}")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info(f"  {col_name} already exists on {table_name}")
                else:
                    logger.error(f"❌ Failed to add {col_name} to {table_name}: {e}")


# =========================================================================
# Stats
# =========================================================================

async def show_stats():
    """Show embedding coverage for all 3 tables."""
    from google.cloud import bigquery
    client = bigquery.Client(project=gcp_config.project_id)
    dataset = gcp_config.full_dataset_id

    tables = [
        ("earnings_quotes", "quote_id"),
        ("sec_filing_nuggets", "nugget_id"),
        ("podcast_quotes", "id"),
    ]

    print(f"\n📊 Embedding Coverage Stats")
    print(f"{'='*60}")

    for table_name, id_col in tables:
        table_id = f"{dataset}.{table_name}"
        try:
            sql = f"""
                SELECT
                    COUNT(*) as total,
                    COUNTIF(embedding IS NOT NULL AND ARRAY_LENGTH(embedding) > 0) as with_embedding,
                    COUNTIF(embedding IS NULL OR ARRAY_LENGTH(embedding) = 0) as without_embedding
                FROM `{table_id}`
            """
            rows = list(client.query(sql).result())
            if rows:
                r = rows[0]
                total = r.total
                with_emb = r.with_embedding
                without_emb = r.without_embedding
                pct = (with_emb / total * 100) if total > 0 else 0
                print(f"\n  {table_name}:")
                print(f"    Total rows:       {total:,}")
                print(f"    With embedding:   {with_emb:,} ({pct:.1f}%)")
                print(f"    Without embedding:{without_emb:,}")
        except Exception as e:
            print(f"\n  {table_name}: Error - {e}")

    print()


# =========================================================================
# Backfill functions
# =========================================================================

async def backfill_earnings_quotes(batch_size: int = 200, max_rows: int = 0):
    """Backfill embeddings for earnings_quotes rows missing them."""
    from google.cloud import bigquery
    from google.cloud.bigquery import QueryJobConfig

    client = bigquery.Client(project=gcp_config.project_id)
    dataset = gcp_config.full_dataset_id
    table_id = f"{dataset}.earnings_quotes"

    searcher = await get_semantic_searcher()
    if not searcher.is_available:
        logger.error("❌ Embedding model not available. Cannot backfill.")
        return

    # Get rows without embeddings
    limit_clause = f"LIMIT {max_rows}" if max_rows > 0 else ""
    sql = f"""
        SELECT *
        FROM `{table_id}`
        WHERE embedding IS NULL OR ARRAY_LENGTH(embedding) = 0
        ORDER BY extracted_at DESC
        {limit_clause}
    """
    rows = list(client.query(sql).result())
    total = len(rows)
    logger.info(f"[EARNINGS] Found {total} rows without embeddings")

    if total == 0:
        return

    processed = 0
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        batch_dicts = [dict(r) for r in batch]

        texts = [searcher.build_embed_text_for_earnings(d) for d in batch_dicts]
        embeddings = await searcher.embed_texts(texts)

        if not embeddings or len(embeddings) != len(batch):
            logger.error(f"[EARNINGS] Embedding batch {i}-{i+len(batch)} failed")
            continue

        # Update rows via DML (BigQuery supports UPDATE)
        for j, (row_dict, emb) in enumerate(zip(batch_dicts, embeddings)):
            quote_id = row_dict.get("quote_id")
            if not quote_id:
                continue

            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            update_sql = f"""
                UPDATE `{table_id}`
                SET embedding = {emb_str},
                    embedding_model = 'text-embedding-004'
                WHERE quote_id = @quote_id
            """
            try:
                job_config = QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("quote_id", "STRING", quote_id)]
                )
                client.query(update_sql, job_config=job_config).result()
            except Exception as e:
                logger.error(f"[EARNINGS] Update failed for {quote_id}: {e}")

        processed += len(batch)
        logger.info(f"[EARNINGS] Processed {processed}/{total} rows")
        # Brief pause to avoid Vertex AI rate limits
        if i + batch_size < total:
            await asyncio.sleep(1)

    logger.info(f"[EARNINGS] ✅ Backfill complete: {processed} rows processed")


async def backfill_sec_nuggets(batch_size: int = 200, max_rows: int = 0):
    """Backfill embeddings for sec_filing_nuggets rows missing them."""
    from google.cloud import bigquery
    from google.cloud.bigquery import QueryJobConfig

    client = bigquery.Client(project=gcp_config.project_id)
    dataset = gcp_config.full_dataset_id
    table_id = f"{dataset}.sec_filing_nuggets"

    searcher = await get_semantic_searcher()
    if not searcher.is_available:
        logger.error("❌ Embedding model not available. Cannot backfill.")
        return

    limit_clause = f"LIMIT {max_rows}" if max_rows > 0 else ""
    sql = f"""
        SELECT *
        FROM `{table_id}`
        WHERE embedding IS NULL OR ARRAY_LENGTH(embedding) = 0
        ORDER BY extracted_at DESC
        {limit_clause}
    """
    rows = list(client.query(sql).result())
    total = len(rows)
    logger.info(f"[SEC] Found {total} rows without embeddings")

    if total == 0:
        return

    processed = 0
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        batch_dicts = [dict(r) for r in batch]

        texts = [searcher.build_embed_text_for_sec(d) for d in batch_dicts]
        embeddings = await searcher.embed_texts(texts)

        if not embeddings or len(embeddings) != len(batch):
            logger.error(f"[SEC] Embedding batch {i}-{i+len(batch)} failed")
            continue

        for j, (row_dict, emb) in enumerate(zip(batch_dicts, embeddings)):
            nugget_id = row_dict.get("nugget_id")
            if not nugget_id:
                continue

            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            update_sql = f"""
                UPDATE `{table_id}`
                SET embedding = {emb_str},
                    embedding_model = 'text-embedding-004'
                WHERE nugget_id = @nugget_id
            """
            try:
                job_config = QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("nugget_id", "STRING", nugget_id)]
                )
                client.query(update_sql, job_config=job_config).result()
            except Exception as e:
                logger.error(f"[SEC] Update failed for {nugget_id}: {e}")

        processed += len(batch)
        logger.info(f"[SEC] Processed {processed}/{total} rows")
        if i + batch_size < total:
            await asyncio.sleep(1)

    logger.info(f"[SEC] ✅ Backfill complete: {processed} rows processed")


async def backfill_podcast_quotes(batch_size: int = 200, max_rows: int = 0):
    """Backfill embeddings for podcast_quotes rows missing them."""
    from google.cloud import bigquery
    from google.cloud.bigquery import QueryJobConfig

    client = bigquery.Client(project=gcp_config.project_id)
    dataset = gcp_config.full_dataset_id
    table_id = f"{dataset}.podcast_quotes"

    searcher = await get_semantic_searcher()
    if not searcher.is_available:
        logger.error("❌ Embedding model not available. Cannot backfill.")
        return

    limit_clause = f"LIMIT {max_rows}" if max_rows > 0 else ""
    sql = f"""
        SELECT *
        FROM `{table_id}`
        WHERE embedding IS NULL OR ARRAY_LENGTH(embedding) = 0
        ORDER BY extracted_at DESC
        {limit_clause}
    """
    rows = list(client.query(sql).result())
    total = len(rows)
    logger.info(f"[PODCAST] Found {total} rows without embeddings")

    if total == 0:
        return

    processed = 0
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        batch_dicts = [dict(r) for r in batch]

        texts = [searcher.build_embed_text_for_podcast(d) for d in batch_dicts]
        embeddings = await searcher.embed_texts(texts)

        if not embeddings or len(embeddings) != len(batch):
            logger.error(f"[PODCAST] Embedding batch {i}-{i+len(batch)} failed")
            continue

        for j, (row_dict, emb) in enumerate(zip(batch_dicts, embeddings)):
            row_id = row_dict.get("id")
            if not row_id:
                continue

            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            update_sql = f"""
                UPDATE `{table_id}`
                SET embedding = {emb_str},
                    embedding_model = 'text-embedding-004'
                WHERE id = @row_id
            """
            try:
                job_config = QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("row_id", "STRING", row_id)]
                )
                client.query(update_sql, job_config=job_config).result()
            except Exception as e:
                logger.error(f"[PODCAST] Update failed for {row_id}: {e}")

        processed += len(batch)
        logger.info(f"[PODCAST] Processed {processed}/{total} rows")
        if i + batch_size < total:
            await asyncio.sleep(1)

    logger.info(f"[PODCAST] ✅ Backfill complete: {processed} rows processed")


# =========================================================================
# Main
# =========================================================================

async def main():
    parser = argparse.ArgumentParser(description="Backfill semantic embeddings for quote/nugget tables")
    parser.add_argument("--table", choices=["earnings", "sec", "podcast", "all"], default="all",
                        help="Which table to backfill (default: all)")
    parser.add_argument("--batch-size", type=int, default=200,
                        help="Embedding batch size (default: 200)")
    parser.add_argument("--max-rows", type=int, default=0,
                        help="Max rows to process per table (0 = all)")
    parser.add_argument("--stats", action="store_true",
                        help="Show embedding coverage stats and exit")
    parser.add_argument("--alter-tables", action="store_true",
                        help="Add embedding columns to existing tables first")
    args = parser.parse_args()

    if args.stats:
        await show_stats()
        return

    if args.alter_tables:
        print("\n🔧 Adding embedding columns to tables...")
        await alter_tables()
        print("Done. Run --stats to verify.\n")
        return

    start = time.time()
    table = args.table

    print(f"\n🚀 Starting embedding backfill (table={table}, batch_size={args.batch_size})")
    print(f"{'='*60}\n")

    if table in ("earnings", "all"):
        await backfill_earnings_quotes(batch_size=args.batch_size, max_rows=args.max_rows)

    if table in ("sec", "all"):
        await backfill_sec_nuggets(batch_size=args.batch_size, max_rows=args.max_rows)

    if table in ("podcast", "all"):
        await backfill_podcast_quotes(batch_size=args.batch_size, max_rows=args.max_rows)

    elapsed = time.time() - start
    print(f"\n✅ Backfill completed in {elapsed:.1f}s")
    print(f"\nRun with --stats to see coverage.\n")


if __name__ == "__main__":
    asyncio.run(main())
