"""
Narrative Enrichment Backfill Script
=====================================
Re-classifies digest_items from Nov 1 2025 onward with full narrative enrichment:
- materials (specific composites materials mentioned)
- industries (vertical markets)
- companies (structured extraction)
- event_type (acquisition, partnership, expansion, contract, etc.)
- sentiment (positive, negative, neutral)
- geography (regions/countries)
- themes (narrative threads: reshoring, sustainability, consolidation, etc.)
- headline (punchy 5-8 word headline)

Architecture:
- SOURCE: articles table (has full_text for better classification)
- JOIN: digest_items → articles via URL
- UPDATE: digest_items with enriched fields
- INSERT: article_tags with normalized tags

Usage:
    # Dry run (first 10 items, no writes)
    python scripts/backfill_narrative_enrichment.py --dry-run --limit 10

    # Small test batch  
    python scripts/backfill_narrative_enrichment.py --limit 50

    # Full backfill from Nov 1
    python scripts/backfill_narrative_enrichment.py

    # Specific month
    python scripts/backfill_narrative_enrichment.py --start-date 2025-12-01 --end-date 2026-01-01

Cost estimate (Claude Haiku):
    ~8000 items × ~1500 tokens/item = ~12M tokens
    At $0.25/M input + $1.25/M output ≈ $3-5 total
"""

import asyncio
import json
import logging
import argparse
import time
import re
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from google.cloud import bigquery

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ID = "gen-lang-client-0436975498"
DATASET_ID = "c1_intelligence"
FULL_DATASET = f"{PROJECT_ID}.{DATASET_ID}"

# Batch size for LLM calls (rate limiting)
BATCH_SIZE = 20
CONCURRENT_LIMIT = 10  # Max concurrent LLM calls
SLEEP_BETWEEN_BATCHES = 1.0  # seconds
API_TIMEOUT = 60  # seconds per API call before giving up

# Model to use for enrichment (Haiku is fast + cheap)
ENRICHMENT_MODEL = "claude-3-5-haiku-20241022"

# ============================================================================
# Enrichment Prompt
# ============================================================================

NARRATIVE_ENRICHMENT_PROMPT = """You are enriching a composites industry intelligence article for a narrative tracking system.

Analyze this article and extract structured metadata. Be specific and precise.

<article>
Title: {title}
Source: {source_name}
Content: {content}
</article>

Respond with ONLY valid JSON (no markdown, no code blocks):

{{
    "companies": ["Company1", "Company2"],
    "materials": ["carbon fiber", "epoxy resin"],
    "industries": ["Aerospace", "Wind", "Construction", "Marine", "Automotive", "Infrastructure", "Transportation", "Sporting Goods", "Defense Space", "Industrial"],
    "event_type": "acquisition|partnership|expansion|contract|regulatory_change|product_launch|earnings|facility_closure|restructuring|investment|supply_disruption|technology|market_shift|other",
    "sentiment": "positive|negative|neutral",
    "geography": ["North America", "Europe", "China"],
    "themes": ["reshoring", "sustainability"],
    "headline": "Punchy 5-8 Word Headline"
}}

EXTRACTION RULES:
- "companies": ALL company names mentioned. Include suppliers, OEMs, customers, partners. Use official names (e.g., "Hexcel Corporation" not just "Hexcel").
- "materials": Specific composites materials ONLY. Examples: "carbon fiber", "epoxy resin", "PEEK", "glass fiber", "prepreg", "vinyl ester", "SMC", "BMC", "aramid", "Kevlar", "basalt fiber", "PVC foam core", "honeycomb core", "polyester resin", "polyurethane". Do NOT include generic terms like "composites" or "materials".
- "industries": Select from the enumerated list. Multiple allowed.
- "event_type": Pick the SINGLE most applicable type from the list.
- "sentiment": Overall market sentiment for composites industry (not article tone).
- "geography": Regions/countries where the activity is happening. Use: "North America", "United States", "Europe", "Germany", "France", "UK", "China", "Japan", "South Korea", "India", "Middle East", "Southeast Asia", "Mexico", "Brazil", "Australia", or specific countries.
- "themes": High-level narrative threads. Choose from: "reshoring", "nearshoring", "sustainability", "recycling", "consolidation", "capacity_expansion", "supply_chain_risk", "trade_policy", "cost_pressure", "demand_growth", "technology_advancement", "workforce", "automation", "electrification", "hydrogen", "defense_spending", "infrastructure_investment", "regulatory_pressure", "decarbonization", "lightweighting", "digitalization". Multiple allowed but be selective (2-4 max).
- "headline": Rewrite title as a punchy 5-8 word headline capturing the core event/signal. Must convey what happened and why it matters.
"""


