#!/usr/bin/env python3
"""
Production Ingestion Health Check
==================================

Comprehensive health check that verifies ACTUAL data landing in BigQuery,
not just log analysis. Catches silent failures that log-only reports miss.

Usage:
    python scripts/ingestion_health_check.py              # Check last 24 hours
    python scripts/ingestion_health_check.py --days 7     # Check last 7 days
"""

import subprocess
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List
import argparse

PROJECT_ID = "gen-lang-client-0436975498"
DATASET = "c1_intelligence"
BQ_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\bq.cmd")
if not os.path.exists(BQ_PATH):
    BQ_PATH = "bq"


def run_bq_query(query: str, debug: bool = False) -> List[Dict]:
    """Run BigQuery query and return results."""
    # Clean up query - remove extra whitespace and make it single line
    clean_query = ' '.join(query.split())
    
    # Use a different approach - write query to temp argument
    cmd = [
        BQ_PATH, 
        "query", 
        "--use_legacy_sql=false", 
        f"--project_id={PROJECT_ID}", 
        "--format=json",
        clean_query
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        if debug:
            print(f"   [DEBUG] Return code: {result.returncode}")
            if result.stderr:
                print(f"   [DEBUG] Stderr: {result.stderr[:200]}")
        if result.returncode != 0:
            if debug:
                print(f"   [DEBUG] BQ command failed: {result.stderr[:200] if result.stderr else 'No stderr'}")
            return []
        if not result.stdout.strip() or result.stdout.strip() == "[]":
            return []
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        if debug:
            print(f"   [DEBUG] JSON parse error: {e}")
            print(f"   [DEBUG] Raw output: {result.stdout[:200] if result.stdout else 'None'}")
        return []
    except Exception as e:
        print(f"❌ BigQuery query failed: {e}")
        return []

# ... (This logic handles multiple occurrences if configured, but here we target specific blocks)



def check_scheduler_status() -> Dict:
    """Check Cloud Scheduler job status."""
    gcloud_path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd")
    if not os.path.exists(gcloud_path):
        gcloud_path = "gcloud"
    
    # Filter for ingestion-related jobs (daily legacy + new ingest/briefing jobs)
    cmd = f'"{gcloud_path}" scheduler jobs list --project={PROJECT_ID} --location=us-central1 --filter="name:(daily OR ingest OR briefing)" --format=json'
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True, stdin=subprocess.DEVNULL)
        if result.returncode != 0:
            return {"error": "Could not fetch scheduler status"}
        jobs = json.loads(result.stdout)
        
        status = {}
        for job in jobs:
            name = job.get("name", "").split("/")[-1]
            status[name] = {
                "state": job.get("state", "UNKNOWN"),
                "last_attempt": job.get("lastAttemptTime", "Never"),
                "status_code": job.get("status", {}).get("code", 0),
                "schedule": job.get("schedule", ""),
            }
        return status
    except Exception as e:
        return {"error": str(e)}


def get_daily_article_counts(days_back: int = 7) -> List[Dict]:
    """Get daily article counts from BigQuery articles table."""
    query = f"""
    SELECT 
        DATE(fetched_at) as date,
        COUNT(*) as total_articles,
        COUNT(DISTINCT source_type) as sources_used,
        COUNTIF(source_type = 'rss') as rss,
        COUNTIF(source_type = 'press_release') as press_releases,
        COUNTIF(source_type = 'sec_filing') as sec_filings,
        COUNTIF(source_type = 'earnings_transcript') as earnings,
        COUNTIF(source_type = 'stocknewsapi') as stocknews,
        COUNTIF(source_type = 'premium_news') as fmp_news,
        COUNTIF(source_type = 'web_search' OR source_type = 'web_news') as web_legacy,
        COUNTIF(source_type = 'web_news_exa') as exa,
        COUNTIF(source_type = 'web_news_tavily') as tavily
    FROM `{PROJECT_ID}.{DATASET}.articles`
    WHERE fetched_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
    GROUP BY date
    ORDER BY date DESC
    """
    return run_bq_query(query)


