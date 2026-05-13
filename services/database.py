"""
Database Service — Pace Restaurant
Supabase operations for orders, menu, and chat history.
"""

import logging
import httpx
from typing import Optional, List, Dict, Any
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SUPABASE_URL = settings.supabase_url
SUPABASE_KEY = settings.supabase_key
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


# ── Menu Operations ─────────────────────────────────────────────────────────

async def read_menu() -> List[Dict[str, Any]]:
    """Read all menu items from MenuPace table."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/MenuPace",
                headers=HEADERS,
                params={"select": "*", "order": "category.asc"},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"read_menu error: {e}")
            return []


async def get_item_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Get a specific menu item by name (case-insensitive search)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/MenuPace",
                headers=HEADERS,
                params={
                    "select": "*",
                    "name": f"ilike.%{name}%",
                },
            )
            resp.raise_for_status()
            items = resp.json()
            return items[0] if items else None
        except Exception as e:
            logger.error(f"get_item_by_name error: {e}")
            return None


# ── Order Operations ─────────────────────────────────────────────────────────

async def upsert_order(order_data: Dict[str, Any]) -> bool:
    """
    Upsert order to pace_orders table.
    Uses order_id as key - INSERT if new, UPDATE if exists.
    """
    async with httpx.AsyncClient() as client:
        try:
            # Use PATCH for upsert behavior
            headers = {**HEADERS, "Prefer": "resolution=merge-duplicates"}
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/pace_orders",
                headers=headers,
                json=[order_data],
            )
            resp.raise_for_status()
            logger.info(f"Order upserted: {order_data.get('order_id')}")
            return True
        except Exception as e:
            logger.error(f"upsert_order error: {e}")
            return False


async def fetch_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a specific order by order_id."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/pace_orders",
                headers=HEADERS,
                params={"select": "*", "order_id": f"eq.{order_id}"},
            )
            resp.raise_for_status()
            orders = resp.json()
            return orders[0] if orders else None
        except Exception as e:
            logger.error(f"fetch_order_by_id error: {e}")
            return None


async def update_order_status(order_id: str, status: str) -> bool:
    """Update order status in database."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.patch(
                f"{SUPABASE_URL}/rest/v1/pace_orders",
                headers=HEADERS,
                params={"order_id": f"eq.{order_id}"},
                json={"status": status},
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"update_order_status error: {e}")
            return False


# ── Chat History Operations ─────────────────────────────────────────────────

async def save_chat_history(
    message_id: str,
    remote_jid: str,
    direction: str,
    message_text: str,
) -> bool:
    """Save a chat message to n8n_chat_histories_pace table."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/n8n_chat_histories_pace",
                headers=HEADERS,
                json=[{
                    "message_id": message_id,
                    "remote_jid": remote_jid,
                    "direction": direction,
                    "message": message_text,
                }],
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"save_chat_history error: {e}")
            return False


async def clear_chat_histories() -> bool:
    """Clear all chat histories (called by scheduled job)."""
    async with httpx.AsyncClient() as client:
        try:
            # Delete all rows (id gte 0 covers all)
            resp = await client.delete(
                f"{SUPABASE_URL}/rest/v1/n8n_chat_histories_pace",
                headers=HEADERS,
                params={"id": "gte.0"},
            )
            resp.raise_for_status()
            logger.info("Chat histories cleared")
            return True
        except Exception as e:
            logger.error(f"clear_chat_histories error: {e}")
            return False