# ============================================================================
# Schema Migration
# ============================================================================

def add_narrative_columns(client: bigquery.Client):
    """Add new narrative enrichment columns to digest_items table if they don't exist."""
    table_id = f"{FULL_DATASET}.digest_items"
    table = client.get_table(table_id)
    
    existing_fields = {f.name for f in table.schema}
    
    new_fields = [
        bigquery.SchemaField("event_type", "STRING"),
        bigquery.SchemaField("sentiment", "STRING"),
        bigquery.SchemaField("geography", "STRING"),  # JSON array
        bigquery.SchemaField("themes", "STRING"),  # JSON array
        bigquery.SchemaField("narrative_enriched_at", "TIMESTAMP"),
    ]
    
    fields_to_add = [f for f in new_fields if f.name not in existing_fields]
    
    if not fields_to_add:
        logger.info("All narrative columns already exist in digest_items table")
        return
    
    new_schema = list(table.schema) + fields_to_add
    table.schema = new_schema
    client.update_table(table, ["schema"])
    logger.info(f"Added columns to digest_items: {[f.name for f in fields_to_add]}")


# ============================================================================
# Data Fetching
# ============================================================================

def fetch_items_to_enrich(
    client: bigquery.Client,
    start_date: str = "2025-11-01",
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    skip_already_enriched: bool = True,
) -> List[Dict[str, Any]]:
    """
    Fetch digest_items joined with articles (for full_text) that need enrichment.
    
    Returns list of dicts with all fields needed for re-classification.
    """
    end_clause = f"AND d.published_at < '{end_date}'" if end_date else ""
    enriched_clause = "AND d.narrative_enriched_at IS NULL" if skip_already_enriched else ""
    limit_clause = f"LIMIT {limit}" if limit else ""
    
    # Also exclude future-dated items (bad date parsing)
    query = f"""
        SELECT 
            d.id as digest_id,
            d.article_id,
            d.title,
            d.url,
            d.published_at,
            d.source_name,
            d.source_type,
            d.category,
            d.priority,
            d.digest_summary,
            d.original_summary,
            d.companies as existing_companies,
            d.materials as existing_materials,
            d.industries as existing_industries,
            d.headline as existing_headline,
            -- Join to articles for full_text
            COALESCE(a.full_text, d.digest_summary, d.original_summary) as content,
            a.full_text IS NOT NULL as has_full_text
        FROM `{FULL_DATASET}.digest_items` d
        LEFT JOIN `{FULL_DATASET}.articles` a ON d.url = a.url
        WHERE d.published_at >= '{start_date}'
            AND d.published_at <= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)
            {end_clause}
            {enriched_clause}
        ORDER BY d.published_at DESC
        {limit_clause}
    """
    
    items = []
    for row in client.query(query):
        items.append({
            "digest_id": row.digest_id,
            "article_id": row.article_id,
            "title": row.title,
            "url": row.url,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "source_name": row.source_name or "",
            "source_type": row.source_type or "",
            "category": row.category,
            "priority": row.priority,
            "digest_summary": row.digest_summary or "",
            "original_summary": row.original_summary or "",
            "existing_companies": row.existing_companies,
            "existing_materials": row.existing_materials,
            "existing_industries": row.existing_industries,
            "existing_headline": row.existing_headline,
            "content": row.content or "",
            "has_full_text": row.has_full_text,
        })
    
    logger.info(f"Fetched {len(items)} items to enrich")
    has_ft = sum(1 for i in items if i["has_full_text"])
    logger.info(f"  With full_text: {has_ft} ({100*has_ft//len(items) if items else 0}%)")
    
    return items


# ============================================================================
# LLM Enrichment
# ============================================================================

