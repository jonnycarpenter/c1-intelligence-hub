#!/usr/bin/env python3
"""Quick RSS feed health check"""
import feedparser

feeds = [
    ('CompositesWorld', 'https://www.compositesworld.com/rss/all'),
    ('JEC Composites', 'https://www.jeccomposites.com/feed/'),
    ('Composites Manufacturing', 'https://compositesmanufacturingmagazine.com/feed/'),
    ('Reinforced Plastics', 'https://www.reinforcedplastics.com/rss/recent'),
    ('Aviation Week', 'https://aviationweek.com/rss.xml'),
    ('Automotive News', 'https://www.autonews.com/rss.xml'),
    ('FreightWaves', 'https://www.freightwaves.com/feed'),
    ('Supply Chain Dive', 'https://www.supplychaindive.com/feeds/news/'),
    ('Supply Chain Dive - Logistics', 'https://www.supplychaindive.com/feeds/topic/logistics/'),
]

print('RSS Feed Health Check')
print('=' * 70)
print(f"{'Feed Name':<35} | {'Status':<8} | {'Entries':<8} | Notes")
print('-' * 70)

total_ok = 0
total_fail = 0

for name, url in feeds:
    try:
        parsed = feedparser.parse(url)
        entries = len(parsed.entries)
        
        if entries > 0 and not parsed.bozo:
            status = "✓ OK"
            total_ok += 1
            notes = ""
        elif entries > 0:
            status = "⚠ WARN"
            total_ok += 1
            notes = str(parsed.bozo_exception)[:30] if parsed.bozo_exception else ""
        else:
            status = "✗ FAIL"
            total_fail += 1
            notes = "No entries returned"
            if parsed.bozo:
                notes = str(parsed.bozo_exception)[:30]
        
        print(f"{name:<35} | {status:<8} | {entries:<8} | {notes}")
        
    except Exception as e:
        total_fail += 1
        print(f"{name:<35} | ✗ ERROR  | 0        | {str(e)[:30]}")

print('=' * 70)
print(f"Summary: {total_ok} OK, {total_fail} Failed")
