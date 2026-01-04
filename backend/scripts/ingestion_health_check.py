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


def run_bq_query(query: str) -> List[Dict]:
    """Run BigQuery query and return results."""
    escaped_query = query.replace('"', '\\"')
    cmd = f'"{BQ_PATH}" query --use_legacy_sql=false --project_id={PROJECT_ID} --format=json "{escaped_query}"'
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
        if result.returncode != 0:
            return []
        if not result.stdout.strip() or result.stdout.strip() == "[]":
            return []
        return json.loads(result.stdout)
    except Exception as e:
        print(f"❌ BigQuery query failed: {e}")
        return []


def check_scheduler_status() -> Dict:
    """Check Cloud Scheduler job status."""
    gcloud_path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd")
    if not os.path.exists(gcloud_path):
        gcloud_path = "gcloud"
    
    cmd = f'"{gcloud_path}" scheduler jobs list --project={PROJECT_ID} --location=us-central1 --filter="name:daily" --format=json'
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True)
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
    """Get daily article counts from BigQuery."""
    query = f"""
    SELECT 
        DATE(fetched_at) as date,
        COUNT(*) as total_articles,
        COUNT(DISTINCT source_type) as sources_used,
        COUNTIF(source_type = 'rss') as rss,
        COUNTIF(source_type = 'press_release') as press_releases,
        COUNTIF(source_type = 'sec_filing') as sec_filings,
        COUNTIF(source_type = 'earnings_transcript') as earnings,
        COUNTIF(source_type = 'stocknews') as stocknews,
        COUNTIF(source_type = 'web_search' OR source_type = 'web_news') as web_legacy,
        COUNTIF(source_type = 'web_news_exa') as exa,
        COUNTIF(source_type = 'web_news_tavily') as tavily
    FROM `{PROJECT_ID}.{DATASET}.corpus_items`
    WHERE fetched_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
    GROUP BY date
    ORDER BY date DESC
    """
    return run_bq_query(query)


def get_pipeline_completeness(days_back: int = 7) -> List[Dict]:
    """Check if articles -> digest_items -> embeddings pipeline is complete."""
    query = f"""
    WITH article_counts AS (
        SELECT DATE(fetched_at) as date, COUNT(*) as articles
        FROM `{PROJECT_ID}.{DATASET}.corpus_items`
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
        "corpus_items": "fetched_at",
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
        print(f"      Total: {counts.get('total', 0):,}")
        print(f"      Last 24h: {counts.get('last_24h', 0):,}")
        print(f"      Last 7d: {counts.get('last_7d', 0):,}")
        print()
    
    # 3. Daily Article Breakdown
    print("📰 DAILY ARTICLE INGESTION (By Source)")
    print("-" * 80)
    daily_counts = get_daily_article_counts(days_back)
    
    if not daily_counts:
        print("   ❌ NO ARTICLES FOUND in last {days_back} days!")
        print("   This is a CRITICAL FAILURE - ingestion pipeline is not working.")
    else:
        print(f"   {'Date':<12} {'Total':<8} {'RSS':<6} {'PR':<6} {'SEC':<6} {'Earn':<6} {'News':<6} {'Exa':<6} {'Tvly':<6} {'Sources':<8}")
        print("   " + "-" * 85)
        for row in daily_counts:
            date = row.get("date", "")
            total = int(row.get("total_articles", 0))
            rss = int(row.get("rss", 0))
            pr = int(row.get("press_releases", 0))
            sec = int(row.get("sec_filings", 0))
            earn = int(row.get("earnings", 0))
            news = int(row.get("stocknews", 0))
            exa = int(row.get("exa", 0))
            tavily = int(row.get("tavily", 0))
            
            # Combine legacy web results into Exa or display separately? 
            # For now, let's assume legacy 'web_news' maps to Exa or just ignore if 0
            legacy_web = int(row.get("web_legacy", 0))
            if legacy_web > 0:
                exa += legacy_web # Attribute legacy to Exa for simpler view, or just add note
                
            sources = int(row.get("sources_used", 0))
            
            # Flag low days
            flag = "⚠️ " if total < 30 else "   "
            print(f"   {flag}{date:<12} {total:<8} {rss:<6} {pr:<6} {sec:<6} {earn:<6} {news:<6} {exa:<6} {tavily:<6} {sources}/8")
    
    # 4. Pipeline Completeness
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
            date = row.get("date", "")
            articles = int(row.get("articles", 0))
            digests = int(row.get("digests", 0))
            embeddings = int(row.get("embeddings", 0))
            
            # Check completeness
            if articles == digests == embeddings and articles > 0:
                status = "✅ Complete"
            elif articles > 0:
                status = "⚠️  Incomplete"
            else:
                status = "❌ No Data"
            
            print(f"   {date:<12} {articles:<10} {digests:<10} {embeddings:<12} {status}")
    
    # 5. Health Summary
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
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check production ingestion health")
    parser.add_argument("--days", type=int, default=7, help="Number of days to check")
    args = parser.parse_args()
    
    print_report(args.days)
