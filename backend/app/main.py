"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config.settings import settings
from app.api.routes import chat, reports, data, digest, briefing, podcast, ingest, products, companies, industries, data_preferences, data_ingestion, scheduler, deep_research, exa_pipeline, datasheets, memory, auth, discovery, guide, supply_network, supply_chain_agent, industry_narratives, financial_feed, expert_feed, evals, feedback
from app.utils.logger import setup_logging, get_logger

# ImportYeti supply chain data now handled via MCP tools (supply_chain.py)
# No REST router needed - agents query via get_company_supply_chain etc.

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging(level=settings.log_level)
    logger.info(f"Starting C1 Intelligence Hub v2 - {settings.environment}")
    logger.info(f"LangSmith tracing: {settings.langchain_tracing_v2}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down C1 Intelligence Hub v2")


app = FastAPI(
    title="C1 Intelligence Hub",
    description="Real-time supply chain intelligence for the composites industry",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js (legacy)
        "http://127.0.0.1:3000",
        "http://localhost:5173",   # Vite (new architecture)
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes - New Architecture
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(digest.router, prefix="/api/digest", tags=["digest"])
app.include_router(briefing.router, prefix="/api/pulse", tags=["pulse"])
app.include_router(podcast.router, prefix="/api/podcast", tags=["podcast"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingestion"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(companies.router, tags=["companies"])
app.include_router(industries.router, tags=["industries"])
app.include_router(data_preferences.router, tags=["data-preferences"])
app.include_router(data_ingestion.router, prefix="/api", tags=["data-ingestion"])
app.include_router(scheduler.router, prefix="/api", tags=["scheduler"])
app.include_router(deep_research.router, prefix="/api/research/deep", tags=["deep-research"])
app.include_router(exa_pipeline.router, prefix="/api/pipeline", tags=["exa-pipeline"])
app.include_router(datasheets.router, prefix="/api/datasheets", tags=["datasheets"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(discovery.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(guide.router, prefix="/api/guide", tags=["guide"])
app.include_router(supply_network.router, prefix="/api/supply-network", tags=["supply-network"])
app.include_router(supply_chain_agent.router, prefix="/api/supply-network", tags=["supply-chain-agent"])
app.include_router(industry_narratives.router, prefix="/api/industry-narratives", tags=["industry-narratives"])
app.include_router(financial_feed.router, prefix="/api/discovery", tags=["discovery-financial"])
app.include_router(expert_feed.router, prefix="/api/discovery", tags=["discovery-expert"])
app.include_router(evals.router, prefix="/api/evals", tags=["evals"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "environment": settings.environment,
    }


@app.get("/health")
async def health_check_root():
    """Root health check endpoint (alias)."""
    return await health_check()


# Serve static files (for production - Next.js build output)
# In Docker: /app/app/main.py, frontend at /app/frontend/out
# Local: backend/app/main.py, frontend at frontend/out (relative to project root)
static_path = Path(__file__).parent.parent / "frontend" / "out"
if static_path.exists():
    logger.info(f"Serving static files from: {static_path}")
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
else:
    logger.warning(f"Static files not found at: {static_path}")


# Trigger reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )
