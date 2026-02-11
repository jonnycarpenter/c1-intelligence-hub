#!/usr/bin/env python3
"""
Cloud Scheduler Ingestion Report Generator
==========================================

Generates a comprehensive report of the most recent Cloud Scheduler ingestion runs,
including source-by-source status, article counts, and storage confirmation.

Usage:
    python scripts/scheduler_report.py                    # Report for most recent run
    python scripts/scheduler_report.py --run morning      # Morning run only (8 AM CT)
    python scripts/scheduler_report.py --run evening      # Evening run only (8 PM CT)
    python scripts/scheduler_report.py --run both         # Both runs
    python scripts/scheduler_report.py --date 2026-01-01  # Specific date
    python scripts/scheduler_report.py --hours 24         # Last N hours

Requires:
    - gcloud CLI authenticated
    - BigQuery access to <GCP_PROJECT_ID> project
"""

import subprocess
import re
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from collections import defaultdict
import argparse
import json

# Configuration
PROJECT_ID = "<GCP_PROJECT_ID>"

# Find gcloud path (Windows SDK location)
GCLOUD_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd")
if not os.path.exists(GCLOUD_PATH):
    # Fallback to PATH
    GCLOUD_PATH = "gcloud"

BQ_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\bq.cmd") 
if not os.path.exists(BQ_PATH):
    BQ_PATH = "bq"
SERVICE_NAME = "c1-hub"
BQ_DATASET = "c1_intelligence"

# Schedule times (UTC)
MORNING_RUN_UTC = 14  # 2 PM UTC = 8 AM Central
EVENING_RUN_UTC = 2   # 2 AM UTC = 8 PM Central


def run_gcloud_logs(filter_query: str, limit: int = 200) -> List[str]:
    """Run gcloud logging read command and return lines."""
    full_filter = f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE_NAME}" AND {filter_query}'
    # Escape quotes for Windows PowerShell - use single quotes inside double quotes
    full_filter_escaped = full_filter.replace('"', '\\"')
    cmd = f'"{GCLOUD_PATH}" logging read "{full_filter_escaped}" --project={PROJECT_ID} --limit={limit} --format=json'
    
    try:
        # TIMEOUT ENFORCED: 45 seconds
        # stdin=DEVNULL prevents gcloud from waiting for user input
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=45, 
            shell=True,
            stdin=subprocess.DEVNULL
        )
        if result.returncode != 0:
            print(f"Warning: gcloud command failed: {result.stderr[:200]}")
            return []
        
        if not result.stdout.strip():
            return []
            
        logs = json.loads(result.stdout)
        return logs
    except subprocess.TimeoutExpired:
        print("Warning: gcloud command timed out after 45s")
        return []
    except json.JSONDecodeError:
        print("Warning: Could not parse gcloud output")
        return []
    except Exception as e:
        print(f"Warning: Error running gcloud: {e}")
        return []


def run_bq_query(query: str) -> List[Dict]:
    """Run BigQuery query and return results."""
    # Escape the query for shell
    escaped_query = query.replace('"', '\\"')
    cmd = f'"{BQ_PATH}" query --use_legacy_sql=false --project_id={PROJECT_ID} --format=json "{escaped_query}"'
    
    try:
        # TIMEOUT ENFORCED: 45 seconds
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=45, 
            shell=True,
            stdin=subprocess.DEVNULL
        )
        if result.returncode != 0:
            return []
        
        if not result.stdout.strip() or result.stdout.strip() == "[]":
            return []
            
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Warning: BigQuery query failed: {e}")
        return []


def parse_log_entry(entry: Dict) -> Dict:
    """Parse a log entry into timestamp and text."""
    timestamp = entry.get("timestamp", "")
    text = entry.get("textPayload", "")
    return {"timestamp": timestamp, "text": text}


