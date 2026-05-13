"""
Admin Router — Pace Restaurant

Management endpoints:
  - Manual history clear (mirrors n8n Webhook → HTTP Request DELETE)
  - Scheduled history clear at 11 AM, 11 PM, midnight
    (mirrors n8n Schedule Trigger1/2/3 → HTTP Request3/4/5)
  - Order lookup
  - Restaurant status

To run the scheduler, add APScheduler in main.py (see startup_event below).
"""

import logging
from contextlib import asynccontextmanager
from fastapi import APIRouter, HTTPException
from services.database import clear_chat_histories, fetch_order_by_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/clear-history")
async def clear_history_endpoint():
    """
    Manual trigger — mirrors n8n 'Webhook → HTTP Request1 (DELETE)' at /pacedeleter.
    """
    success = await clear_chat_histories()
    if success:
        return {"status": "cleared", "table": "n8n_chat_histories_pace"}
    raise HTTPException(status_code=500, detail="Failed to clear history")


@router.get("/order/{order_id}")
async def get_order(order_id: str):
    """Look up a Pace order by its PACE-... ID."""
    order = await fetch_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/status")
async def status():
    return {
        "restaurant":  "Pace Restaurant",
        "tagline":     "Est. 2004 — Sobat & Desi Food",
        "city":        "Dera Ismail Khan, Pakistan",
        "hours":       "11:00 AM – 11:30 PM daily",
        "services":    "Delivery & Takeaway only",
        "min_order":   "Rs. 300 (delivery)",
        "payment":     "Cash only",
    }


# ── Scheduled History Clearing ─────────────────────────────────────────────
# Add this to main.py to enable the three scheduled clears.
#
# Mirrors n8n:
#   Schedule Trigger1 → cron 0 11 * * * → HTTP Request3 (DELETE pace histories)
#   Schedule Trigger2 → cron 0 23 * * * → HTTP Request4 (DELETE pace histories)
#   Schedule Trigger3 → cron 0  0 * * * → HTTP Request5 (DELETE pace histories)
#
# ─────────────────────────────────────────────────────────────────────────
# COPY THIS INTO main.py:
#
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from services.database import clear_chat_histories
#
# scheduler = AsyncIOScheduler()
#
# @app.on_event("startup")
# async def start_scheduler():
#     scheduler.add_job(clear_chat_histories, "cron", hour=11, minute=0)  # 11 AM
#     scheduler.add_job(clear_chat_histories, "cron", hour=23, minute=0)  # 11 PM
#     scheduler.add_job(clear_chat_histories, "cron", hour=0,  minute=0)  # Midnight
#     scheduler.start()
#     logger.info("Pace history-cleanup scheduler started (11 AM, 11 PM, midnight)")
#
# @app.on_event("shutdown")
# async def stop_scheduler():
#     scheduler.shutdown()
