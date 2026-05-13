"""
WhatsApp Service — Pace Restaurant
Evolution API operations for sending messages, media, and notifications.
"""

import logging
import httpx
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

EVOLUTION_URL = settings.evolution_api_url
EVOLUTION_KEY = settings.evolution_api_key

# Admin WhatsApp numbers
ADMIN_1 = settings.admin_1_whatsapp
ADMIN_1_INSTANCE = settings.admin_1_instance
ADMIN_2 = settings.admin_2_whatsapp
ADMIN_2_INSTANCE = settings.admin_2_instance
KITCHEN = settings.kitchen_whatsapp
KITCHEN_INSTANCE = settings.kitchen_instance

# Menu image URLs
MENU_IMAGE_1 = "https://i.ibb.co/DDMVyfnP/menu1.jpg"
MENU_IMAGE_2 = "https://i.ibb.co/v6zQkQjd/Whats-App-Image-2026-04-14-at-10-19-32-AM.jpg"


def _get_headers() -> dict:
    return {"apikey": EVOLUTION_KEY, "Content-Type": "application/json"}


async def send_text(
    jid: str,
    text: str,
    instance: str = "moiz",
) -> bool:
    """Send a text message via Evolution API."""
    async with httpx.AsyncClient() as client:
        try:
            url = f"{EVOLUTION_URL}/message/sendText/{instance}"
            resp = await client.post(
                url,
                headers=_get_headers(),
                json={"number": jid, "text": text},
                timeout=30.0,
            )
            resp.raise_for_status()
            logger.info(f"Text sent to {jid}")
            return True
        except Exception as e:
            logger.error(f"send_text error: {e}")
            return False


async def send_media(
    jid: str,
    media_url: str,
    media_type: str = "image",
    mime_type: str = "image/jpeg",
    caption: str = "",
    instance: str = "moiz",
) -> bool:
    """Send media (image/video) via Evolution API."""
    async with httpx.AsyncClient() as client:
        try:
            url = f"{EVOLUTION_URL}/message/sendMedia/{instance}"
            payload = {
                "number": jid,
                "mediatype": media_type,
                "mimetype": mime_type,
                "media": media_url,
            }
            if caption:
                payload["caption"] = caption

            resp = await client.post(
                url,
                headers=_get_headers(),
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            logger.info(f"Media sent to {jid}: {media_type}")
            return True
        except Exception as e:
            logger.error(f"send_media error: {e}")
            return False


async def send_menu_images(jid: str, instance: str = "moiz") -> bool:
    """Send both menu images to customer (menu1 then menu2)."""
    # Send first image
    success1 = await send_media(
        jid=jid,
        media_url=MENU_IMAGE_1,
        media_type="image",
        mime_type="image/jpeg",
        instance=instance,
    )

    # Send second image
    success2 = await send_media(
        jid=jid,
        media_url=MENU_IMAGE_2,
        media_type="image",
        mime_type="image/jpeg",
        instance=instance,
    )

    return success1 and success2


# ── Admin & Kitchen Notifications ───────────────────────────────────────────

async def notify_admin_1(message: str) -> bool:
    """Send notification to Admin 1."""
    return await send_text(ADMIN_1, message, instance=ADMIN_1_INSTANCE)


async def notify_admin_2(message: str) -> bool:
    """Send notification to Admin 2."""
    return await send_text(ADMIN_2, message, instance=ADMIN_2_INSTANCE)


async def notify_kitchen(message: str) -> bool:
    """Send notification to Kitchen."""
    return await send_text(KITCHEN, message, instance=KITCHEN_INSTANCE)