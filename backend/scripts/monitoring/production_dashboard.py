#!/usr/bin/env python3
"""
Production Intelligence Hub Dashboard
======================================

Unified monitoring dashboard that orchestrates all health checks and reports.
Provides both quick smoke tests and detailed forensic analysis.

Usage:
    python scripts/production_dashboard.py                    # Quick check (default)
    python scripts/production_dashboard.py --detailed          # Full analysis with logs
    python scripts/production_dashboard.py --days 14           # Custom lookback period
    python scripts/production_dashboard.py --detailed --days 3 # Last 3 days detailed

Components:
    - ingestion_health_check.py: BigQuery data verification, scheduler status
    - scheduler_report.py: Cloud Run log analysis, source-by-source breakdown
"""

import subprocess
import sys
import os
import argparse
from datetime import datetime

def print_banner(text: str, char: str = "="):
    """Print a formatted banner."""
    print()
    print(char * 80)
    print(f"  {text}")
    print(char * 80)
    print()

def run_script(script_name: str, args: list = None, timeout: int = 300, subdir: str = None) -> bool:
    """Run a Python script and return success status.
    
    Args:
        script_name: Name of the script file
        args: Command line arguments to pass
        timeout: Max seconds to wait (default 5 min)
        subdir: Subdirectory relative to scripts/ (e.g., 'health', 'monitoring')
    """
    # Get the scripts directory (parent of monitoring/)
    monitoring_dir = os.path.dirname(os.path.abspath(__file__))
    scripts_dir = os.path.dirname(monitoring_dir)
    
    if subdir:
        script_path = os.path.join(scripts_dir, subdir, script_name)
    else:
        # Default to same directory (monitoring/)
        script_path = os.path.join(monitoring_dir, script_name)
    
    if not os.path.exists(script_path):
        print(f"⚠️  Warning: {script_name} not found at {script_path}")
        return False
    
    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)
    
    try:
        # Run with timeout (default 5 minutes)
        result = subprocess.run(cmd, cwd=os.path.dirname(script_path), timeout=timeout)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"❌ Error: {script_name} timed out after {timeout} seconds")
        return False
    except Exception as e:
        print(f"❌ Error running {script_name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Production Intelligence Hub Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick daily check (30 sec)
  python scripts/production_dashboard.py
  
  # Full forensic analysis (3-5 min)
  python scripts/production_dashboard.py --detailed
  
  # Check last 14 days
  python scripts/production_dashboard.py --days 14
  
  # Deep dive into last 3 days
  python scripts/production_dashboard.py --detailed --days 3
        """
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Run detailed log analysis (adds 2-3 minutes)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to analyze (default: 7)"
    )
    parser.add_argument(
        "--run",
        choices=["latest", "morning", "evening", "both"],
        default="latest",
        help="Which scheduler run to analyze in detailed mode (default: latest)"
    )
    
    args = parser.parse_args()
    
    print_banner("🎯 C1 INTELLIGENCE HUB - PRODUCTION DASHBOARD", "=")
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Mode: {'DETAILED ANALYSIS' if args.detailed else 'QUICK CHECK'}")
    print(f"Lookback: {args.days} days")
    
    # Track overall success
    health_check_ok = False
    detailed_report_ok = False
    
    # ============================================================================
    # PHASE 1: HEALTH CHECK (Always Run - Critical Smoke Test)
    # ============================================================================
    print_banner("PHASE 1: SYSTEM HEALTH CHECK", "-")
    print("📊 Querying BigQuery tables and scheduler status...")
    print("   (This verifies actual data landed, not just logs)")
    print()
    
    health_check_ok = run_script("ingestion_health_check.py", [f"--days={args.days}"], subdir="health")
    
    if not health_check_ok:
        print()
        print("⚠️  Health check encountered issues (see above)")
        print()
    
    # ============================================================================
    # PHASE 2: DETAILED LOG ANALYSIS (Optional - Deep Forensics)
    # ============================================================================
    if args.detailed:
        print_banner("PHASE 2: DETAILED LOG ANALYSIS", "-")
        print("🔬 Analyzing Cloud Run logs for source-level diagnostics...")
        print("   (This shows per-source stats, errors, and execution details)")
        print()
        
        detailed_args = [f"--run={args.run}"]
        if args.days != 7:
            detailed_args.append(f"--hours={args.days * 24}")
        
        detailed_report_ok = run_script("scheduler_report.py", detailed_args)
        
        if not detailed_report_ok:
            print()
            print("⚠️  Detailed report encountered issues (see above)")
            print()
    else:
        print_banner("PHASE 2: DETAILED ANALYSIS (SKIPPED)", "-")
        print("ℹ️  Quick mode: Skipping log-based forensics")
        print("   Run with --detailed flag for source-level breakdown")
        print()
        detailed_report_ok = True  # Not a failure, just skipped
    
    # ============================================================================
    # SUMMARY
    # ============================================================================
    print_banner("DASHBOARD SUMMARY", "=")
    
    print("Component Status:")
    print(f"  {'✅' if health_check_ok else '❌'} Health Check (BigQuery + Scheduler)")
    if args.detailed:
        print(f"  {'✅' if detailed_report_ok else '❌'} Log Analysis (Source Breakdown)")
    else:
        print(f"  ⏭️  Log Analysis (Skipped - use --detailed)")
    
    print()
    
    if health_check_ok and detailed_report_ok:
        print("🎉 All checks passed!")
        print()
        print("Next Steps:")
        print("  • Monitor daily for ingestion health")
        print("  • Review any warnings flagged above")
        if not args.detailed:
            print("  • Run with --detailed if quality issues arise")
        sys.exit(0)
    else:
        print("⚠️  Some checks failed or showed warnings")
        print()
        print("Troubleshooting:")
        print("  1. Review error messages above")
        print("  2. Check Cloud Scheduler job status")
        print("  3. Verify Cloud Run service is healthy")
        print("  4. Run manual ingestion test if needed")
        sys.exit(1)

if __name__ == "__main__":
    main()
