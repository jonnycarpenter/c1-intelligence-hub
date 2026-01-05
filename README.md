# C1 Intelligence Hub

An AI-powered intelligence platform for the composites industry, built with Next.js and FastAPI, deployed on Google Cloud Run.

## Overview

C1 Intelligence Hub helps composites industry professionals stay informed with AI-powered briefings, deep research, and organizational memory.

### Core Features

| Feature | Description |
|---------|-------------|
| **Ad-Hoc Briefings** | On-demand AI briefings on any topic with real-time web search |
| **Deep Research** | Multi-step research workflows with source grounding |
| **Pipeline Dashboard** | Track news from 50+ industry sources via Exa/Tavily |
| **Long-Term Memory** | Save insights to BigQuery with team-based retrieval |
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
├── frontend/                 # Next.js 14 App Router
│   ├── src/
│   │   ├── app/             # App router pages
│   │   ├── components/      # React components
│   │   │   ├── chat/       # Chat interface
│   │   │   ├── layout/     # Header, nav, supply chain bar
│   │   │   └── tabs/       # Tab-specific components
│   │   └── types/          # TypeScript types
│   └── package.json
│
├── backend/                  # FastAPI + LangGraph
│   ├── app/
│   │   ├── agents/         # Agent implementations
│   │   ├── api/            # REST API routes
│   │   ├── config/         # Settings and prompts
│   │   ├── graph/          # LangGraph workflow
│   │   ├── mcp/            # MCP tool server
│   │   │   └── tools/      # Tool implementations
│   │   └── utils/          # Helpers, logging
│   ├── data/               # Master data files
│   └── requirements.txt
│
├── docker-compose.yml       # Development config
├── Dockerfile              # Production build
└── BUILD_SPEC.md           # Detailed architecture doc
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/briefing/adhoc` | POST | Stream ad-hoc briefing (SSE) |
| `/api/research/start` | POST | Start deep research workflow |
| `/api/research/stream/{id}` | GET | Stream research progress |
| `/api/memory/log` | GET/POST | Long-term memory CRUD |
| `/api/memory/relevant` | GET | Retrieve relevant memories |
| `/api/memory/{id}/pin` | PATCH | Pin/unpin memory |
| `/api/verify-access` | POST | Login verification |
| `/api/data/preferences` | GET/PUT | User/org preferences |
| `/api/pipeline/articles` | GET | Pipeline article search |
| `/health` | GET | Health check |

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `TAVILY_API_KEY` | Yes | Tavily web search API key |
| `EXA_API_KEY` | Yes | Exa semantic search API key |
| `GCP_PROJECT_ID` | Yes | Google Cloud project ID |
| `GCP_DATASET_ID` | Yes | BigQuery dataset (e.g., `c1_intelligence`) |
| `SITE_ACCESS_PASSWORD` | Yes | Shared password for login gate |
| `FMP_API_KEY` | No | Financial Modeling Prep API key |
| `ENVIRONMENT` | No | `development` or `production` |

> **Note**: GCP project and bucket defaults are hardcoded in `backend/app/db/gcp_storage.py`
> and `backend/app/config/settings.py`. The system works without env vars for GCP config.

### Data Storage

**BigQuery is the single source of truth.** All data flows to:
- `gen-lang-client-0436975498.c1_intelligence.digest_items` - Classified articles
- `gen-lang-client-0436975498.c1_intelligence.articles` - Raw articles with embeddings
- `gen-lang-client-0436975498.c1_intelligence.ingestion_events` - Pipeline logs

See `backend/app/db/README.md` for detailed documentation.

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

## License

Proprietary - Composites One LLC