def get_date_filter_stats(days_back: int = 7) -> Dict:
    """Get date filtering statistics from digest_items table.
    
    This shows how many articles are feed_eligible vs filtered out.
    Filtered articles are still stored, just not shown in Drumbeat feed.
    """
    query = f"""
    SELECT 
        COUNTIF(feed_eligible = TRUE) as feed_eligible,
        COUNTIF(feed_eligible = FALSE) as filtered_out,
        COUNTIF(feed_eligible IS NULL) as null_status,
        COUNTIF(published_at IS NULL) as no_date,
        COUNTIF(published_at > CURRENT_TIMESTAMP()) as future_date,
        COUNT(*) as total
    FROM `{PROJECT_ID}.{DATASET}.digest_items`
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
    """
    result = run_bq_query(query)
    if result:
        return result[0]
    return {"feed_eligible": 0, "filtered_out": 0, "null_status": 0, "no_date": 0, "future_date": 0, "total": 0}


def get_pipeline_completeness(days_back: int = 7) -> List[Dict]:
    """Check if articles -> digest_items -> embeddings pipeline is complete."""
    query = f"""
    WITH article_counts AS (
        SELECT DATE(fetched_at) as date, COUNT(*) as articles
        FROM `{PROJECT_ID}.{DATASET}.articles`
        WHERE fetched_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
        GROUP BY date
    ),
    digest_counts AS (
        SELECT DATE(ingested_at) as date, COUNT(*) as digests
        FROM `{PROJECT_ID}.{DATASET}.digest_items`
        WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
        GROUP BY date
    ),
    embedding_counts AS (
        SELECT DATE(created_at) as date, COUNT(DISTINCT article_id) as embeddings
        FROM `{PROJECT_ID}.{DATASET}.article_chunk_embeddings`
        WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
        GROUP BY date
    )
    SELECT 
        a.date,
        COALESCE(a.articles, 0) as articles,
        COALESCE(d.digests, 0) as digests,
        COALESCE(e.embeddings, 0) as embeddings
    FROM article_counts a
    FULL OUTER JOIN digest_counts d ON a.date = d.date
    FULL OUTER JOIN embedding_counts e ON a.date = e.date
    ORDER BY a.date DESC
    """
    return run_bq_query(query)


def get_table_stats() -> Dict:
    """Get current table record counts."""
    tables = {
        "articles": "fetched_at",
        "digest_items": "ingested_at",
        "article_chunk_embeddings": "created_at",
        "article_images": "extracted_at",
        "freight_rates": "ingestion_timestamp",
        "pre_briefings": "generated_at",
        "weekly_briefings": "generated_at",
    }
    
    stats = {}
    for table, date_col in tables.items():
        query = f"""
        SELECT 
            COUNT(*) as total,
            COUNTIF({date_col} >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)) as last_24h,
            COUNTIF({date_col} >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)) as last_7d
        FROM `{PROJECT_ID}.{DATASET}.{table}`
        """
        result = run_bq_query(query)
        if result:
            stats[table] = result[0]
    
    return stats


def get_briefing_quality() -> Dict:
    """Check quality of latest weekly briefing and pre-briefing count."""
    try:
        # Get latest weekly briefing quality
        briefing_query = f"""
        SELECT 
            id,
            briefing_title,
            bluf,
            sections,
            generated_at
        FROM `{PROJECT_ID}.{DATASET}.weekly_briefings`
        ORDER BY generated_at DESC
        LIMIT 1
        """
        briefing_result = run_bq_query(briefing_query)
        
        # Get pre-briefing count
        prebrief_query = f"""
        SELECT COUNT(*) as cnt 
        FROM `{PROJECT_ID}.{DATASET}.pre_briefings`
        """
        prebrief_result = run_bq_query(prebrief_query)
        
        if not briefing_result:
            return {"error": None, "id": None}
        
        row = briefing_result[0]
        sections_json = row.get("sections", "[]")
        
        # Count sections
        try:
            import json
            sections = json.loads(sections_json) if sections_json else []
            section_count = len(sections)
        except:
            section_count = 0
        
        return {
            "id": row.get("id"),
            "title": row.get("briefing_title", ""),
            "has_bluf": bool(row.get("bluf")),
            "section_count": section_count,
            "generated_at": row.get("generated_at"),
            "pre_brief_count": int(prebrief_result[0].get("cnt", 0)) if prebrief_result else 0,
        }
    except Exception as e:
        return {"error": str(e)}


