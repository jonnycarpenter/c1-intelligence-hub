# AI Agent Instructions

This file contains instructions for AI coding assistants (Claude, Gemini, Copilot, etc.)

## Project Structure

- **Backend**: `backend/` - Python FastAPI
- **Frontend**: `frontend/` - Next.js React
- **Governance docs**: `.agent/` - Architecture and coding rules

## Before Making Changes

1. Read `.agent/CODING_RULES.md` for mandatory rules
2. Read `.agent/ARCHITECTURE.md` for design decisions
3. Check relevant README files in the directory you're modifying

## Quick Rules

- BigQuery is the only database (no SQLite/ChromaDB)
- Agent tools go in `backend/app/mcp/tools/`
- Ingestion tools go in `backend/app/tools/`
- Frontend components follow existing patterns in `frontend/src/components/`

## Testing

Backend:
```bash
cd backend && python -c "from app.mcp.server import get_all_mcp_tools; print('OK')"
```

Frontend:
```bash
cd frontend && npm run build
```
