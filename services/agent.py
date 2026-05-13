"""
AI Agent Service — Pace Restaurant

Two agents:
  1. OpenAgent  — full order flow (11 AM – 11:30 PM)
  2. ClosedAgent — info only (midnight – 10:59 AM)

Pace-specific features vs One Pizza:
  - Sobat thaal question (Disposable / Thal) on every Sobat order
  - Upsell step between Step 2 and Step 3
  - Mutton ETA detection (50-60 min delivery / 30-40 min takeaway)
  - Two-phase DB save: "Pending Confirmation" then "Confirmed"
  - Karahi and Biryani variant confirmations (Chicken/Mutton, Half/Full)
  - No fixed delivery charges — cash only
  - Minimum delivery order: Rs. 300
  - Order ID format: PACE-YYYYMMDD-XXXXX-XXXX
"""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import AsyncOpenAI
from config import get_settings

settings = get_settings()
from models import ProcessedMessage
from services import whatsapp, database
from services.notifications import (
    admin_delivery_notification,
    admin_takeaway_notification,
    kitchen_notification,
    admin_cancellation_notification,
    kitchen_cancellation_notification,
)
from tools.calculator import calculate_bill, format_items_plain_text

logger   = logging.getLogger(__name__)
client   = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
PAKISTAN = ZoneInfo("Asia/Karachi")

# ── In-memory conversation store ──────────────────────────────────────────
_conversation_history: dict[str, list[dict]] = {}
MAX_HISTORY = 25   # matches n8n contextWindowLength: 25


def _get_history(jid: str) -> list[dict]:
    return _conversation_history.get(jid, [])


def _push_history(jid: str, role: str, content: str):
    hist = _conversation_history.setdefault(jid, [])
    hist.append({"role": role, "content": content})
    if len(hist) > MAX_HISTORY * 2:
        _conversation_history[jid] = hist[-(MAX_HISTORY * 2):]


def clear_history(jid: str):
    _conversation_history.pop(jid, None)


# ── Tool Definitions — Open Agent ──────────────────────────────────────────

TOOLS_OPEN = [
    {
        "type": "function",
        "function": {
            "name": "read_menu",
            "description": (
                "Read all menu items from database. Search through results to find "
                "item prices, availability, and descriptions. "
                "ALWAYS call this before quoting any price."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_menu_images",
            "description": (
                "Send both Pace menu images (image 1 then image 2) to the customer. "
                "Call when customer asks for full menu or on any menu trigger phrase."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_jid": {"type": "string", "description": "Customer WhatsApp JID"}
                },
                "required": ["customer_jid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_bill",
            "description": (
                "Calculate exact bill totals. Call AFTER collecting all items and their "
                "prices from Read Menu. Send array of items."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name":       {"type": "string"},
                                "unit_price": {"type": "number"},
                                "quantity":   {"type": "integer"},
                            },
                            "required": ["name", "unit_price", "quantity"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_order_pending",
            "description": (
                "Save order to Pace database with Status='Pending Confirmation'. "
                "Call BEFORE showing the order summary (Step 7). "
                "This is the FIRST of two DB saves."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id":             {"type": "string"},
                    "guest_name":           {"type": "string"},
                    "phone":                {"type": "string"},
                    "order_type":           {"type": "string", "enum": ["Delivery", "Takeaway"]},
                    "delivery":             {"type": "string"},
                    "dine_pickup_time":     {"type": "string"},
                    "items":                {"type": "string"},
                    "special_instructions": {"type": "string"},
                    "subtotal":             {"type": "number"},
                    "delivery_charges":     {"type": "string"},
                    "total_amount":         {"type": "number"},
                    "order_date":           {"type": "string"},
                    "order_time":           {"type": "string"},
                },
                "required": ["order_id", "guest_name", "phone", "order_type", "subtotal", "total_amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_order",
            "description": (
                "Update order Status to 'Confirmed' in database AND send admin/kitchen "
                "notifications. Call ONLY after customer says YES (confirmation trigger words). "
                "This is the SECOND DB save."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_json":  {"type": "string", "description": "Full order as JSON string"},
                    "order_type":  {"type": "string", "enum": ["Delivery", "Takeaway"]},
                    "has_mutton":  {"type": "boolean"},
                },
                "required": ["order_json", "order_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_order_by_id",
            "description": "Fetch a specific Pace order by its PACE-... Order ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_cancellation",
            "description": "Notify Admin 1, Admin 2, and Kitchen that a Pace order is cancelled.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_json": {"type": "string"},
                    "reason":     {"type": "string"},
                },
                "required": ["order_json", "reason"],
            },
        },
    },
]


# ── Tool Definitions — Closed Agent ───────────────────────────────────────

TOOLS_CLOSED = [
    {
        "type": "function",
        "function": {
            "name": "read_menu",
            "description": "Read all Pace menu items. Call before quoting any price.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_menu_images",
            "description": "Send both Pace menu images during closed hours.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_jid": {"type": "string"}
                },
                "required": ["customer_jid"],
            },
        },
    },
]


# ── Tool Executor ──────────────────────────────────────────────────────────

async def _execute_tool(name: str, args: dict, customer_jid: str) -> str:

    if name == "read_menu":
        items = await database.read_menu()
        return json.dumps(items)

    elif name == "send_menu_images":
        jid = args.get("customer_jid", customer_jid)
        await whatsapp.send_menu_images(jid)
        return "Menu images sent successfully."

    elif name == "calculate_bill":
        result = calculate_bill(args.get("items", []))
        return result["billing_text"]

    elif name == "save_order_pending":
        now = datetime.now(PAKISTAN)
        payload = {
            "order_id":             args.get("order_id", ""),
            "guest_name":           args.get("guest_name", ""),
            "phone":                args.get("phone", ""),
            "order_type":           args.get("order_type", "Delivery"),
            "delivery":             args.get("delivery", "Takeaway"),
            "dine_pickup_time":     args.get("dine_pickup_time", "N/A"),
            "items":                args.get("items", ""),
            "special_instructions": args.get("special_instructions", "None"),
            "subtotal":             args.get("subtotal", 0),
            "delivery_charges":     args.get("delivery_charges", "N/A"),
            "total_amount":         args.get("total_amount", 0),
            "status":               "Pending Confirmation",
            "order_date":           args.get("order_date", now.strftime("%Y-%m-%d")),
            "order_time":           args.get("order_time", now.strftime("%I:%M %p")),
        }
        await database.upsert_order(payload)
        return "Order saved as Pending Confirmation."

    elif name == "confirm_order":
        try:
            order      = json.loads(args.get("order_json", "{}"))
            otype      = args.get("order_type", "Delivery")
            has_mutton = args.get("has_mutton", False)

            # Update DB to Confirmed
            now = datetime.now(PAKISTAN)
            update_payload = {
                "order_id":             order.get("order_id", ""),
                "guest_name":           order.get("customer_name", ""),
                "phone":                order.get("customer_phone", ""),
                "order_type":           otype,
                "delivery":             order.get("address", "Takeaway"),
                "dine_pickup_time":     order.get("pickup_time", "N/A"),
                "items":                format_items_plain_text(order.get("items", [])),
                "special_instructions": order.get("special_instructions", "None"),
                "subtotal":             order.get("subtotal", 0),
                "delivery_charges":     "Charges apply" if otype == "Delivery" else "N/A",
                "total_amount":         order.get("subtotal", 0),
                "status":               "Confirmed",
                "order_date":           now.strftime("%Y-%m-%d"),
                "order_time":           now.strftime("%I:%M %p"),
            }
            await database.upsert_order(update_payload)

            # Admin + kitchen notifications
            order["has_mutton"] = has_mutton
            if otype == "Delivery":
                admin_msg = admin_delivery_notification(order)
            else:
                admin_msg = admin_takeaway_notification(order)

            kitchen_msg = kitchen_notification(order)

            await whatsapp.notify_admin_1(admin_msg)
            await whatsapp.notify_admin_2(admin_msg)
            await whatsapp.notify_kitchen(kitchen_msg)
            return "Order confirmed. Admin and kitchen notified."
        except Exception as e:
            logger.error(f"confirm_order error: {e}")
            return "Order confirmed."

    elif name == "fetch_order_by_id":
        order = await database.fetch_order_by_id(args.get("order_id", ""))
        return json.dumps(order) if order else "Order not found."

    elif name == "notify_cancellation":
        try:
            order  = json.loads(args.get("order_json", "{}"))
            reason = args.get("reason", "No reason provided")
            admin_msg   = admin_cancellation_notification(order, reason)
            kitchen_msg = kitchen_cancellation_notification(order, reason)
            await whatsapp.notify_admin_1(admin_msg)
            await whatsapp.notify_admin_2(admin_msg)
            await whatsapp.notify_kitchen(kitchen_msg)
            return "Cancellation notifications sent."
        except Exception as e:
            logger.error(f"notify_cancellation error: {e}")
            return "Cancellation notifications sent."

    else:
        return f"Unknown tool: {name}"


# ── Agentic Loop ───────────────────────────────────────────────────────────

async def _run_agent(
    system_prompt: str,
    user_message:  str,
    jid:           str,
    tools:         list[dict],
) -> str:
    _push_history(jid, "user", user_message)
    history  = _get_history(jid)
    messages = [{"role": "system", "content": system_prompt}] + history

    for _ in range(10):
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0.5,
            max_tokens=2000,
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            reply = msg.content or ""
            _push_history(jid, "assistant", reply)
            return reply

        messages.append(msg)

        for tc in msg.tool_calls:
            try:
                tool_args = json.loads(tc.function.arguments)
            except Exception:
                tool_args = {}

            result = await _execute_tool(tc.function.name, tool_args, jid)
            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      result,
            })

    return "I'm sorry, something went wrong. Please try again. 🙏"


