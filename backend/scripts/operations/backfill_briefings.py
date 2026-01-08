"""
Backfill Historical Briefings Script
====================================

Generates pre_briefings and weekly_briefings for historical periods
to establish the "net_new" vs "continuing" context chain.

Must be run in chronological order so each week builds on the last.

Backfill Schedule (all times 12:00 UTC = 6:00 AM CST):
  Week 1: Dec 8-22, 2025  → "Week of December 22, 2025"
  Week 2: Dec 15-29, 2025 → "Week of December 29, 2025"  
  Week 3: Dec 22-Jan 5, 2026 → "Week of January 05, 2026" (CURRENT)

Each week runs:
  1. Agent 1 (Pre-Brief): Analyzes articles in the date range
  2. Agent 2 (Weekly Briefing): Synthesizes with historical context
"""

import asyncio
import sys
from datetime import datetime, timezone

# Backfill periods (period_start, period_end, target_week_monday)
# All times are 12:00 UTC (6:00 AM CST)
BACKFILL_WEEKS = [
    {
        "name": "Week of December 22, 2025",
        "period_start": datetime(2025, 12, 8, 12, 0, 0, tzinfo=timezone.utc),
        "period_end": datetime(2025, 12, 22, 12, 0, 0, tzinfo=timezone.utc),
        "target_week_monday": datetime(2025, 12, 22, 12, 0, 0, tzinfo=timezone.utc),
    },
    {
        "name": "Week of December 29, 2025",
        "period_start": datetime(2025, 12, 15, 12, 0, 0, tzinfo=timezone.utc),
        "period_end": datetime(2025, 12, 29, 12, 0, 0, tzinfo=timezone.utc),
        "target_week_monday": datetime(2025, 12, 29, 12, 0, 0, tzinfo=timezone.utc),
    },
    {
        "name": "Week of January 05, 2026",
        "period_start": datetime(2025, 12, 22, 12, 0, 0, tzinfo=timezone.utc),
        "period_end": datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
        "target_week_monday": datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
    },
]


async def run_backfill(week_index: int = None, skip_podcast: bool = True):
    """
    Run backfill for specified week(s).
    
    Args:
        week_index: If provided, only run that week (0, 1, or 2). 
                   If None, runs all weeks in sequence.
        skip_podcast: Skip podcast generation for backfill (faster, cheaper)
    """
    from app.ingestion.generators.pre_briefing import PreBriefGenerator
    from app.ingestion.generators.weekly_briefing import WeeklyBriefingGenerator
    
    weeks_to_run = [BACKFILL_WEEKS[week_index]] if week_index is not None else BACKFILL_WEEKS
    
    for i, week in enumerate(weeks_to_run):
        actual_index = week_index if week_index is not None else i
        print(f"\n{'='*60}")
        print(f"BACKFILL {actual_index + 1}/3: {week['name']}")
        print(f"Period: {week['period_start'].date()} to {week['period_end'].date()}")
        print(f"{'='*60}")
        
        # Step 1: Generate Pre-Brief (Agent 1)
        print(f"\n--- Agent 1: Generating Pre-Brief ---")
        agent1 = PreBriefGenerator()
        pre_brief = await agent1.generate_pre_brief(
            start_date=week['period_start'],
            end_date=week['period_end']
        )
        
        if not pre_brief:
            print(f"ERROR: Agent 1 failed for {week['name']}")
            print("Aborting backfill - cannot proceed without pre-brief")
            return False
        
        print(f"SUCCESS: Pre-brief generated with {pre_brief.get('article_count', 0)} articles")
        print(f"Pre-brief ID: {pre_brief.get('id')}")
        
        # Step 2: Generate Weekly Briefing (Agent 2)
        print(f"\n--- Agent 2: Generating Weekly Briefing ---")
        agent2 = WeeklyBriefingGenerator()
        
        # Optionally skip podcast for faster backfill
        if skip_podcast:
            # Temporarily disable ElevenLabs
            original_key = agent2.config.elevenlabs_api_key
            agent2.config.elevenlabs_api_key = None
        
        try:
            briefing = await agent2.generate(
                pre_brief=pre_brief,
                target_week_monday=week['target_week_monday']
            )
        finally:
            if skip_podcast:
                agent2.config.elevenlabs_api_key = original_key
        
        if not briefing:
            print(f"ERROR: Agent 2 failed for {week['name']}")
            print("Aborting backfill - cannot proceed without weekly briefing")
            return False
        
        print(f"SUCCESS: Weekly briefing generated!")
        print(f"Title: {briefing.get('briefing_title')}")
        print(f"Briefing ID: {briefing.get('id')}")
        print(f"Sections: {len(briefing.get('sections', []))}")
        
        # Pause between weeks to avoid rate limits
        if i < len(weeks_to_run) - 1:
            print(f"\nWaiting 10 seconds before next week...")
            await asyncio.sleep(10)
    
    print(f"\n{'='*60}")
    print("BACKFILL COMPLETE!")
    print(f"{'='*60}")
    return True


async def verify_backfill():
    """Verify the backfill results in BigQuery."""
    from google.cloud import bigquery
    
    client = bigquery.Client()
    
    print("\n=== Pre-Briefings ===")
    pre_query = """
        SELECT id, period_start, period_end, article_count, generated_at
        FROM `gen-lang-client-0436975498.c1_intelligence.pre_briefings`
        ORDER BY period_end ASC
    """
    pre_results = list(client.query(pre_query).result())
    for r in pre_results:
        print(f"  {r.period_end.date()}: {r.article_count} articles (id={r.id[:8]}...)")
    
    print("\n=== Weekly Briefings ===")
    weekly_query = """
        SELECT id, briefing_title, period_end, generated_at
        FROM `gen-lang-client-0436975498.c1_intelligence.weekly_briefings`
        ORDER BY period_end ASC
    """
    weekly_results = list(client.query(weekly_query).result())
    for r in weekly_results:
        print(f"  {r.briefing_title} (id={r.id[:8]}...)")
    
    print(f"\nTotal: {len(pre_results)} pre_briefings, {len(weekly_results)} weekly_briefings")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Backfill historical briefings')
    parser.add_argument('--week', type=int, choices=[0, 1, 2], 
                       help='Run specific week only (0=Dec 22, 1=Dec 29, 2=Jan 5)')
    parser.add_argument('--verify', action='store_true',
                       help='Only verify existing backfill, do not generate')
    parser.add_argument('--with-podcast', action='store_true',
                       help='Include podcast generation (slower, costs more)')
    args = parser.parse_args()
    
    if args.verify:
        asyncio.run(verify_backfill())
    else:
        print("Starting backfill process...")
        print("This will generate pre_briefings and weekly_briefings for historical periods.")
        print(f"Podcast generation: {'ENABLED' if args.with_podcast else 'DISABLED (faster)'}")
        print()
        
        success = asyncio.run(run_backfill(
            week_index=args.week,
            skip_podcast=not args.with_podcast
        ))
        
        if success:
            print("\nVerifying results...")
            asyncio.run(verify_backfill())
        else:
            print("\nBackfill failed. Check logs above.")
            sys.exit(1)


if __name__ == "__main__":
    main()
