"""
Webhook Router — Pace Restaurant
Receives Evolution API messages, deduplicates, routes, and processes.

Mirrors n8n flow:
  Chat Webhook → Deduplicate & Filter → Switch
  → [Audio] Get Audio Base64 → Convert to File → Translate → isOpen Router
  → [Text]  Restaurant Configuration Audio → isOpen Router
  → isOpen TRUE  → Pace Restaurant Agent (Open)
  → isOpen FALSE → Pace Restaurant Agent (Closed)
  → Enviar texto (send reply)

Also handles the "paceagentoff" kill-switch (mirrors n8n Switch → Publish output).
"""

import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from utils.session import session_manager, parse_webhook
from services import whatsapp
from services import audio as audio_svc
from services.agent import run_open_agent, run_closed_agent

logger = logging.getLogger(__name__)
router = APIRouter()

# Kill-switch phrase — mirrors n8n Switch condition for "paceagentoff"
KILL_SWITCH = "paceagentoff"


@router.post("/pace-restaurant")
async def chat_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives all WhatsApp messages from Evolution API (moiz instance).
    Returns 200 immediately — processes asynchronously.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    msg = parse_webhook(raw, session_manager)

    if msg is None:
        return {"status": "ignored"}

    # Kill-switch: "paceagentoff" → mirrors Unpublish/Publish workflow toggle
    # In production you can set a flag to disable the bot temporarily
    if msg.message_text.strip().lower() == KILL_SWITCH:
        logger.warning(f"Kill-switch triggered by {msg.remote_jid}")
        return {"status": "kill_switch_triggered"}

    background_tasks.add_task(process_message, msg, raw)
    return {"status": "accepted"}


async def process_message(msg, raw: dict):
    """
    Full pipeline for one incoming message:
    1. Audio → transcribe with Whisper
    2. Route: is_open → OpenAgent, else → ClosedAgent
    3. Send reply via WhatsApp (moiz instance)
    """
    try:
        # ── Audio transcription ──────────────────────────────────────────
        if msg.is_audio:
            data        = (raw.get("body", {}) or {}).get("data", {})
            message_raw = data.get("message", {})
            transcribed = await audio_svc.transcribe_audio_message(message_raw)

            if transcribed:
                logger.info(f"[AUDIO] {msg.remote_jid}: {transcribed[:80]}")
                msg = msg.model_copy(update={"message_text": transcribed})
            else:
                logger.warning(f"Empty transcription for {msg.remote_jid}")
                return

        # ── Route to agent ───────────────────────────────────────────────
        if msg.is_open:
            logger.info(f"[OPEN]   {msg.remote_jid}: {msg.message_text[:60]}")
            reply = await run_open_agent(msg)
        else:
            logger.info(f"[CLOSED] {msg.remote_jid}: {msg.message_text[:60]}")
            reply = await run_closed_agent(msg)

        # ── Send reply ───────────────────────────────────────────────────
        if reply:
            await whatsapp.send_text(
                msg.remote_jid_alt,
                reply,
                instance="moiz",    # Pace always uses moiz instance for replies
            )
            logger.info(f"Reply sent to {msg.remote_jid_alt}")

    except Exception as e:
        logger.error(f"process_message error [{msg.remote_jid}]: {e}", exc_info=True)