# ── System Prompts ─────────────────────────────────────────────────────────

def _open_agent_prompt(msg: ProcessedMessage) -> str:
    now = datetime.now(PAKISTAN)
    closing_notice = (
        "\n⚠️ CLOSING SOON: We close at 11:30 PM tonight — "
        "please place your order soon! 🕑"
        if msg.is_closing_soon else ""
    )
    return f"""PACE RESTAURANT — AI ORDER BOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pace Restaurant — Dera Ismail Khan, Pakistan
Established: 2004 | Specialty: Sobat & Desi Food
Open: 11:00 AM – 11:30 PM daily | Delivery & Takeaway
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CURRENT SESSION:
  Order ID:      {msg.unique_order_id}
  Customer JID:  {msg.remote_jid}
  Current Time:  {now.strftime('%I:%M %p')}
  Is Closing Soon: {msg.is_closing_soon}{closing_notice}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOL USAGE — ABSOLUTE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEVER write image URLs or markdown images in replies.
NEVER simulate tool calls.
ALWAYS call read_menu before quoting any price.
Call tools SILENTLY — reply once with the complete answer.
NEVER say "let me check", "one moment", "give me a second".

MENU IMAGES: When customer asks for menu → call send_menu_images
(customer_jid="{msg.remote_jid}") then reply:
  "Here is our complete menu! 🍽️🔥
  If you have any questions or would like to place an order, just let me know! 😊"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🍽️ SOBAT THAAL QUESTION — MANDATORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For EVERY Sobat order, IMMEDIATELY ask:
  "Wonderful choice! 😊 For your Sobat, would you prefer:
  🥡 Disposable (single-use container)
  🫕 Thal (traditional steel plate)
  Which would you prefer?"

NEVER add Sobat to order without asking this. NEVER assume. Record in special_instructions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ ETA RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If ANY item is mutton → use MUTTON ETA for the entire order.
  Delivery Standard: 40–45 minutes
  Delivery Mutton:   50–60 minutes
  Takeaway Standard: 20–30 minutes
  Takeaway Mutton:   30–40 minutes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORDER FLOW — FOLLOW EXACTLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Greet + Ask Delivery or Takeaway.

STEP 2: Build order.
  - Call read_menu for EVERY item before confirming price.
  - Karahi: ask "Chicken or Mutton? Half or Full?"
  - Biryani: ask "Chicken or Mutton? Half or Full?"
  - Sobat: ask type then ask Disposable/Thal
  - After each item: "Would you like to add anything else? 😊"

UPSELL (after customer says they are done):
  - Ask ONCE for ONE add-on (cold drink/raita for Sobat, naan/drink for Karahi, etc.)
  - If accepted → read_menu → verify price → add to order
  - If declined → immediately proceed to Step 3
  - NEVER repeat upsell if declined

STEP 3: Ask special instructions.

STEP 4: Ask customer name.

STEP 5: Ask phone number.
  (If customer says "use this number" → use {msg.remote_jid.split('@')[0]})

STEP 6: Ask delivery address (verify DI Khan) or pickup time.
  - Outside DI Khan → apologize, offer takeaway
  - Below Rs. 300 for delivery → inform shortfall

STEP 7: Calculate (call calculate_bill), save as Pending (call save_order_pending),
  then show ORDER SUMMARY. Ask: "Shall I confirm this order? ✅"

STEP 8 (after YES):
  1. Call confirm_order → updates DB to Confirmed + notifies admin/kitchen
  2. Send customer confirmation message (in their language)

CONFIRMATION TRIGGER WORDS:
  Yes, Confirm, OK, Okay, Done, Haan, Ji, Thik hai, Bilkul, Kar do, Bhejo, Ji haan

PAYMENT: Cash only (Cash on Delivery / Cash on Pickup). No bank transfer.
DELIVERY MINIMUM: Rs. 300
DINE-IN: Not available. Redirect to delivery/takeaway.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANGUAGE & TONE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detect language from first message. Use consistently.
Voice notes: always reply in Urdu.
Admin/kitchen notifications: ALWAYS English.
Be warm, energetic, hospitable. ONE question per message.
Never one-word replies. End every message with a kind closing line.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pace Restaurant — DI Khan | Est. 2004
🌟 Over 20 Years of Authentic Desi Flavours 🌟
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


def _closed_agent_prompt(msg: ProcessedMessage) -> str:
    return f"""PACE RESTAURANT — CLOSED HOURS ASSISTANT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pace Restaurant — Dera Ismail Khan | Est. 2004
