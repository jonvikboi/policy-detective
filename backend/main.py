"""
Policy Detective — FastAPI Backend Application

Main entry point for the backend server.
"""

import sys
import asyncio
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.db.session import init_db
from backend.db.mongo import init_mongo_db, close_mongo_db
from backend.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    settings = get_settings()
    logger.info(f"Policy Detective starting up with database: {settings.database_type}...")
    await init_db()
    if settings.database_type == "mongodb":
        await init_mongo_db()
    logger.info("Databases initialized")
    yield
    logger.info("Policy Detective shutting down...")
    if settings.database_type == "mongodb":
        await close_mongo_db()


app = FastAPI(
    title="Policy Detective",
    description="Agentic web investigation system for policy compliance analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server and production deployments (Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint providing service status and documentation links."""
    return {
        "name": "Policy Detective API",
        "status": "online",
        "documentation": "/docs",
        "health": "/health",
        "endpoints": {
            "create_scan": "POST /api/scans",
            "get_scan": "GET /api/scans/{scan_id}",
            "get_report": "GET /api/scans/{scan_id}/report",
            "stream_events": "GET /api/scans/{scan_id}/events",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "database_type": settings.database_type,
        "llm_model": settings.llm_model,
        "webcmd_binary": settings.webcmd_binary,
    }