def print_report(days_back: int):
    """Generate and print the health check report."""
    print("=" * 80)
    print("🏥 PRODUCTION INGESTION HEALTH CHECK")
    print("=" * 80)
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Lookback Period: Last {days_back} days")
    print()
    
    # 1. Scheduler Status
    print("📅 CLOUD SCHEDULER STATUS")
    print("-" * 80)
    scheduler_status = check_scheduler_status()
    if "error" in scheduler_status:
        print(f"   ⚠️  Could not check scheduler: {scheduler_status['error']}")
    else:
        for job_name, info in scheduler_status.items():
            state_emoji = "✅" if info["state"] == "ENABLED" else "❌"
            status_emoji = "✅" if info["status_code"] == 0 else "❌"
            print(f"   {state_emoji} {job_name}")
            print(f"      State: {info['state']}")
            print(f"      Schedule: {info['schedule']}")
            print(f"      Last Attempt: {info['last_attempt']}")
            print(f"      {status_emoji} Status Code: {info['status_code']}")
            print()
    
    # 2. Table Statistics
    print("📊 BIGQUERY TABLE STATISTICS")
    print("-" * 80)
    table_stats = get_table_stats()
    for table, counts in table_stats.items():
        print(f"   {table}:")
        total = int(counts.get('total', 0) or 0)
        last_24h = int(counts.get('last_24h', 0) or 0)
        last_7d = int(counts.get('last_7d', 0) or 0)
        print(f"      Total: {total:,}")
        print(f"      Last 24h: {last_24h:,}")
        print(f"      Last 7d: {last_7d:,}")
        print()
    
    # 3. Daily Article Breakdown
    print("📰 DAILY ARTICLE INGESTION (By Source)")
    print("-" * 80)
    daily_counts = get_daily_article_counts(days_back)
    
    if not daily_counts:
        print("   ❌ NO ARTICLES FOUND in last {days_back} days!")
        print("   This is a CRITICAL FAILURE - ingestion pipeline is not working.")
    else:
        print(f"   {'Date':<12} {'Total':<7} {'RSS':<5} {'SEC':<5} {'Earn':<5} {'FMP':<5} {'News':<5} {'Exa':<5} {'Tvly':<5} {'Src':<5}")
        print("   " + "-" * 75)
        for row in daily_counts:
            date = row.get("date", "")
            total = int(row.get("total_articles", 0))
            rss = int(row.get("rss", 0))
            sec = int(row.get("sec_filings", 0))
            earn = int(row.get("earnings", 0))
            fmp = int(row.get("fmp_news", 0))
            news = int(row.get("stocknews", 0))
            exa = int(row.get("exa", 0))
            tavily = int(row.get("tavily", 0))
            
            # Combine legacy web results into Exa
            legacy_web = int(row.get("web_legacy", 0))
            if legacy_web > 0:
                exa += legacy_web
                
            sources = int(row.get("sources_used", 0))
            
            # Flag low days
            flag = "⚠️ " if total < 30 else "   "
            print(f"   {flag}{date:<12} {total:<7} {rss:<5} {sec:<5} {earn:<5} {fmp:<5} {news:<5} {exa:<5} {tavily:<5} {sources}/9")
    
    # 4. Date Filter Analysis (NEW)
    print()
    print("📅 DATE FILTER ANALYSIS (Drumbeat Feed Eligibility)")
    print("-" * 80)
    date_stats = get_date_filter_stats(days_back)
    
    total = int(date_stats.get("total", 0) or 0)
    feed_eligible = int(date_stats.get("feed_eligible", 0) or 0)
    filtered_out = int(date_stats.get("filtered_out", 0) or 0)
    null_status = int(date_stats.get("null_status", 0) or 0)
    no_date = int(date_stats.get("no_date", 0) or 0)
    future_date = int(date_stats.get("future_date", 0) or 0)
    
    print(f"   Total digest items (last {days_back} days): {total:,}")
    print(f"   ├─ Feed eligible (shown in Drumbeat):  {feed_eligible:,}")
    print(f"   ├─ Filtered out (stored but hidden):   {filtered_out:,}")
    print(f"   ├─ Null feed_eligible status:          {null_status:,}")
    print(f"   └─ Date issues:")
    print(f"      ├─ No published_at date:  {no_date:,}")
    print(f"      └─ Future date (bad parse): {future_date:,}")
    
    if future_date > 0:
        pct = (future_date / total * 100) if total > 0 else 0
        print(f"   ⚠️  {pct:.1f}% of articles have future dates - date extraction bugs!")
    
    # 5. Pipeline Completeness
    print()
    print("🔗 PIPELINE COMPLETENESS CHECK")
    print("-" * 80)
    pipeline = get_pipeline_completeness(days_back)
    
    if not pipeline:
        print("   ⚠️  No pipeline data available")
    else:
        print(f"   {'Date':<12} {'Articles':<10} {'Digests':<10} {'Embeddings':<12} {'Status':<15}")
        print("   " + "-" * 70)
        for row in pipeline:
            date = row.get("date") or "Unknown"
            articles = int(row.get("articles") or 0)
            digests = int(row.get("digests") or 0)
            embeddings = int(row.get("embeddings") or 0)
            
            # Check completeness
            if articles == digests == embeddings and articles > 0:
                status = "✅ Complete"
            elif articles > 0:
                status = "⚠️  Incomplete"
            else:
                status = "❌ No Data"
            
            print(f"   {str(date):<12} {articles:<10} {digests:<10} {embeddings:<12} {status}")
    
    # 6. Briefing Quality Check
    print()
    print("📝 WEEKLY BRIEFING QUALITY CHECK")
    print("-" * 80)
    briefing_quality = get_briefing_quality()
    
    if briefing_quality.get("error"):
        print(f"   ⚠️  Could not check briefing quality: {briefing_quality['error']}")
    elif not briefing_quality.get("id"):
        print("   ❌ No weekly briefings found")
    else:
        print(f"   Latest briefing: {briefing_quality.get('generated_at', 'Unknown')}")
        print(f"   Title: {briefing_quality.get('title', 'N/A')}")
        
        has_bluf = briefing_quality.get('has_bluf', False)
        section_count = briefing_quality.get('section_count', 0)
        pre_brief_count = briefing_quality.get('pre_brief_count', 0)
        
        bluf_status = "✅" if has_bluf else "❌"
        section_status = "✅" if section_count >= 3 else "⚠️" if section_count > 0 else "❌"
        prebrief_status = "✅" if pre_brief_count >= 2 else "⚠️" if pre_brief_count > 0 else "❌"
        
        print(f"   {bluf_status} BLUF: {'Present' if has_bluf else 'MISSING'}")
        print(f"   {section_status} Sections: {section_count}")
        print(f"   {prebrief_status} Historical pre-briefings: {pre_brief_count}")
        
        if has_bluf and section_count >= 3 and pre_brief_count >= 2:
            print("   ✅ Briefing pipeline healthy")
        else:
            print("   ⚠️  Briefing may need attention")
    
    # 7. Health Summary
    print()
    print("🎯 HEALTH SUMMARY")
    print("-" * 80)
    
    # Calculate expected vs actual
    total_articles = sum(int(row.get("total_articles", 0)) for row in daily_counts)
    avg_per_day = total_articles / days_back if days_back > 0 else 0
    expected_per_day = 80  # 2 runs x 40 avg articles
    
    print(f"   Average articles/day: {avg_per_day:.1f}")
    print(f"   Expected articles/day: ~{expected_per_day} (varies by news cycle)")
    
    if avg_per_day < 30:
        print(f"   ❌ CRITICAL: Ingestion severely underperforming")
    elif avg_per_day < 50:
        print(f"   ⚠️  WARNING: Ingestion below expected levels")
    else:
        print(f"   ✅ Ingestion performing within normal range")
    
    # Date filtering health
    if future_date > 10:
        print(f"   ⚠️  WARNING: {future_date} articles with future dates - review date extraction")
    
    print()
    print("📌 ACTIVE DATA SOURCES (Jan 2026):")
    print("   • RSS feeds (industry news)")
    print("   • SEC filings (10-K, 10-Q for tracked companies)")
    print("   • API Ninja earnings transcripts (35 companies with Q3 2025 data)")
    print("   • FMP Premium News (Benzinga, Seeking Alpha via FMP API)")
    print("   • StockNews API (market news)")
    print("   • Exa.ai (industry web search - 91 queries)")
    print("   • Tavily (industry web search - 145 queries)")
    print()
    print("📌 KEY ARCHITECTURE:")
    print("   • ALL articles stored regardless of date (feed_eligible flag controls visibility)")
    print("   • Deduplication via BigQuery (no SQLite)")
    print("   • Earnings use quarter-based fetching (not date ranges)")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check production ingestion health")
    parser.add_argument("--days", type=int, default=7, help="Number of days to check")
    args = parser.parse_args()
    
    print_report(args.days)
