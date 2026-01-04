# C1 Intelligence Hub v2

A production-grade intelligence platform for the composites industry, built with Next.js and FastAPI.

## Overview

C1 Intelligence Hub helps composites industry professionals stay informed with AI-powered analysis across four key areas:

| Tab | Agent | Description |
|-----|-------|-------------|
| **Market Intelligence** | Industry Watcher | News, press releases, and market trends |
| **Financial Intelligence** | Market Scout | Earnings analysis, financial data, commodities |
| **Product Intelligence** | Product Maven | Spec sheets, datasheets, competitor analysis |
| **Hub Inputs** | Data Steward | Manage tracked companies, materials, preferences |

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
| `/api/chat` | POST | Stream chat responses (SSE) |
| `/api/reports` | GET | List generated reports |
| `/api/reports/{id}` | GET | Get report content |
| `/api/reports/{id}/download` | GET | Download as markdown |
| `/api/data/companies` | GET | List tracked companies |
| `/api/data/materials` | GET | List materials |
| `/api/data/industries` | GET | List industries |
| `/api/data/preferences` | GET/PUT | User preferences |
| `/health` | GET | Health check |

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `FMP_API_KEY` | Yes | Financial Modeling Prep API key |
| `TAVILY_API_KEY` | Yes | Tavily web search API key |
| `ENVIRONMENT` | No | `development` or `production` |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

### Supply Chain Context

Use the supply chain selector to switch between different business contexts:

- **C1** - Composites One (default)
- **F1** - Fiberglass One
- **E1** - Electronics One

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
