"""
Session Manager — Pace Restaurant
Mirrors the n8n 'Deduplicate & Filter' Code node exactly.

Key differences from One Pizza & Grill:
  - Open hours: 11 AM (hour 11) → 11:30 PM (hour 23)
  - Closed: hours 0–10
  - isClosingSoon: hour 23
  - No group filtering (Pace drops groups same as One Pizza)
  - No 👍 reaction handling (Pace doesn't handle reactions)
  - Order ID format: PACE-YYYYMMDD-XXXXX-XXXX
"""

import time
import random
import string
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from models import ProcessedMessage

PAKISTAN_TZ            = ZoneInfo("Asia/Karachi")
SESSION_EXPIRY_SECONDS = 5 * 60        # 5 minutes
CLEANUP_AGE_SECONDS    = 24 * 60 * 60  # 24 hours
MAX_SEEN_IDS           = 200
MAX_ORDER_IDS          = 10_000


class SessionManager:
    """In-memory session store (swap for Redis in production)."""

    def __init__(self):
        self._seen_ids:           list[str] = []
        self._order_counter:      int       = 1000
        self._issued_order_ids:   list[str] = []
        self._customer_sessions:  dict      = {}

    # ── Deduplication ──────────────────────────────────────────────────────

    def is_duplicate(self, message_id: str, remote_jid: str) -> bool:
        unique_key = f"{message_id}_{remote_jid}"
        if unique_key in self._seen_ids:
            return True
        self._seen_ids.append(unique_key)
        if len(self._seen_ids) > MAX_SEEN_IDS:
            self._seen_ids = self._seen_ids[-MAX_SEEN_IDS:]
        return False

    # ── Order ID ───────────────────────────────────────────────────────────

    def get_order_id(self, remote_jid: str) -> str:
        now_ts  = time.time()
        session = self._customer_sessions.get(remote_jid)

        if (
            session
            and session.get("order_id")
            and (now_ts - session["last_seen"]) < SESSION_EXPIRY_SECONDS
        ):
            self._customer_sessions[remote_jid]["last_seen"] = now_ts
            return session["order_id"]

        # New session → generate PACE-YYYYMMDD-XXXXX-XXXX
        self._order_counter += 1
        now_pk   = datetime.now(PAKISTAN_TZ)
        date_str = now_pk.strftime("%Y%m%d")

        attempts = 0
        while True:
            counter_part = str(self._order_counter).zfill(5)
            hex_part     = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            order_id     = f"PACE-{date_str}-{counter_part}-{hex_part}"
            attempts    += 1
            if order_id not in self._issued_order_ids or attempts > 10:
                break

        self._issued_order_ids.append(order_id)
        if len(self._issued_order_ids) > MAX_ORDER_IDS:
            self._issued_order_ids = self._issued_order_ids[-MAX_ORDER_IDS:]

        self._customer_sessions[remote_jid] = {
            "order_id":  order_id,
            "last_seen": now_ts,
        }
        self._cleanup_sessions(now_ts)
        return order_id

    def invalidate_session(self, remote_jid: str):
        """Call after order confirmed — next message starts fresh."""
        self._customer_sessions.pop(remote_jid, None)

    def _cleanup_sessions(self, now_ts: float):
        stale = [
            k for k, v in self._customer_sessions.items()
            if (now_ts - v["last_seen"]) > CLEANUP_AGE_SECONDS
        ]
        for k in stale:
            del self._customer_sessions[k]

    # ── Open-hours logic ───────────────────────────────────────────────────
    # Pace Restaurant: Open 11:00 AM (hour 11) – 11:30 PM (hour 23)
    # Closed: hours 0–10
    # isClosingSoon: hour 23

    @staticmethod
    def get_hours_info() -> dict:
        now  = datetime.now(PAKISTAN_TZ)
        hour = now.hour
        is_open         = hour >= 11          # 11 AM onward
        is_closing_soon = hour == 23          # last hour 11 PM
        time_str = now.strftime("%A, %B %d, %Y, %I:%M:%S %p")
        return {
            "current_hour":            hour,
            "is_open":                 is_open,
            "is_closing_soon":         is_closing_soon,
            "now_pk":                  now,
            "current_time_islamabad":  now.strftime(
                "%A, %B %d, %Y, %I:%M:%S %p"
            ),
        }


# ── Webhook Parser ─────────────────────────────────────────────────────────

def parse_webhook(raw: dict, session_mgr: SessionManager) -> Optional[ProcessedMessage]:
    """
    Parse raw Evolution API payload → ProcessedMessage.
    Returns None if the message should be dropped.
    Mirrors n8n Deduplicate & Filter code node for Pace.
    """
    # Evolution API can send payload at root or inside 'body'
    data = raw.get("data", {})
    if not data:
        data = raw.get("body", {}).get("data", {}) or {}
    key_data     = data.get("key", {})
    msg_data     = data.get("message", {}) or {}
    raw_type     = data.get("messageType", "")

    message_id   = key_data.get("id", "")
    from_me      = key_data.get("fromMe", False)
    remote_jid   = key_data.get("remoteJid", "")
    remote_jid_alt = key_data.get("remoteJidAlt") or remote_jid

    # ── Drop guards ──
    if not message_id:                      return None
    if from_me:                             return None
    if remote_jid.endswith("@g.us"):        return None  # no group messages

    # ── Audio detection ──
    audio_msg   = msg_data.get("audioMessage") or msg_data.get("pttMessage")
    audio_mime  = (audio_msg or {}).get("mimetype", "")
    audio_url   = (audio_msg or {}).get("url")
    is_ptt      = (audio_msg or {}).get("ptt", False)
    is_ogg_opus = "ogg" in audio_mime or "opus" in audio_mime
    is_audio    = bool(
        raw_type in ("audioMessage", "pttMessage")
        or is_ogg_opus
        or audio_mime.startswith("audio/")
        or audio_msg
    )
    msg_type = "audioMessage" if (
        is_audio and raw_type not in ("audioMessage", "pttMessage")
    ) else raw_type

    # ── Text extraction ──
    message_text = (
        msg_data.get("conversation")
        or (msg_data.get("extendedTextMessage") or {}).get("text")
        or ("[VOICE NOTE]" if is_audio else "")
    ).strip()

    # ── Secret kill-switch: "paceagentoff" → handled in webhook router ──
    # (mirrors n8n Switch → Publish output for workflow toggling)

    if not message_text and not is_audio:   return None

    # ── Deduplication ──
    if session_mgr.is_duplicate(message_id, remote_jid):
        return None

    # ── Hours & Order ID ──
    hours_info   = SessionManager.get_hours_info()
    unique_order = session_mgr.get_order_id(remote_jid)

    return ProcessedMessage(
        message_id              = message_id,
        remote_jid              = remote_jid,
        remote_jid_alt          = remote_jid_alt,
        from_me                 = from_me,
        message_text            = message_text,
        message_type            = msg_type,
        raw_msg_type            = raw_type,
        is_audio                = is_audio,
        is_ptt                  = is_ptt,
        audio_url               = audio_url,
        audio_mimetype          = audio_mime or None,
        audio_raw               = audio_msg,
        is_open                 = hours_info["is_open"],
        is_closing_soon         = hours_info["is_closing_soon"],
        current_hour            = hours_info["current_hour"],
        unique_order_id         = unique_order,
        push_name               = data.get("pushName"),
        current_time_islamabad  = hours_info["current_time_islamabad"],
    )


# Singleton
session_manager = SessionManager()
