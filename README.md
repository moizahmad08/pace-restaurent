# 🍽️ Pace Restaurant — AI WhatsApp Order Bot
### Python (FastAPI) — Converted from n8n Workflow
**Est. 2004 | Sobat & Desi Food | Dera Ismail Khan**

---

## Architecture Overview

```
Evolution API (moiz instance)
        │
        ▼
POST /webhook/pace-restaurant         ← FastAPI (main.py)
        │
        ▼
Deduplicate & Filter (utils/session.py)
  - Deduplication by message_id + remoteJid
  - PACE-... session-scoped Order IDs
  - Open hours: 11 AM (hour 11) → 11:30 PM (hour 23)
  - isClosingSoon: hour 23
  - Kill-switch: "paceagentoff" drops message
        │
        ├── Audio? → Whisper transcription (services/audio.py)
        │
        ▼
isOpen check
  ├── TRUE  → Open Agent  (services/agent.py → run_open_agent)
  └── FALSE → Closed Agent (services/agent.py → run_closed_agent)
        │
        ▼
Agent Tools (gpt-4o-mini, temperature 0.5):
  - read_menu           → Supabase MenuPace table
  - send_menu_images    → Evolution API moiz instance (2 images)
  - calculate_bill      → Pure Python (tools/calculator.py)
  - save_order_pending  → Supabase pace_orders (Status: Pending Confirmation)
  - confirm_order       → Supabase pace_orders (Status: Confirmed) + notifications
  - fetch_order_by_id   → Supabase pace_orders
  - notify_cancellation → Admin 1 + Admin 2 + Kitchen
        │
        ▼
WhatsApp Reply → moiz instance → send_text
```

---

## n8n → Python Node Mapping

| n8n Node | Python Equivalent |
|---|---|
| `Chat Webhook` | `POST /webhook/pace-restaurant` |
| `Deduplicate & Filter` | `utils/session.py → parse_webhook()` |
| `Restaurant Configuration` | `config.py + ProcessedMessage` |
| `Switch` (Audio/Publish/Text) | `routers/webhook.py` |
| `Get Audio Base64` | `services/whatsapp.py → get_audio_base64()` |
| `Convert to File` | In-memory in `services/audio.py` |
| `Translate a recording` | `services/audio.py → transcribe_audio_message()` |
| `Set Transcription as Text` | `msg.model_copy(update={"message_text": transcribed})` |
| `isOpen Router` | `if msg.is_open` in webhook router |
| `Pace Restaurant Agent (Open)` | `services/agent.py → run_open_agent()` |
| `Pace Restaurant Agent (Closed)` | `services/agent.py → run_closed_agent()` |
| `OpenAI Chat Model` | `gpt-4o-mini` in agentic loop |
| `Postgres Chat Memory` | `_conversation_history` dict (25 msg window) |
| `Read Menu` (tool) | `database.read_menu()` |
| `Send Menu Image 1 & 2` (tool) | `whatsapp.send_menu_images()` |
| `Orders Database` (tool) | `database.upsert_order()` |
| `1st Admin WhatsApp Notification` | `whatsapp.notify_admin_1()` via One instance |
| `2nd Admin WhatsApp Notification` | `whatsapp.notify_admin_2()` via moiz instance |
| `Kitchen WhatsApp Notification` | `whatsapp.notify_kitchen()` via moiz instance |
| `Calculate_Bill` (tool) | `tools/calculator.py → calculate_bill()` |
| `Enviar texto` | `whatsapp.send_text()` moiz instance |
| `Webhook → HTTP Request1` | `POST /admin/clear-history` |
| `Schedule Trigger1/2/3` | APScheduler cron at 11 AM, 11 PM, midnight |
| `Unpublish/Publish workflow` | Kill-switch "paceagentoff" detection |

---

## Key Differences from One Pizza & Grill

| Feature | One Pizza & Grill | Pace Restaurant |
|---|---|---|
| WhatsApp instance | `One` | `moiz` |
| Open hours | 12 PM – 2 AM | 11 AM – 11:30 PM |
| isClosingSoon hour | 2 | 23 |
| Order ID prefix | `OPG-` | `PACE-` |
| DB table (menu) | `Menu` | `MenuPace` |
| DB table (orders) | `databases` | `pace_orders` |
| DB table (chat history) | `n8n_chat_histories` | `n8n_chat_histories_pace` |
| Min delivery order | Rs. 1,000 | Rs. 300 |
| Payment | Cash + Bank Alfalah | Cash only |
| DB save timing | Once (on confirm) | Twice: Pending → Confirmed |
| Sobat thaal question | ❌ | ✅ Mandatory |
| Upsell step | ❌ | ✅ Between Step 2 and 3 |
| Mutton ETA detection | ❌ | ✅ 50-60 min delivery |
| Scheduled history clears | 1 (3 AM) | 3 (11 AM, 11 PM, midnight) |
| Admin 1 instance | `One` | `One` |
| Admin 2 instance | group JID | `moiz` |

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your OPENAI_API_KEY to .env
python main.py
```

Point Evolution API webhook (`moiz` instance) to:
```
https://your-domain.com/webhook/pace-restaurant
```

---

## Enable Scheduled History Clearing

Add to `main.py` (uncomment the block in `routers/admin.py`):

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.database import clear_chat_histories

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(clear_chat_histories, "cron", hour=11, minute=0)  # 11 AM
    scheduler.add_job(clear_chat_histories, "cron", hour=23, minute=0)  # 11 PM
    scheduler.add_job(clear_chat_histories, "cron", hour=0,  minute=0)  # Midnight
    scheduler.start()
```

---

## Project Structure

```
pace_bot/
├── main.py                    # FastAPI app (port 8001)
├── config.py                  # Settings
├── requirements.txt
├── .env.example
│
├── models/
│   └── __init__.py            # Pydantic models + SobatContainer enum
│
├── routers/
│   ├── webhook.py             # POST /webhook/pace-restaurant
│   └── admin.py               # Admin utilities + scheduler docs
│
├── services/
│   ├── agent.py               # OpenAgent + ClosedAgent (full Sobat/mutton/upsell logic)
│   ├── whatsapp.py            # Evolution API (moiz instance + dual admin instances)
│   ├── database.py            # Supabase (MenuPace, pace_orders, chat histories)
│   ├── audio.py               # Whisper transcription (moiz instance)
│   └── notifications.py       # Admin/kitchen formatters (Sobat thaal + mutton ETA)
│
├── tools/
│   └── calculator.py          # Bill calculator + mutton detection
│
└── utils/
    └── session.py             # Dedup + session + open-hours (11 AM–11:30 PM)
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/webhook/pace-restaurant` | WhatsApp message receiver |
| `GET` | `/` | Root status |
| `GET` | `/health` | Health check |
| `POST` | `/admin/clear-history` | Delete chat history table |
| `GET` | `/admin/order/{order_id}` | Lookup PACE-... order |
| `GET` | `/admin/status` | Restaurant info |

---

## Restaurant Info

**Pace Restaurant**
Dera Ismail Khan, Pakistan
🗓️ Established: 2004 (20+ years of authentic desi flavours!)
🍽️ Specialty: Sobat & Desi Food
🕐 Hours: 11:00 AM to 11:30 PM daily
🚫 Delivery & Takeaway only — no dine-in
💵 Cash only (no bank transfer)
📦 Min delivery: Rs. 300