def find_ingestion_runs(hours_back: int = 24) -> List[Dict]:
    """Find ingestion run start/end times in the logs."""
    logs = run_gcloud_logs(f'textPayload:"Ingestion triggered"', limit=20)
    
    runs = []
    for entry in logs:
        parsed = parse_log_entry(entry)
        if "Ingestion triggered" in parsed["text"]:
            ts = parsed["timestamp"]
            # Parse timestamp
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                hour_utc = dt.hour
                
                # Determine run type
                if 13 <= hour_utc <= 15:
                    run_type = "morning"
                elif 1 <= hour_utc <= 3:
                    run_type = "evening"
                else:
                    run_type = "manual"
                
                runs.append({
                    "timestamp": ts,
                    "datetime": dt,
                    "type": run_type,
                    "date": dt.strftime("%Y-%m-%d")
                })
            except:
                pass
    
    return runs


def get_run_logs(start_time: datetime, duration_minutes: int = 30) -> List[Dict]:
    """Get all logs for a specific run window using server-side filtering."""
    # Format times for gcloud (UTC) - Ensure zulu format
    start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time = start_time + timedelta(minutes=duration_minutes)
    end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Use server-side timestamp filtering for reliability
    # Fetch more logs since we are time-bounded now
    time_filter = f'timestamp>="{start_str}" AND timestamp<="{end_str}"'
    
    print(f"   (Fetching logs from {start_str} to {end_str})...")
    return run_gcloud_logs(time_filter, limit=1000)