async def enrich_single_item(
    item: Dict[str, Any],
    anthropic_client,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    """Enrich a single item using Claude."""
    async with semaphore:
        # Prepare content (truncate if needed)
        content = item["content"] or item["digest_summary"] or item["original_summary"] or item["title"]
        if len(content) > 4000:
            content = content[:4000] + "..."
        
        prompt = NARRATIVE_ENRICHMENT_PROMPT.format(
            title=item["title"],
            source_name=item["source_name"],
            content=content,
        )
        
        try:
            response = await asyncio.wait_for(
                anthropic_client.messages.create(
                    model=ENRICHMENT_MODEL,
                    max_tokens=800,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=API_TIMEOUT,
            )
            
            result_text = response.content[0].text.strip()
            
            # Clean markdown code blocks
            if result_text.startswith("```"):
                result_text = re.sub(r'^```json?\n?', '', result_text)
                result_text = re.sub(r'\n?```$', '', result_text)
            
            # Handle LLM returning multiple JSON blocks (Extra data error)
            try:
                data = json.loads(result_text)
            except json.JSONDecodeError:
                # Try extracting first JSON object
                match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result_text)
                if match:
                    data = json.loads(match.group())
                else:
                    raise
            
            return {
                "digest_id": item["digest_id"],
                "article_id": item["article_id"],
                "title": item["title"],
                "url": item["url"],
                "published_at": item["published_at"],
                "source_name": item["source_name"],
                "source_type": item["source_type"],
                # Enriched fields
                "companies": data.get("companies", []),
                "materials": data.get("materials", []),
                "industries": data.get("industries", []),
                "event_type": data.get("event_type", "other"),
                "sentiment": data.get("sentiment", "neutral"),
                "geography": data.get("geography", []),
                "themes": data.get("themes", []),
                "headline": data.get("headline", ""),
                "success": True,
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error for {item['digest_id'][:8]}: {e}")
            return {"digest_id": item["digest_id"], "success": False, "error": str(e)}
        except asyncio.TimeoutError:
            logger.warning(f"Timeout ({API_TIMEOUT}s) for {item['digest_id'][:8]}")
            return {"digest_id": item["digest_id"], "success": False, "error": "timeout"}
        except Exception as e:
            logger.warning(f"Enrichment error for {item['digest_id'][:8]}: {e}")
            return {"digest_id": item["digest_id"], "success": False, "error": str(e)}


async def enrich_batch(
    items: List[Dict[str, Any]],
    anthropic_client,
) -> List[Dict[str, Any]]:
    """Enrich a batch of items concurrently."""
    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    
    tasks = [
        enrich_single_item(item, anthropic_client, semaphore)
        for item in items
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    enriched = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Batch exception: {r}")
        elif isinstance(r, dict):
            enriched.append(r)
    
    return enriched


# ============================================================================
# BigQuery Updates — Staging Table + MERGE (fast bulk writes)
# ============================================================================

STAGING_TABLE = f"{FULL_DATASET}.narrative_enrichment_staging"

STAGING_SCHEMA = [
    bigquery.SchemaField("digest_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("companies", "STRING"),
    bigquery.SchemaField("materials", "STRING"),
    bigquery.SchemaField("industries", "STRING"),
    bigquery.SchemaField("event_type", "STRING"),
    bigquery.SchemaField("sentiment", "STRING"),
    bigquery.SchemaField("geography", "STRING"),
    bigquery.SchemaField("themes", "STRING"),
    bigquery.SchemaField("headline", "STRING"),
]


def write_staging_table(
    client: bigquery.Client,
    enriched_items: List[Dict[str, Any]],
    dry_run: bool = False,
) -> int:
    """
    Load enriched results into a staging table via BQ load API.
    
    load_table_from_json uses the load API (not streaming), so the staging
    table has NO streaming buffer — enabling a fast MERGE afterwards.
    """
    successful = [i for i in enriched_items if i.get("success")]
    if not successful:
        return 0
    
    # Deduplicate by digest_id (keep last enrichment if same item enriched twice)
    seen = {}
    for item in successful:
        seen[item["digest_id"]] = item
    
    rows = []
    for item in seen.values():
        rows.append({
            "digest_id": item["digest_id"],
            "companies": json.dumps(item["companies"]),
            "materials": json.dumps(item["materials"]),
            "industries": json.dumps(item["industries"]),
            "event_type": item["event_type"],
            "sentiment": item["sentiment"],
            "geography": json.dumps(item["geography"]),
            "themes": json.dumps(item["themes"]),
            "headline": item.get("headline", ""),
        })
    
    if dry_run:
        logger.info(f"[DRY RUN] Would load {len(rows)} rows into staging table")
        return len(rows)
    
    # Create/overwrite staging table with load
    job_config = bigquery.LoadJobConfig(
        schema=STAGING_SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    
    load_job = client.load_table_from_json(rows, STAGING_TABLE, job_config=job_config)
    load_job.result()  # Wait for completion
    
    logger.info(f"Loaded {len(rows)} rows into staging table")
    return len(rows)


def merge_staging_to_digest_items(
    client: bigquery.Client,
    dry_run: bool = False,
) -> int:
    """
    Single MERGE from staging table → digest_items.
    
    Updates all enriched fields in one atomic operation (~5s for any batch size).
    """
    if dry_run:
        logger.info("[DRY RUN] Would MERGE staging → digest_items")
        return 0
    
    merge_query = f"""
        MERGE `{FULL_DATASET}.digest_items` AS T
        USING `{STAGING_TABLE}` AS S
        ON T.id = S.digest_id
        WHEN MATCHED THEN UPDATE SET
            T.companies = S.companies,
            T.materials = S.materials,
            T.industries = S.industries,
            T.event_type = S.event_type,
            T.sentiment = S.sentiment,
            T.geography = S.geography,
            T.themes = S.themes,
            T.headline = S.headline,
            T.narrative_enriched_at = CURRENT_TIMESTAMP()
    """
    
    result = client.query(merge_query).result()
    # Get rows affected from DML stats
    rows_affected = result.num_dml_affected_rows if hasattr(result, 'num_dml_affected_rows') else -1
    return rows_affected


def insert_article_tags_batch(
    client: bigquery.Client,
    enriched_items: List[Dict[str, Any]],
    dry_run: bool = False,
) -> int:
    """Insert normalized tags into article_tags table."""
    import uuid
    
    successful = [i for i in enriched_items if i.get("success")]
    if not successful:
        return 0
    
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    
    for item in successful:
        article_id = item["article_id"]
        pub_at = item["published_at"]
        source_type = item["source_type"]
        
        # Companies → tag_type: "company"
        for company in item.get("companies", []):
            if company and company.strip():
                rows.append({
                    "id": str(uuid.uuid4()),
                    "article_id": article_id,
                    "tag": company.strip(),
                    "tag_normalized": company.strip().lower(),
                    "tag_type": "company",
                    "confidence": 0.85,
                    "source": "narrative_backfill",
                    "source_type": source_type,
                    "article_published_at": pub_at,
                    "classified_at": now,
                })
        
        # Materials → tag_type: "material"
        for material in item.get("materials", []):
            if material and material.strip():
                rows.append({
                    "id": str(uuid.uuid4()),
                    "article_id": article_id,
                    "tag": material.strip(),
                    "tag_normalized": material.strip().lower(),
                    "tag_type": "material",
                    "confidence": 0.85,
                    "source": "narrative_backfill",
                    "source_type": source_type,
                    "article_published_at": pub_at,
                    "classified_at": now,
                })
        
        # Industries → tag_type: "market"
        for industry in item.get("industries", []):
            if industry and industry.strip():
                rows.append({
                    "id": str(uuid.uuid4()),
                    "article_id": article_id,
                    "tag": industry.strip(),
                    "tag_normalized": industry.strip().lower(),
                    "tag_type": "market",
                    "confidence": 0.85,
                    "source": "narrative_backfill",
                    "source_type": source_type,
                    "article_published_at": pub_at,
                    "classified_at": now,
                })
        
        # Themes → tag_type: "theme"
        for theme in item.get("themes", []):
            if theme and theme.strip():
                rows.append({
                    "id": str(uuid.uuid4()),
                    "article_id": article_id,
                    "tag": theme.strip(),
                    "tag_normalized": theme.strip().lower(),
                    "tag_type": "theme",
                    "confidence": 0.80,
                    "source": "narrative_backfill",
                    "source_type": source_type,
                    "article_published_at": pub_at,
                    "classified_at": now,
                })
        
        # Geography → tag_type: "geography"
        for geo in item.get("geography", []):
            if geo and geo.strip():
                rows.append({
                    "id": str(uuid.uuid4()),
                    "article_id": article_id,
                    "tag": geo.strip(),
                    "tag_normalized": geo.strip().lower(),
                    "tag_type": "geography",
                    "confidence": 0.80,
                    "source": "narrative_backfill",
                    "source_type": source_type,
                    "article_published_at": pub_at,
                    "classified_at": now,
                })
        
        # Event type → tag_type: "topic"
        event = item.get("event_type", "")
        if event and event.strip() and event != "other":
            rows.append({
                "id": str(uuid.uuid4()),
                "article_id": article_id,
                "tag": event.strip(),
                "tag_normalized": event.strip().lower(),
                "tag_type": "topic",
                "confidence": 0.85,
                "source": "narrative_backfill",
                "source_type": source_type,
                "article_published_at": pub_at,
                "classified_at": now,
            })
    
    if dry_run:
        logger.info(f"[DRY RUN] Would insert {len(rows)} article_tags")
        # Show tag type breakdown
        from collections import Counter
        type_counts = Counter(r["tag_type"] for r in rows)
        for tag_type, count in sorted(type_counts.items()):
            logger.info(f"  {tag_type}: {count}")
        return len(rows)
    
    if not rows:
        return 0
    
    table_id = f"{FULL_DATASET}.article_tags"
    
    # Insert in chunks of 500 (BQ streaming insert limit)
    total_inserted = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i+500]
        errors = client.insert_rows_json(table_id, chunk)
        if errors:
            logger.error(f"article_tags insert errors: {errors[:3]}")
        total_inserted += len(chunk) - (len(errors) if errors else 0)
    
    return total_inserted


# ============================================================================
# Main
# ============================================================================

CHECKPOINT_FILE = os.path.join(os.path.dirname(__file__), "backfill_checkpoint.jsonl")


def load_checkpoint() -> Dict[str, Dict]:
    """Load previously enriched items from JSONL checkpoint file."""
    items = {}
    if not os.path.exists(CHECKPOINT_FILE):
        return items
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if item.get("success"):
                    items[item["digest_id"]] = item
            except json.JSONDecodeError:
                continue
    return items


def append_checkpoint(enriched_items: List[Dict]):
    """Append enriched items to JSONL checkpoint (crash-safe)."""
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        for item in enriched_items:
            f.write(json.dumps(item) + "\n")
        f.flush()
        os.fsync(f.fileno())


async def main():
    from collections import Counter
    
    parser = argparse.ArgumentParser(description="Narrative enrichment backfill")
    parser.add_argument("--start-date", default="2025-11-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=None, help="Max items to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to BQ")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Items per LLM batch")
    parser.add_argument("--skip-schema", action="store_true", help="Skip adding new BQ columns")
    parser.add_argument("--re-enrich", action="store_true", help="Re-enrich already enriched items")
    parser.add_argument("--write-only", action="store_true", help="Skip LLM, write from checkpoint file")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("NARRATIVE ENRICHMENT BACKFILL v2")
    logger.info("=" * 60)
    logger.info(f"Start date: {args.start_date}")
    logger.info(f"End date: {args.end_date or 'now'}")
    logger.info(f"Limit: {args.limit or 'all'}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Model: {ENRICHMENT_MODEL}")
    logger.info(f"Write-only: {args.write_only}")
    
    # Initialize clients
    bq_client = bigquery.Client(project=PROJECT_ID)
    
    # Step 1: Add new columns to BQ
    if not args.skip_schema:
        logger.info("\n--- Step 1: Schema Migration ---")
        add_narrative_columns(bq_client)
    
    # ========================================================================
    # PHASE 1: LLM Enrichment (or load from checkpoint)
    # ========================================================================
    all_enriched: List[Dict] = []
    all_event_types = Counter()
    all_sentiments = Counter()
    all_materials = Counter()
    all_themes = Counter()

    if args.write_only:
        # Skip LLM, load from checkpoint
        logger.info("\n--- Phase 1: Loading from checkpoint (write-only mode) ---")
        checkpoint = load_checkpoint()
        all_enriched = list(checkpoint.values())
        logger.info(f"Loaded {len(all_enriched)} enriched items from checkpoint")
        if not all_enriched:
            logger.error("No checkpoint data found. Run without --write-only first.")
            return
    else:
        # Fetch items and enrich with LLM
        logger.info("\n--- Phase 1: Fetching items ---")
        items = fetch_items_to_enrich(
            bq_client,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            skip_already_enriched=not args.re_enrich,
        )
        
        if not items:
            logger.info("No items to enrich. Done.")
            return
        
        # Load existing checkpoint to skip already-enriched items
        checkpoint = load_checkpoint()
        if checkpoint:
            before = len(items)
            items = [i for i in items if i["digest_id"] not in checkpoint]
            skipped = before - len(items)
            if skipped > 0:
                logger.info(f"Skipping {skipped} items already in checkpoint ({len(items)} remaining)")
                # Include checkpoint items in our results
                all_enriched.extend(checkpoint.values())
        
        if not items:
            logger.info("All items already in checkpoint. Proceeding to write phase.")
        else:
            logger.info(f"\n--- Phase 1b: Enriching {len(items)} items with LLM ---")
            
            # Initialize Anthropic client
            import anthropic
            
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                try:
                    from app.config.settings import settings
                    api_key = settings.anthropic_api_key
                except Exception:
                    pass
            
            if not api_key:
                logger.error("ANTHROPIC_API_KEY not found. Set it as env var or in app config.")
                return
            
            anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
            
            total_batches = (len(items) + args.batch_size - 1) // args.batch_size
            total_success = 0
            total_failed = 0
            
            for batch_num in range(total_batches):
                batch_start = batch_num * args.batch_size
                batch_end = min(batch_start + args.batch_size, len(items))
                batch = items[batch_start:batch_end]
                
                start_time = time.time()
                logger.info(f"  Batch {batch_num + 1}/{total_batches} ({len(batch)} items)...")
                
                enriched = await enrich_batch(batch, anthropic_client)
                
                elapsed = time.time() - start_time
                success = [e for e in enriched if e.get("success")]
                failed = [e for e in enriched if not e.get("success")]
                total_success += len(success)
                total_failed += len(failed)
                
                logger.info(f"  → {len(success)}/{len(batch)} succeeded in {elapsed:.1f}s  [{total_success}/{len(items)} total]")
                
                if failed:
                    logger.warning(f"    Failed: {[f.get('digest_id','?')[:8] for f in failed]}")
                
                # Save to checkpoint file (crash-safe)
                if enriched:
                    append_checkpoint(enriched)
                
                all_enriched.extend(success)
                
                if batch_num < total_batches - 1:
                    await asyncio.sleep(SLEEP_BETWEEN_BATCHES)
            
            logger.info(f"\nLLM enrichment complete: {total_success} succeeded, {total_failed} failed")
    
    # Filter to successful only
    successful = [e for e in all_enriched if e.get("success")]
    logger.info(f"\nTotal successful enrichments: {len(successful)}")
    
    if not successful:
        logger.info("Nothing to write. Done.")
        return
    
    # Collect stats
    for item in successful:
        all_event_types[item.get("event_type", "other")] += 1
        all_sentiments[item.get("sentiment", "neutral")] += 1
        for m in item.get("materials", []):
            all_materials[m] += 1
        for t in item.get("themes", []):
            all_themes[t] += 1
    
    # ========================================================================
    # PHASE 2: Bulk write to BQ via staging table + MERGE
    # ========================================================================
    logger.info("\n--- Phase 2: Writing to BigQuery ---")
    
    # 2a: Load into staging table
    write_start = time.time()
    staged = write_staging_table(bq_client, successful, dry_run=args.dry_run)
    logger.info(f"  Staging table: {staged} rows loaded in {time.time() - write_start:.1f}s")
    
    # 2b: MERGE staging → digest_items
    merge_start = time.time()
    merged = merge_staging_to_digest_items(bq_client, dry_run=args.dry_run)
    logger.info(f"  MERGE: {merged} rows updated in {time.time() - merge_start:.1f}s")
    
    # 2c: Insert article_tags (streaming insert, already fast)
    tags_start = time.time()
    tags_inserted = insert_article_tags_batch(bq_client, successful, dry_run=args.dry_run)
    logger.info(f"  Article tags: {tags_inserted} tags inserted in {time.time() - tags_start:.1f}s")
    
    total_write_time = time.time() - write_start
    logger.info(f"  Total write time: {total_write_time:.1f}s")
    
    # ========================================================================
    # Summary
    # ========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Successfully enriched: {len(successful)}")
    logger.info(f"Digest items updated (MERGE): {merged}")
    logger.info(f"Article tags inserted: {tags_inserted}")
    
    if successful:
        logger.info(f"\nTop event types: {all_event_types.most_common(5)}")
        logger.info(f"Sentiment distribution: {dict(all_sentiments)}")
        logger.info(f"Top materials: {all_materials.most_common(10)}")
        logger.info(f"Top themes: {all_themes.most_common(10)}")
    
    # Clean up checkpoint file on successful completion
    if not args.dry_run and os.path.exists(CHECKPOINT_FILE):
        done_path = CHECKPOINT_FILE + ".done"
        if os.path.exists(done_path):
            os.remove(done_path)
        os.rename(CHECKPOINT_FILE, done_path)
        logger.info(f"Checkpoint file renamed to {CHECKPOINT_FILE}.done")


if __name__ == "__main__":
    asyncio.run(main())