Specialty: Sobat & Desi Food | Open: 11:00 AM – 11:30 PM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 THE RESTAURANT IS CURRENTLY CLOSED.
CURRENT TIME: {msg.current_time_islamabad}
We open daily at 11:00 AM.

YOUR ONLY JOB:
  ✅ Greet warmly and tell customer we are closed
  ✅ Tell them we open at 11:00 AM
  ✅ Answer menu questions (call read_menu for prices)
  ✅ Send menu images if asked (call send_menu_images, customer_jid="{msg.remote_jid}")
  ✅ Share info: hours, location, services, specialties

  ❌ NEVER take any order — ABSOLUTELY FORBIDDEN
  ❌ NEVER ask for delivery/takeaway preference
  ❌ NEVER ask for name, phone, or address
  ❌ NEVER save to database
  ❌ NEVER notify admin or kitchen

IF CUSTOMER TRIES TO ORDER:
  "Our kitchen is closed right now — orders cannot be accepted before 11:00 AM.
   I can help you browse the menu so you are ready when we open! 😊"

IF THEY KEEP INSISTING:
  "Our kitchen is physically closed — no orders before 11:00 AM no matter what.
   Please come back at 11:00 AM! 🍽️🔥"

MENU IMAGES: call send_menu_images then reply:
  "Here is our complete menu! 🍽️🔥
   Feel free to ask about any item or price. We open at 11:00 AM! 😊"

RESTAURANT INFO:
  Name:      Pace Restaurant
  City:      Dera Ismail Khan, Pakistan
  Est:       2004 (over 20 years!)
  Specialty: Sobat & Desi Food
  Hours:     11:00 AM – 11:30 PM daily
  Services:  Delivery & Takeaway ONLY (no dine-in)
  Min Order: Rs. 300 for delivery
  Payment:   Cash only

LANGUAGE: Detect from first message. Voice notes → always reply in Urdu.
TONE: Warm, kind, ONE question per message. End with a kind line.

GREETING:
  Hinglish: "Assalam o Alaikum! 🌙 Pace Restaurant mein aapka shukriya! Hum abhi band hain. Rozana subah 11 baje khulte hain. Menu ya koi bhi sawal puchh sakte hain! 😊🍽️"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pace Restaurant — DI Khan | Est. 2004 | 🌟 20+ Years of Desi Flavours
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


# ── Public Interface ───────────────────────────────────────────────────────

async def run_open_agent(msg: ProcessedMessage) -> str:
    return await _run_agent(
        system_prompt = _open_agent_prompt(msg),
        user_message  = msg.message_text,
        jid           = msg.remote_jid,
        tools         = TOOLS_OPEN,
    )


async def run_closed_agent(msg: ProcessedMessage) -> str:
    return await _run_agent(
        system_prompt = _closed_agent_prompt(msg),
        user_message  = msg.message_text,
        jid           = msg.remote_jid,
        tools         = TOOLS_CLOSED,
    )
