import sys
import os

# Guarantee backend directory is in sys.path in all hosting environments
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.logging_config import setup_logging, logger
from app.database.session import engine, get_db
from app.database.init_db import init_db
from app.api.router import api_router
from app.ai.speech_service import speech_service

# Setup logging
setup_logging(debug=settings.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables and seed data
    logger.info("Initializing VoxentraAI database and default seed data...")
    init_db()
    logger.info("VoxentraAI server initialization complete.")
    yield
    # Shutdown
    logger.info("Shutting down VoxentraAI server.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise AI-Powered Citizen Grievance Redressal and Municipal Complaint Management Portal for Tamil Nadu.",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount central API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """
    Returns system health, database connectivity, and speech engine status.
    """
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"disconnected: {str(e)}"

    speech_info = speech_service.check_availability()

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "speech_engine": speech_info["engine"],
        "speech_engine_available": speech_info["available"],
        "fallback_ai_active": settings.ENABLE_FALLBACK_AI
    }


@app.get("/", tags=["Root"])
def root():
    return {
        "project": "VoxentraAI",
        "message": "Welcome to VoxentraAI Citizen Complaint Management System API",
        "docs_url": "/docs",
        "health_url": "/health",
        "api_v1": settings.API_V1_STR
    }