def analyze_stocknews(logs: List[Dict]) -> Dict:
    """Analyze StockNewsAPI results from logs."""
    result = {
        "ticker_articles": 0,
        "keyword_articles": 0,
        "total_articles": 0,
        "api_calls": 0,
        "filtered_out": 0,
        "ticker_queries": [],
        "keyword_queries": [],
        "status": "unknown"
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        # Total collection
        match = re.search(r"StockNews: Total collection: (\d+) unique articles", text)
        if match:
            result["total_articles"] = int(match.group(1))
            result["status"] = "success"
        
        # API calls
        match = re.search(r"StockNews: API calls used: (\d+)", text)
        if match:
            result["api_calls"] = int(match.group(1))
        
        # Ticker articles
        match = re.search(r"StockNews: Collected (\d+) unique articles from ticker queries", text)
        if match:
            result["ticker_articles"] = int(match.group(1))
        
        # Keyword articles
        match = re.search(r"StockNews: Collected (\d+) unique articles from keyword queries", text)
        if match:
            result["keyword_articles"] = int(match.group(1))
        
        # Filtered out
        match = re.search(r"Filtered out (\d+) StockNewsAPI articles", text)
        if match:
            result["filtered_out"] = int(match.group(1))
        
        # Individual ticker queries
        match = re.search(r"StockNewsAPI: (\d+) articles for tickers \[(.*?)\]", text)
        if match:
            result["ticker_queries"].append({
                "tickers": match.group(2),
                "count": int(match.group(1))
            })
        
        # Individual keyword queries
        match = re.search(r"StockNewsAPI: (\d+) articles for keyword '(.*?)'", text)
        if match:
            result["keyword_queries"].append({
                "keyword": match.group(2),
                "count": int(match.group(1))
            })
    
    return result


def analyze_rss(logs: List[Dict]) -> Dict:
    """Analyze RSS feed results from logs."""
    result = {
        "total_articles": 0,
        "logistics_articles": 0,
        "feeds": [],
        "warnings": [],
        "status": "unknown"
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        # Total RSS
        match = re.search(r"Total RSS articles fetched: (\d+)", text)
        if match:
            result["total_articles"] = int(match.group(1))
            result["status"] = "success"
        
        # Individual feeds
        match = re.search(r"Fetched (\d+) articles from (.+)$", text)
        if match:
            result["feeds"].append({
                "name": match.group(2),
                "count": int(match.group(1))
            })
            if any(name in match.group(2) for name in ["FreightWaves", "Supply Chain Dive"]):
                result["logistics_articles"] += int(match.group(1))
        
        # Warnings
        if "Feed parse warning" in text:
            result["warnings"].append(text)
    
    return result


def analyze_sec(logs: List[Dict]) -> Dict:
    """Analyze SEC filings results from logs."""
    result = {
        "status": "unknown",
        "since_date": None,
        "errors": []
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        # SEC fetch
        match = re.search(r"Fetching SEC filings \(Since ([\d-]+)\)", text)
        if match:
            result["since_date"] = match.group(1)
            result["status"] = "success"
        
        # Errors
        if "SEC Query failed" in text or "SEC" in text and "error" in text.lower():
            result["errors"].append(text)
            result["status"] = "partial"
    
    return result


def analyze_earnings(logs: List[Dict]) -> Dict:
    """Analyze earnings transcript results from logs."""
    result = {
        "companies_checked": 0,
        "companies": [],
        "status": "unknown"
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        # Individual company
        match = re.search(r"Collecting earnings for (.+)\.\.\.", text)
        if match:
            result["companies"].append(match.group(1))
            result["status"] = "success"
    
    result["companies_checked"] = len(result["companies"])
    return result


def analyze_press_releases(logs: List[Dict]) -> Dict:
    """Analyze press release results from logs."""
    result = {
        "filtered_out": 0,
        "status": "unknown"
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        # Filtered PRs
        match = re.search(r"Filtered out (\d+) PRs", text)
        if match:
            result["filtered_out"] = int(match.group(1))
            result["status"] = "success"
    
    return result


def analyze_web_search(logs: List[Dict]) -> Dict:
    """Analyze Web search (Exa & Tavily) results from logs."""
    result = {
        "exa_count": 0,
        "tavily_count": 0,
        "total_articles": 0,
        "exa_industry_queries": 0,
        "tavily_industry_queries": 0,
        "company_queries": 0,
        "filtered_out": 0,
        "status": "unknown"
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        # Total web news (aggregate)
        match = re.search(r"Total web news articles: (\d+)", text)
        if match:
            result["total_articles"] = int(match.group(1))
            result["status"] = "success"
        
        # Exa Queries
        match = re.search(r"Exa Query \[.*?\]: '.*?' -> (\d+) results", text)
        if match:
            count = int(match.group(1))
            result["exa_count"] += count
            result["exa_industry_queries"] += 1

        # Tavily Queries
        match = re.search(r"Tavily Query \[.*?\]: '.*?' -> (\d+) results", text)
        if match:
            count = int(match.group(1))
            result["tavily_count"] += count
            result["tavily_industry_queries"] += 1
            
        # Company queries (Exa)
        match = re.search(r"Company Query: '.*?' -> (\d+) results", text)
        if match:
            count = int(match.group(1))
            # Company queries are currently Exa-only in orchestrator logic
            result["exa_count"] += count
            result["company_queries"] += count
        
        # Filtered
        match = re.search(r"Filtered out (\d+) web articles", text)
        if match:
            result["filtered_out"] = int(match.group(1))
            
    return result


def analyze_pipeline_steps(logs: List[Dict]) -> Dict:
    """Analyze pipeline step completions."""
    steps = {
        "step1_rss": False,
        "step1b_freight": False,
        "step2_tiered_data": False,
        "step3_dedup": False,
        "step4_enriching": False,
        "step5_classifying": False,
        "step5b_images": False,
        "step6_storing": False,
        "step6a_bq_articles": False,
        "step6c_bq_digest": False,
        "step7_vectors": False,
        "step8_digest": False,
        "step9_briefings": False,
        "complete": False,
        "execution_time": None,
        "total_articles_fetched": 0,
        "unique_after_dedup": 0,
        "classified": 0,
        "stored_bq": 0,
        "stored_vectors": 0
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        if "Step 1: Fetching RSS" in text:
            steps["step1_rss"] = True
        if "Step 1b: Fetching Drewry Freight Rates" in text:
            steps["step1b_freight"] = True
        if "Step 2: Fetching Tiered Data" in text:
            steps["step2_tiered_data"] = True
        if "Step 3: Deduplicating" in text:
            steps["step3_dedup"] = True
        if "Step 4: Enriching" in text:
            steps["step4_enriching"] = True
        if "Step 5: Classifying" in text:
            steps["step5_classifying"] = True
        if "Step 5b: Extracting images" in text:
            steps["step5b_images"] = True
        if "Step 6: Linking entities" in text:
            steps["step6_storing"] = True
        if "Step 6a: Storing articles in BigQuery" in text:
            steps["step6a_bq_articles"] = True
        if "Step 6c: Storing digest items in BigQuery" in text:
            steps["step6c_bq_digest"] = True
        if "Step 7: Updating vector stores" in text:
            steps["step7_vectors"] = True
        if "Step 8: Generating digest" in text:
            steps["step8_digest"] = True
        if "Step 9: Generating Pulse briefings" in text:
            steps["step9_briefings"] = True
        
        # Completion
        if "Ingestion complete in" in text:
            steps["complete"] = True
            match = re.search(r"Ingestion complete in ([\d.]+)s", text)
            if match:
                steps["execution_time"] = float(match.group(1))
        
        # Article counts
        match = re.search(r"Total articles to process: (\d+)", text)
        if match:
            steps["total_articles_fetched"] = int(match.group(1))
        
        match = re.search(r"Unique articles after dedup: (\d+)", text)
        if match:
            steps["unique_after_dedup"] = int(match.group(1))
        
        match = re.search(r"Classified (\d+)/\d+ articles", text)
        if match:
            steps["classified"] = int(match.group(1))
        
        # Vector store (BigQuery embeddings)
        match = re.search(r"Added (\d+) items to (?:vector store|BigQuery)", text)
        if match:
            steps["stored_vectors"] = int(match.group(1))
        
        match = re.search(r"Stored (\d+) digest items in BigQuery", text)
        if match:
            steps["stored_bq"] = int(match.group(1))
            
        # Freight rates specific count
        match = re.search(r"Stored (\d+) freight rates in BigQuery", text)
        if match:
            steps["freight_rates_stored"] = int(match.group(1))
    
    return steps


def analyze_image_classifier(logs: List[Dict]) -> Dict:
    """Analyze image classification/enrichment details."""
    result = {
        "status": "unknown",
        "articles_enriched": 0,
        "total_images_extracted": 0,
        "images_per_article": [],
        "classification_errors": 0,
        "vision_errors": 0,
        "articles_with_images": 0,
        "started": False,
        "completed": False
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        # Step 5b started
        if "Step 5b: Extracting images" in text:
            result["started"] = True
        
        # Batch enrichment start: "Enriching X articles with images..."
        match = re.search(r"Enriching (\d+) articles with images", text)
        if match:
            result["articles_enriched"] = int(match.group(1))
        
        # Per-article extraction: "Extracted X images for article: ..."
        match = re.search(r"Extracted (\d+) images for article", text)
        if match:
            count = int(match.group(1))
            result["images_per_article"].append(count)
            if count > 0:
                result["articles_with_images"] += 1
        
        # Batch completion: "Enriched X articles with Y total images"
        match = re.search(r"Enriched (\d+) articles with (\d+) total images", text)
        if match:
            result["completed"] = True
            result["total_images_extracted"] = int(match.group(2))
        
        # Classification errors
        if "Failed to classify image" in text:
            result["classification_errors"] += 1
        
        # Vision API errors
        if "Vision classification error" in text:
            result["vision_errors"] += 1
        
        # Image enrichment failures
        if "Image enrichment failed" in text:
            result["classification_errors"] += 1
    
    # Determine overall status
    if not result["started"]:
        result["status"] = "skipped"
    elif result["completed"] and result["classification_errors"] == 0:
        result["status"] = "success"
    elif result["completed"]:
        result["status"] = "partial"
    else:
        result["status"] = "failed"
    
    return result


def analyze_briefings(logs: List[Dict]) -> Dict:
    """Analyze Agent 1 and Agent 2 briefing generation."""
    result = {
        "agent1_started": False,
        "agent1_completed": False,
        "agent2_started": False,
        "agent2_completed": False,
        "pre_brief_id": None,
        "weekly_brief_id": None,
        "errors": []
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        # Agent 1
        if "Agent 1: Generating pre-brief" in text:
            result["agent1_started"] = True
        if "Agent 1: Pre-brief" in text and "generated and stored" in text:
            result["agent1_completed"] = True
            match = re.search(r"Pre-brief ([a-f0-9-]+) generated", text)
            if match:
                result["pre_brief_id"] = match.group(1)
                
        # Agent 2
        if "Agent 2: Generating high-conviction" in text:
            result["agent2_started"] = True
        if "Agent 2: Weekly briefing generated" in text:
            result["agent2_completed"] = True
            
        # Errors
        if "Error in Agent 1" in text or "Error in Agent 2" in text:
            result["errors"].append(text)
            
    return result


def get_bq_article_counts(date_str: str) -> Dict:
    """Get article counts from BigQuery for a specific date."""
    result = {
        "articles_table": 0,
        "embeddings_table": 0,
        "digest_items_table": 0,
        "article_images_table": 0,
        "images_by_type": {},
        "by_source": {}
    }
    
    # Articles count (uses fetched_at)
    query = f"""
    SELECT COUNT(*) as cnt 
    FROM `{PROJECT_ID}.{BQ_DATASET}.articles` 
    WHERE DATE(fetched_at) = '{date_str}'
    """
    rows = run_bq_query(query)
    if rows:
        result["articles_table"] = int(rows[0].get("cnt", 0))
    
    # Articles by source type
    query = f"""
    SELECT source_type, COUNT(*) as cnt 
    FROM `{PROJECT_ID}.{BQ_DATASET}.articles` 
    WHERE DATE(fetched_at) = '{date_str}'
    GROUP BY source_type
    """
    rows = run_bq_query(query)
    for row in rows:
        result["by_source"][row.get("source_type", "unknown")] = int(row.get("cnt", 0))
    
    # Embeddings count (article_chunk_embeddings uses created_at)
    query = f"""
    SELECT COUNT(*) as cnt 
    FROM `{PROJECT_ID}.{BQ_DATASET}.article_chunk_embeddings` 
    WHERE DATE(created_at) = '{date_str}'
    """
    rows = run_bq_query(query)
    if rows:
        result["embeddings_table"] = int(rows[0].get("cnt", 0))
    
    # Digest items count (uses ingested_at)
    query = f"""
    SELECT COUNT(*) as cnt 
    FROM `{PROJECT_ID}.{BQ_DATASET}.digest_items` 
    WHERE DATE(ingested_at) = '{date_str}'
    """
    rows = run_bq_query(query)
    if rows:
        result["digest_items_table"] = int(rows[0].get("cnt", 0))
    
    # Article images count (uses extracted_at)
    query = f"""
    SELECT COUNT(*) as cnt 
    FROM `{PROJECT_ID}.{BQ_DATASET}.article_images` 
    WHERE DATE(extracted_at) = '{date_str}'
    """
    rows = run_bq_query(query)
    if rows:
        result["article_images_table"] = int(rows[0].get("cnt", 0))
    
    # Images by type
    query = f"""
    SELECT image_type, COUNT(*) as cnt 
    FROM `{PROJECT_ID}.{BQ_DATASET}.article_images` 
    WHERE DATE(extracted_at) = '{date_str}'
    GROUP BY image_type
    """
    rows = run_bq_query(query)
    for row in rows:
        result["images_by_type"][row.get("image_type", "unknown")] = int(row.get("cnt", 0))
    
    return result


def get_bq_briefing_counts(date_str: str) -> Dict:
    """Get briefing counts from BigQuery."""
    result = {
        "pre_briefings": 0,
        "weekly_briefings": 0
    }
    
    # Pre-briefings (uses generated_at)
    query = f"""
    SELECT COUNT(*) as cnt 
    FROM `{PROJECT_ID}.{BQ_DATASET}.pre_briefings` 
    WHERE DATE(generated_at) = '{date_str}'
    """
    rows = run_bq_query(query)
    if rows:
        result["pre_briefings"] = int(rows[0].get("cnt", 0))
        
    # Weekly briefings (uses generated_at)
    query = f"""
    SELECT COUNT(*) as cnt 
    FROM `{PROJECT_ID}.{BQ_DATASET}.weekly_briefings` 
    WHERE DATE(generated_at) = '{date_str}'
    """
    rows = run_bq_query(query)
    if rows:
        result["weekly_briefings"] = int(rows[0].get("cnt", 0))
        
    return result


def format_status(status: str) -> str:
    """Format status with emoji."""
    if status == "success":
        return "✅"
    elif status == "partial":
        return "⚠️"
    elif status == "error":
        return "❌"
    return "❓"


def analyze_detail_queries(logs: List[Dict]) -> Dict:
    """Analyze individual industry and company queries."""
    result = {
        "industry_exa": defaultdict(int),
        "industry_tavily": defaultdict(int),
        "companies": defaultdict(int),
        "failed_queries": []
    }
    
    for entry in logs:
        text = entry.get("textPayload", "")
        
        # Exa Industry Query Pattern
        match = re.search(r"Exa Query \[(.*?)\]: '(.*?)' -> (\d+) results", text)
        if match:
            cat, query, count = match.group(1), match.group(2), int(match.group(3))
            result["industry_exa"][f"{cat}: {query}"] = count

        # Tavily Industry Query Pattern
        match = re.search(r"Tavily Query \[(.*?)\]: '(.*?)' -> (\d+) results", text)
        if match:
            cat, query, count = match.group(1), match.group(2), int(match.group(3))
            result["industry_tavily"][f"{cat}: {query}"] = count
            
        # Company Query Pattern
        match = re.search(r"Company Query: '(.*?)' -> (\d+) results", text)
        if match:
            name, count = match.group(1), int(match.group(2))
            result["companies"][name] = count
            
        # Failures
        if "Exa query failed" in text or "Tavily query failed" in text or "Web search failed" in text:
            result["failed_queries"].append(text)
            
    return result

def print_header(text: str, color: str = None):
    """Print a formatted header."""
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "bold": "\033[1m",
        "end": "\033[0m"
    }
    
    if os.name == 'nt':  # Basic check for Windows, though modern terminals support ANSI
        print(f"\n{'=' * 70}\n {text.upper()}\n{'=' * 70}")
    else:
        c = colors.get(color, "")
        end = colors["end"] if color else ""
        print(f"\n{c}{'=' * 70}{end}")
        print(f"{c} {text.upper()}{end}")
        print(f"{c}{'=' * 70}{end}")

def generate_report(run_type: str = "latest", target_date: str = None, hours_back: int = 24):
    """Generate the full high-fidelity ingestion report."""
    print_header("C1 Intelligence Hub - High-Fidelity Ingestion Report", "blue")
    print(f"Report Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    # 1. Check Service Health
    print(f"\n🔍 SERVICE CHECK")
    print("-" * 40)
    print(f"   Project:  {PROJECT_ID}")
    print(f"   Service:  {SERVICE_NAME}")
    print(f"   Dataset:  {BQ_DATASET}")
    
    # Find recent runs
    runs = find_ingestion_runs(hours_back)
    
    if not runs:
        print("\n❌ CRITICAL: No ingestion runs detected in last {hours_back} hours.")
        print("   Check Cloud Scheduler configurations and Cloud Run triggers.")
        return
    
    # Filter runs based on type
    if run_type == "morning":
        runs = [r for r in runs if r["type"] == "morning"]
    elif run_type == "evening":
        runs = [r for r in runs if r["type"] == "evening"]
    elif run_type == "latest":
        runs = [runs[0]] if runs else []
    
    if target_date:
        runs = [r for r in runs if r["date"] == target_date]
    
    for run in runs:
        run_label = run["type"].upper() if run["type"] != "manual" else "MANUAL"
        print(f"\n🚀 {run_label} RUN: {run['datetime'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # Get logs for this run window
        logs = get_run_logs(run["datetime"] - timedelta(minutes=2), duration_minutes=45)
        
        if not logs:
            print("   ⚠️  Logs inaccessible for this time window.")
            continue
            
        steps = analyze_pipeline_steps(logs)
        
        # --- DASHBOARD SECTION ---
        print("\n🏆 INGESTION DASHBOARD")
        print("=" * 40)
        overall_status = "SUCCESS" if steps["complete"] else "INCOMPLETE"
        status_emoji = "✅" if steps["complete"] else "❌"
        print(f"   Status:    {status_emoji} {overall_status}")
        print(f"   Fetched:   {steps['total_articles_fetched']} articles")
        print(f"   Stored:    {steps['unique_after_dedup']} unique articles")
        if steps["execution_time"]:
            print(f"   Duration:  {int(steps['execution_time']//60)}m {int(steps['execution_time']%60)}s")
            
        if steps["total_articles_fetched"] > 0:
            efficiency = (steps["unique_after_dedup"] / steps["total_articles_fetched"]) * 100
            print(f"   Efficiency: {efficiency:.1f}% (New content ratio)")

        # --- SOURCE FIDELITY ---
        print("\n📡 SOURCE FIDELITY ANALYSIS")
        print("-" * 40)
        
        # StockNews
        sn = analyze_stocknews(logs)
        print(f"   {format_status(sn['status'])} StockNewsAPI: {sn['total_articles']} fetched ({sn['api_calls']} API calls)")
        
        # Web / Exa
        # Web / Exa / Tavily Combined
        web = analyze_web_search(logs)
        detail = analyze_detail_queries(logs)
        
        print(f"   {format_status(web['status'])} Web Search Total: {web['total_articles']} fetched")
        
        # Exa Detail
        print(f"      🔹 Exa.ai:       {web['exa_count']} articles")
        print(f"         └─ Ind. Qbs:  {web['exa_industry_queries']} executed")
        print(f"         └─ Comp. Qbs: {web['company_queries']} executed")
        
        if detail["industry_exa"]:
            print(f"         └─ Top Exa Queries:")
            sorted_iq = sorted(detail["industry_exa"].items(), key=lambda x: x[1], reverse=True)[:3]
            for q, c in sorted_iq:
                print(f"            • {q[:35]}... -> {c}")

        # Tavily Detail
        print(f"      🔹 Tavily:       {web['tavily_count']} articles")
        print(f"         └─ Ind. Qbs:  {web['tavily_industry_queries']} executed")
        
        if detail["industry_tavily"]:
            print(f"         └─ Top Tavily Queries:")
            sorted_iq = sorted(detail["industry_tavily"].items(), key=lambda x: x[1], reverse=True)[:3]
            for q, c in sorted_iq:
                print(f"            • {q[:35]}... -> {c}")
        
        # RSS
        rss = analyze_rss(logs)
        print(f"   {format_status(rss['status'])} RSS Feeds:     {rss['total_articles']} fetched from {len(rss['feeds'])} active feeds")
        
        # SEC / Earnings
        sec = analyze_sec(logs)
        earn = analyze_earnings(logs)
        print(f"   {format_status(sec['status'])} SEC Filings:   {format_status(sec['status'])} (Since {sec['since_date']})")
        print(f"   {format_status(earn['status'])} Earnings:      {earn['companies_checked']} companies checked")
        
        # Freight Intelligence section
        freight_status = "success" if steps.get("step1b_freight") else "unknown"
        print(f"   {format_status(freight_status)} Freight Intel:  {steps.get('freight_rates_stored', 0)} rates stored from Drewry WCI")

        # --- PIPELINE STAGES ---
        print("\n🏗️  PIPELINE STAGE METRICS")
        print("-" * 40)
        
        stage_list = [
            ("step1_rss", "1. RSS Acquisition", f"{rss['total_articles']} items ({rss['logistics_articles']} logistics)"),
            ("step1b_freight", "1b. Freight Rates", f"{steps.get('freight_rates_stored', 0)} rates"),
            ("step2_tiered_data", "2. Tiered Discovery", f"{web['total_articles']+sn['total_articles']} items"),
            ("step3_dedup", "3. Deduplication", f"{steps['unique_after_dedup']} unique"),
            ("step4_enriching", "4. AI Enrichment", f"Complete" if steps["step4_enriching"] else "Pending"),
            ("step5_classifying", "5. LLM Classification", f"{steps['classified']} classified"),
            ("step5b_images", "5b. Image Vision", "Active" if steps["step5b_images"] else "Skipped"),
            ("step6a_bq_articles", "6a. BigQuery Article", "Stored" if steps["step6a_bq_articles"] else "Pending"),
            ("step6c_bq_digest", "6c. BigQuery Digest", "Stored" if steps["step6c_bq_digest"] else "Pending"),
            ("step7_vectors", "7. Vector Indexing", "Synced" if steps["step7_vectors"] else "Pending"),
            ("step9_briefings", "9. Pulse Generator", "Ready" if steps["step9_briefings"] else "Pending"),
        ]
        
        for key, name, met in stage_list:
            status = "✅" if steps[key] else "⬜"
            print(f"   {status} {name:<22} | {met}")

        # --- BRIEFING GENERATION STATUS ---
        print("\n🧠 BRIEFING GENERATION STATUS")
        print("-" * 40)
        brief = analyze_briefings(logs)
        bq_brief = get_bq_briefing_counts(run["date"])
        
        a1_status = "✅" if brief["agent1_completed"] else "❌" if brief["agent1_started"] else "⬜"
        a2_status = "✅" if brief["agent2_completed"] else "❌" if brief["agent2_started"] else "⬜"
        
        print(f"   {a1_status} Agent 1 (Pre-Brief):   {'Completed' if brief['agent1_completed'] else 'Failed/Pending'}")
        if brief["pre_brief_id"]:
            print(f"      └─ ID: {brief['pre_brief_id']}")
        print(f"   {a2_status} Agent 2 (Synthesizer): {'Completed' if brief['agent2_completed'] else 'Failed/Pending'}")
        
        print(f"\n   BigQuery Storage (Today):")
        print(f"   • Pre-Briefings:    {bq_brief['pre_briefings']}")
        print(f"   • Weekly Briefings: {bq_brief['weekly_briefings']}")
        
        if brief["errors"]:
            print(f"\n   ⚠️  Briefing Errors:")
            for err in brief["errors"]:
                print(f"      • {err.split(' | ')[-1][:80]}")


        # --- STORAGE & DATA INTEGRITY ---
        print("\n💾 STORAGE & DATA INTEGRITY")
        print("-" * 40)
        bq = get_bq_article_counts(run["date"])
        print(f"   BigQuery Rows (Today): {bq['articles_table']} articles, {bq['digest_items_table']} digest items")
        print(f"   Vector Embeddings:     {bq['embeddings_table']} vectors created")
        
        if bq['articles_table'] > 0 and steps["unique_after_dedup"] > 0:
            sync_health = (bq['articles_table'] / steps["unique_after_dedup"]) * 100
            print(f"   Sync Integrity:        {sync_health:.1f}%")
        
        # --- ERROR & ANOMALY DETECTION ---
        errors = [parsed["text"] for parsed in [parse_log_entry(e) for e in logs] if "ERROR" in parsed["text"] or "Exception" in parsed["text"]]
        if errors or detail["failed_queries"]:
            print("\n🚨 CRITICAL ERRORS & ANOMALIES")
            print("-" * 40)
            seen_errs = set()
            for err in errors[:5]:
                # Simplify error for display
                simple_err = err.split(" | ")[-1][:80]
                if simple_err not in seen_errs:
                    print(f"   • {simple_err}")
                    seen_errs.add(simple_err)
            
            for fq in detail["failed_queries"][:3]:
                print(f"   • Query Failed: {fq[:80]}")
        else:
            print("\n🛡️  No critical errors detected in this run window.")

    print("\n" + "=" * 70)
    print(" " * 24 + "END OF HIGH-FIDELITY REPORT")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate High-Fidelity Cloud Scheduler ingestion report"
    )
    parser.add_argument(
        "--run", 
        choices=["latest", "morning", "evening", "both"],
        default="latest",
        help="Which run to report on (default: latest)"
    )
    parser.add_argument(
        "--date",
        help="Specific date to report on (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="How many hours back to look for runs (default: 24)"
    )
    
    args = parser.parse_args()
    
    try:
        generate_report(
            run_type=args.run,
            target_date=args.date,
            hours_back=args.hours
        )
    except KeyboardInterrupt:
        print("\nReport cancelled.")
    except Exception as e:
        print(f"\nError generating report: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
