"""
Main Entry Point — Pace Restaurant
FastAPI application with webhook router and admin endpoints.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from webhook import router as webhook_router
from admin import router as admin_router
from services.database import clear_chat_histories

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Scheduler for history cleanup
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: Add scheduled jobs
    scheduler.add_job(clear_chat_histories, "cron", hour=11, minute=0)  # 11 AM
    scheduler.add_job(clear_chat_histories, "cron", hour=23, minute=0)  # 11 PM
    scheduler.add_job(clear_chat_histories, "cron", hour=0, minute=0)    # Midnight
    scheduler.start()
    logger.info("Pace Restaurant bot started — scheduler running (11 AM, 11 PM, midnight)")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("Pace Restaurant bot stopped")


# Create FastAPI app
app = FastAPI(
    title="Pace Restaurant AI Order Bot",
    description="WhatsApp ordering system for Pace Restaurant, DI Khan",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(webhook_router, prefix="/webhook", tags=["Webhook"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])


@app.get("/")
async def root():
    return {
        "name": "Pace Restaurant AI Order Bot",
        "version": "1.0.0",
        "status": "running",
        "restaurant": "Pace Restaurant | Est. 2004",
        "specialty": "Sobat & Desi Food",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from config import get_settings

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )