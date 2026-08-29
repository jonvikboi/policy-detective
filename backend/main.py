"""
Policy Detective — FastAPI Backend Application

Main entry point for the backend server.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.db.session import init_db
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
    logger.info("Policy Detective starting up...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Policy Detective shutting down...")


app = FastAPI(
    title="Policy Detective",
    description="Agentic web investigation system for policy compliance analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "llm_model": settings.llm_model,
        "webcmd_binary": settings.webcmd_binary,
    }
