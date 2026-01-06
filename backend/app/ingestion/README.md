# Ingestion Pipeline

The data ingestion system for C1 Intelligence Hub. Collects, deduplicates, enriches, classifies, and stores articles from multiple sources into BigQuery.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION ORCHESTRATOR                               │
│                         (orchestrator.py)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  DATA COLLECTORS │  │   PROCESSING     │  │      STORAGE             │   │
│  │  (app/tools/)    │  │   PIPELINE       │  │                          │   │
│  │                  │  │                  │  │                          │   │
│  │  • RSS Feeds     │  │  1. Dedup        │  │  BigQuery Tables:        │   │
│  │  • Exa.ai (91)   │──▶│  2. Scraper     │──▶│  • articles              │   │
│  │  • Tavily (145)  │  │  3. Classifier   │  │  • digest_items          │   │
│  │  • SEC EDGAR     │  │  4. Entity Link  │  │  • article_chunk_embeddings │
│  │  • FMP News      │  │  5. Image Enrich │  │  • ingestion_events      │   │
│  │  • StockNews     │  │                  │  │                          │   │
│  │  • Drewry (WCI)  │  │                  │  │                          │   │
│  │  • Earnings      │  │                  │  │                          │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Configuration

| Parameter | Value | Location |
|-----------|-------|----------|
| **Lookback Window** | 2 days | `orchestrator.py:207` |
| **Classifier Concurrency** | 10 concurrent | `classifier.py:295` |
| **Classifier Sleep** | 0.2s between calls | `classifier.py:303` |
| **Embedding Batch Size** | 5 chunks | `bq_vector_store.py:545` |
| **Insert Batch Size** | 5 rows | `bq_vector_store.py:607` |

## Data Sources

### Flash Loop Sources (Frequent, Real-Time)
| Source | Type | Articles/Day | Notes |
|--------|------|--------------|-------|
| RSS Feeds | 14 feeds | ~50-100 | CompositesWorld, JEC, FreightWaves, etc. |
| Exa.ai | 91 queries | ~200-400 | Neural search, high quality |
| Tavily | 145 queries | ~100-200 | Web crawl, broad coverage |
| FMP Premium News | API | ~50-100 | Benzinga, Seeking Alpha |

### Deep Loop Sources (Less Frequent, High Value)
| Source | Type | Articles/Week | Notes |
|--------|------|---------------|-------|
| SEC Filings | 10-K, 10-Q, 8-K | ~20-50 | Via sec-api.io |
| Earnings Transcripts | Q1-Q4 | ~40 per quarter | API Ninja |
| Drewry WCI | Freight rates | Weekly | Container shipping index |
| StockNews | Premium news | ~50-100 | Ticker-specific news |

## Processing Pipeline

1. **Deduplication** (`processing/deduplication.py`)
   - URL-based + content-hash dedup
   - Caches recent articles in memory
   - Persists to BigQuery for cross-run dedup

2. **Web Scraping** (`processing/scraper.py`)
   - Enriches articles with full text
   - Handles paywalls gracefully (403s expected)
   - Limits: 50 articles/run (200 for backfill)

3. **Classification** (`processing/classifier.py`)
   - Claude claude-sonnet-4-5 for high accuracy
   - 10 concurrent calls, 0.2s throttle
   - Outputs: category, priority, relevance, summary

4. **Entity Linking** (`processing/linker.py`)
   - Links to tracked companies from BigQuery
   - Adds company metadata (ticker, type)

5. **Image Enrichment** (optional)
   - Tavily image search
   - Claude vision classification
   - Limit: 20 articles/run

## Feed Eligibility

Articles are **always stored** in BigQuery regardless of date. The `feed_eligible` flag controls visibility in the Drumbeat feed:

```python
feed_eligible = (
    article.published_at is not None AND
    article.published_at <= now AND           # Not future date
    article.published_at >= tier2_since       # Within lookback window
)
```

## Running Ingestion

### Via Cloud Scheduler (Production)
```
# Flash Loop - Every 2 hours
POST /api/v1/scheduler/ingest?sources=rss,industry_queries,fmp_news

# Deep Loop - Every 6 hours  
POST /api/v1/scheduler/ingest?sources=sec,earnings,stocknews

# Weekly Briefing - Monday 8:30 AM CST
POST /api/v1/scheduler/briefing
```

### Manually (Local/Testing)
```bash
# Full ingestion
python -c "
from app.ingestion.orchestrator import IngestionOrchestrator, IngestionConfig
import asyncio
o = IngestionOrchestrator(IngestionConfig())
asyncio.run(o.run_full_ingestion())
"

# Specific sources only
asyncio.run(o.run_full_ingestion(sources=['rss', 'fmp_news']))

# Backfill mode (override lookback)
asyncio.run(o.run_full_ingestion(backfill_days=5))
```

## Directory Structure

```
ingestion/
├── orchestrator.py      # Main pipeline coordinator
├── config.py            # RSS feeds, keywords, entity lists
├── industry_queries.py  # 236 Exa/Tavily search queries
├── classifier.py        # Legacy (use processing/classifier.py)
├── fetchers/            # RSS fetcher
├── freight/             # Drewry WCI scraper
├── generators/          # Briefing generators (Agent 1 & 2)
├── importyeti/          # ImportYeti integration
└── processing/          # Core processing pipeline
    ├── classifier.py    # Claude-based classification
    ├── deduplication.py # URL + content dedup
    ├── linker.py        # Entity linking
    ├── scraper.py       # Web scraping/enrichment
    └── image_enrichment.py
```

## Performance (Jan 2026 Tuning)

| Metric | Before | After |
|--------|--------|-------|
| Lookback | 3 days | 2 days |
| Articles/run | 400-600 | 250-400 |
| Classification time | ~25 min | ~7-10 min |
| Total run time | ~35-40 min | ~15-20 min |

## Source Score Boost

The classifier applies a relevance score boost based on source quality tier. This helps prioritize articles from authoritative composites and business sources.

| Tier | Boost | Sources |
|------|-------|---------|
| **Tier 1: Core Composites** | +0.15 | CompositesWorld, JEC Composites, Composites Manufacturing, composites.media |
| **Tier 2: Premium Business** | +0.10 | Reuters, WSJ, Barron's, Financial Times, Bloomberg |
| **Tier 3: Quality Sector** | +0.05 | Aviation Week, Defense News, FreightWaves, Supply Chain Dive, Seeking Alpha, Flight Global, CNBC, Manufacturing Dive, Plastics News |

**How it works:**
1. Claude assigns base `relevance_score` (0.0-1.0)
2. Source boost is applied based on partial name matching
3. Final score is capped at 1.0

**Example:** An article from CompositesWorld with base score 0.7 → final score 0.85

See `processing/classifier.py` for the full `SOURCE_SCORE_BOOSTS` dictionary.

## Blocked Sources

Articles from low-quality or irrelevant sources are filtered out entirely before classification (saves API costs and improves signal quality).

| Category | Examples | Reason |
|----------|----------|--------|
| **Aggregators** | TradingView, Morningstar, GuruFocus | Repackaged content |
| **Social/Noise** | Wikipedia, YouTube, LinkedIn, Reddit, Twitter | Not news sources |
| **E-commerce** | Amazon, eBay, Alibaba | Not news |
| **AI Search** | Perplexity | Not primary sources |
| **Paywalled Teasers** | GrandViewResearch, MarketsAndMarkets, Mordor Intelligence, etc. | Just subscription prompts |

Blocked articles are logged but not classified or stored.

See `processing/classifier.py` for the full `BLOCKED_SOURCES` set.

---

*Last updated: January 5, 2026*


