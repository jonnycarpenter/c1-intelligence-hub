# C1 Intelligence Hub

An AI-powered intelligence platform for the composites industry, built with Next.js and FastAPI, deployed on Google Cloud Run.

## Overview

C1 Intelligence Hub helps composites industry professionals stay informed with AI-powered briefings, deep research, and organizational memory.

### Core Features

| Feature | Description |
|---------|-------------|
| **Ad-Hoc Briefings** | On-demand AI briefings on any topic with real-time web search |
| **Weekly Executive Briefings** | 2-agent pipeline with podcast generation (ElevenLabs TTS) |
| **[Deep Research](#deep-research)** | 7-node LangGraph pipeline with parallel agents, real-time streaming |
| **Saved Reports** | Browse and reload past Deep Research reports from sidebar |
| **Pipeline Dashboard** | Track news from 50+ industry sources via Exa/Tavily |
| **Long-Term Memory** | Save insights to BigQuery with team-based retrieval |
| **Preferences** | Manage priority/blocked topics for personalized briefings |
| **Login Gate** | Team-based access (Sales East/West, Marketing, Product/Supplier) |

### Data Sources

- **Exa AI** - Semantic web search for industry news
- **Tavily** - Real-time web search with date filtering  
- **BigQuery** - Article corpus with 768-dim embeddings
- **SEC EDGAR** - Company filings and press releases
- **Financial APIs** - FMP, API Ninja for earnings data

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Cloud Run Container                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │   Next.js Frontend  │───►│      FastAPI Backend        │ │
│  │   (Static Export)   │    │                             │ │
│  └─────────────────────┘    │  ┌─────────────────────────┐│ │
│                              │  │    LangGraph Workflow   ││ │
│                              │  │    ┌─────────────────┐  ││ │
│                              │  │    │  Router (Haiku) │  ││ │
│                              │  │    └────────┬────────┘  ││ │
│                              │  │             │           ││ │
│                              │  │   ┌─────────┴─────────┐ ││ │
│                              │  │   │    Agent Pool     │ ││ │
│                              │  │   │ (Sonnet 4 each)   │ ││ │
│                              │  │   └─────────┬─────────┘ ││ │
│                              │  │             │           ││ │
│                              │  │   ┌─────────┴─────────┐ ││ │
│                              │  │   │    MCP Tools      │ ││ │
│                              │  │   └───────────────────┘ ││ │
│                              │  └─────────────────────────┘│ │
│                              └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- API Keys: Anthropic, FMP, Tavily

### Development Setup

1. **Clone and configure environment:**
```bash
cd c1-intelligence-hub_v2
cp .env.example .env
# Edit .env with your API keys
```

2. **Start backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

3. **Start frontend (new terminal):**
```bash
cd frontend
npm install
npm run dev
```

4. **Open http://localhost:3000**

### Docker Development

```bash
# Create .env file first
docker-compose up
```

### Production Build

```bash
docker build -t c1-intelligence-hub .
docker run -p 8080:8080 --env-file .env c1-intelligence-hub
```

## Project Structure

```
c1-intelligence-hub_v2/
├── frontend/                 # Next.js 16 App Router
│   ├── src/
│   │   ├── app/             # App router pages
│   │   ├── components/      # React components
│   │   │   ├── chat/       # Chat interface
│   │   │   ├── dashboard/  # Pulse, briefings, podcast player
│   │   │   ├── layout/     # Header, sidebar
│   │   │   ├── memory/     # PreferencesPanel, memory log
│   │   │   ├── research/   # ResearchCanvas, SavedReportsPanel
│   │   │   └── ...         # Other feature components
│   │   ├── hooks/          # useDeepResearch, useDigest, etc.
│   │   ├── lib/            # API client, utilities
│   │   └── types/          # TypeScript types
│   └── package.json
│
├── backend/                  # FastAPI + LangGraph
│   ├── app/
│   │   ├── agents/         # Agent implementations
│   │   │   └── research/   # Deep Research agents (7-node workflow)
│   │   ├── api/            # REST API routes
│   │   ├── config/         # Settings and prompts
│   │   ├── db/             # BigQuery storage layer
│   │   ├── graph/          # LangGraph workflows
│   │   ├── ingestion/      # Data collection + briefing generators
│   │   ├── mcp/            # MCP tool server
│   │   │   └── tools/      # Tool implementations (48 tools)
│   │   └── utils/          # Helpers, retry logic, logging
│   ├── scripts/            # Operations, monitoring, testing
│   └── requirements.txt
│
├── deploy/                   # GCP deployment config (Terraform, scripts)
├── docker-compose.yml       # Development config
├── Dockerfile              # Production build
├── CLAUDE.md               # AI agent instructions
└── WORKLOG.md              # Session work log
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/briefing/adhoc` | POST | Stream ad-hoc briefing (SSE) |
| `/api/briefing/adhoc/stream` | POST | Alternative streaming endpoint |
| `/api/briefing/adhoc/session/{id}` | GET | Get session info (follow-up count, etc.) |
| `/api/briefing/adhoc/session/{id}` | DELETE | End/delete a session |
| `/api/briefing/adhoc/sessions/stats` | GET | Session manager statistics |
| `/api/research/start` | POST | Start deep research workflow |
| `/api/research/stream/{id}` | GET | Stream research progress |
| `/api/research/reports` | GET | List saved research reports |
| `/api/research/reports/{id}` | GET | Get specific research report |
| `/api/research/reports/search/related` | GET | Find related past research |
| `/api/memory/log` | GET/POST | Long-term memory CRUD |
| `/api/memory/relevant` | GET | Retrieve relevant memories |
| `/api/memory/{id}/pin` | PATCH | Pin/unpin memory |
| `/api/verify-access` | POST | Login verification |
| `/api/data/preferences` | GET/POST/DELETE | User/org preferences CRUD |
| `/api/pipeline/articles` | GET | Pipeline article search |
| `/api/podcast/briefing/{id}` | GET | Stream weekly briefing podcast audio |
| `/api/podcast/script` | POST | Generate podcast script from content |
| `/api/podcast/audio` | POST | Generate audio from script |
| `/health` | GET | Health check |

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key (primary LLM) |
| `OPENAI_API_KEY` | No | OpenAI API key (fallback LLM when Anthropic fails) |
| `TAVILY_API_KEY` | Yes | Tavily web search API key |
| `EXA_API_KEY` | Yes | Exa semantic search API key |
| `ELEVENLABS_API_KEY` | No | ElevenLabs TTS for podcast generation |
| `GCP_PROJECT_ID` | Yes | Google Cloud project ID |
| `GCP_DATASET_ID` | Yes | BigQuery dataset (e.g., `c1_intelligence`) |
| `SITE_ACCESS_PASSWORD` | Yes | Shared password for login gate |
| `FMP_API_KEY` | No | Financial Modeling Prep API key |
| `ENVIRONMENT` | No | `development` or `production` |

> **Note**: GCP project and bucket defaults are hardcoded in `backend/app/db/gcp_storage.py`
> and `backend/app/config/settings.py`. The system works without env vars for GCP config.

> **LLM Resilience**: When `OPENAI_API_KEY` is set, the system automatically falls back to OpenAI 
> (GPT-4o) if Anthropic (Claude) fails due to credit exhaustion or API errors.
> See `backend/app/utils/resilient_llm.py` for details.

### Data Storage

**BigQuery is the single source of truth.** All data flows to:
- `gen-lang-client-0436975498.c1_intelligence.digest_items` - Classified articles
- `gen-lang-client-0436975498.c1_intelligence.articles` - Raw articles with embeddings
- `gen-lang-client-0436975498.c1_intelligence.ingestion_events` - Pipeline logs

See `backend/app/db/README.md` for detailed documentation.

### Automated Data Ingestion

Cloud Scheduler jobs automatically collect data:

| Job | Schedule | Sources |
|-----|----------|---------|
| `ingest-flash-update` | Every 4 hours | RSS, StockNews, Freight |
| `ingest-deep-dive` | 2 AM CST daily | All 8 sources (industry_queries, rss, sec, earnings, stocknews, fmp_news, freight, press_releases) |
| `weekly-executive-briefing` | Mon 8:30 AM | Generates weekly briefing |

**Full documentation**: [`backend/app/ingestion/README.md`](backend/app/ingestion/README.md)  
**Deployment script**: [`deploy/scheduler/deploy_jobs.ps1`](deploy/scheduler/deploy_jobs.ps1)

#### SQLite Migration

If you have legacy data in SQLite (from GCS bucket):
```bash
gsutil cp gs://gen-lang-client-0436975498-c1-hub-data/c1_corpus.db backend/data/
cd backend && python migrate_sqlite_to_bq.py
```

### Teams

The app supports team-based memory and preferences:

- **Sales East** - Eastern region sales team
- **Sales West** - Western region sales team  
- **Marketing** - Marketing team
- **Product/Supplier** - Product and supplier intelligence
- **All Others** - Default team

## Development

### Adding a New Tool

1. Create tool in `backend/app/mcp/tools/`
2. Register in `backend/app/mcp/server.py`
3. Add to appropriate agent's tool list

### Adding a New Agent

1. Create agent in `backend/app/agents/`
2. Add system prompt in `backend/app/config/prompts.py`
3. Register in `backend/app/agents/__init__.py`
4. Update router in `backend/app/agents/router.py`

## Deep Research

**Status: ✅ PRODUCTION READY** (January 5, 2026)

A 7-node LangGraph pipeline for comprehensive industry research with parallel agent execution:

```
              ┌──► [Financial] ──┐
[Groomer] ───┤                   ├──► [Synthesizer] → [Category] → [Validator] → Report
              └──► [Industry]  ──┘
                   (parallel)
```

| Agent | Purpose |
| **Groomer** | Query interpretation, sub-query generation |
| **Financial** | SEC filings, earnings calls, analyst ratings |
| **Industry** | Trade publications, market signals, news |
| **Synthesizer** | Merge findings into executive-ready report |
| **Category** | Territory-specific sales intelligence (East/West) |
| **Validator** | Citation verification and quality gate |

**Full documentation**: [`backend/app/agents/research/README.md`](backend/app/agents/research/README.md)

**Key files**:
- Workflow: `backend/app/graph/research_workflow.py`
- Agents: `backend/app/agents/research/*.py`
- State schemas: `backend/app/agents/research/state.py`

## License

Proprietary - Composites One LLC
