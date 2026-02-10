"""RSS Feed Health Check - JSON Output"""
import feedparser
import json
from datetime import datetime

feeds = [
    ('CompositesWorld', 'https://www.compositesworld.com/rss/news'),
    ('JEC Composites', 'https://www.jeccomposites.com/feed/'),
    ('Composites Manufacturing (ACMA)', 'https://compositesmanufacturingmagazine.com/feed/'),
    ('ACMA News', 'https://acmanet.org/feed/'),
    ('Plastics Today', 'https://www.plasticstoday.com/rss.xml'),
    ('Aviation Week', 'https://aviationweek.com/rss.xml'),
    ('Just Auto', 'https://www.just-auto.com/feed/'),
    ('Wind Power Engineering', 'https://www.windpowerengineering.com/feed/'),
    ('Offshore Wind', 'https://www.offshorewind.biz/feed/'),
    ('Boating Industry', 'https://boatingindustry.com/feed/'),
    ('Marine Industry News', 'https://www.marineindustrynews.co.uk/feed/'),
    ('FreightWaves', 'https://www.freightwaves.com/feed'),
    ('Supply Chain Dive', 'https://www.supplychaindive.com/feeds/news/'),
    ('Supply Chain Dive Logistics', 'https://www.supplychaindive.com/feeds/topic/logistics/'),
]

results = []
for name, url in feeds:
    result = {'name': name, 'url': url, 'status': 'ERROR', 'items': 0, 'latest': 'N/A', 'error': None}
    try:
        parsed = feedparser.parse(url)
        items = len(parsed.entries)
        result['items'] = items
        
        if parsed.bozo and items == 0:
            result['status'] = 'FAIL'
            result['error'] = str(parsed.bozo_exception)[:50] if parsed.bozo_exception else 'Parse error'
        elif parsed.bozo:
            result['status'] = 'WARN'
        elif items == 0:
            result['status'] = 'EMPTY'
        else:
            result['status'] = 'OK'
        
        if items > 0:
            entry = parsed.entries[0]
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                result['latest'] = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d')
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                result['latest'] = datetime(*entry.updated_parsed[:6]).strftime('%Y-%m-%d')
    except Exception as e:
        result['error'] = str(e)[:50]

    results.append(result)

# Write to JSON file
with open('scripts/rss_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print('Results written to scripts/rss_results.json')
