"""
Notifications Service — Pace Restaurant
Admin and kitchen notification message templates.
All notifications are in ENGLISH as per n8n workflow rules.
"""

from typing import Dict, Any


def format_order_items(items_text: str) -> str:
    """Format items for notification - ensure each item on new line."""
    if not items_text:
        return "No items"

    lines = items_text.split("\n")
    formatted = []
    for line in lines:
        line = line.strip()
        if line:
            formatted.append(line)

    return "\n".join(formatted)


def _format_time(time_str: str, has_mutton: bool = False) -> str:
    """Format ETA based on mutton presence."""
    if has_mutton:
        return "50-60 minutes"
    return "40-45 minutes"


# ── Delivery Notifications ─────────────────────────────────────────────────

def admin_delivery_notification(order: Dict[str, Any]) -> str:
    """
    Admin notification for delivery order.
    ALWAYS INCLUDE ALL PRICES AND SOBAT THAAL TYPE.
    """
    items = format_order_items(order.get("items", ""))
    name = order.get("customer_name", "N/A")
    phone = order.get("customer_phone", "N/A")
    address = order.get("address", "N/A")
    subtotal = order.get("subtotal", 0)
    total = order.get("subtotal", 0)  # Same as subtotal for delivery
    has_mutton = order.get("has_mutton", False)
    eta = _format_time("", has_mutton)

    # Get thaal type if present in items
    thaal_type = ""
    if "🥡" in items:
        thaal_type = "Disposable"
    elif "🫕" in items:
        thaal_type = "Thaal"

    thaal_info = f"\n🍽️ Sobat Type: {thal_type}" if thaal_type else ""

    return f"""🔔 NEW DELIVERY ORDER — PACE RESTAURANT

📋 ORDER ID: {order.get('order_id', 'N/A')}
👤 Customer: {name}
📞 Phone: {phone}
📍 Address: {address}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🍽️ ORDER ITEMS:
{items}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{thal_info}
📝 Special: {order.get('special_instructions', 'None')}

💰 BILLING:
  Subtotal:   Rs. {subtotal}
  Delivery:   Charges apply
  TOTAL:      Rs. {total} + delivery
  Payment:    Cash on Delivery

⏱️ ETA: {eta}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌟 Pace Restaurant | Est. 2004 | DI Khan"""


def admin_takeaway_notification(order: Dict[str, Any]) -> str:
    """Admin notification for takeaway order."""
    items = format_order_items(order.get("items", ""))
    name = order.get("customer_name", "N/A")
    phone = order.get("customer_phone", "N/A")
    pickup_time = order.get("pickup_time", "N/A")
    subtotal = order.get("subtotal", 0)
    has_mutton = order.get("has_mutton", False)
    eta = "30-40 minutes" if has_mutton else "20-30 minutes"

    # Get thaal type
    thaal_type = ""
    if "🥡" in items:
        thaal_type = "Disposable"
    elif "🫕" in items:
        thaal_type = "Thaal"

    thaal_info = f"\n🍽️ Sobat Type: {thal_type}" if thaal_type else ""

    return f"""🔔 NEW TAKEAWAY ORDER — PACE RESTAURANT

📋 ORDER ID: {order.get('order_id', 'N/A')}
👤 Customer: {name}
📞 Phone: {phone}
⏰ Pickup: {pickup_time}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🍽️ ORDER ITEMS:
{items}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{thal_info}
📝 Special: {order.get('special_instructions', 'None')}

💰 BILLING:
  Subtotal:   Rs. {subtotal}
  TOTAL:      Rs. {subtotal}
  Payment:    Cash on Pickup

⏱️ Ready in: {eta}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌟 Pace Restaurant | Est. 2004 | DI Khan"""


def kitchen_notification(order: Dict[str, Any]) -> str:
    """
    Kitchen notification.
    INCLUDE SOBAT THAAL TYPE PROMINENTLY.
    """
    items = format_order_items(order.get("items", ""))
    order_type = order.get("order_type", "Delivery")
    has_mutton = order.get("has_mutton", False)
    eta = _format_time("", has_mutton)

    # Get thaal type prominently
    thaal_type = ""
    if "🥡" in items:
        thaal_type = "🥡 DISPOSABLE"
    elif "🫕" in items:
        thaal_type = "🫕 THAAL"

    thaal_info = f"\n🍽️ SOBAT: {thal_type}" if thaal_type else ""
    special = f"\n📝 Special: {order.get('special_instructions', 'None')}"

    return f"""🍳 NEW KITCHEN ORDER — PACE RESTAURANT

📋 Order ID: {order.get('order_id', 'N/A')}
🚚 Type: {order_type}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🍽️ ITEMS:
{items}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{thal_info}{special}
⏱️ ETA: {eta}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


# ── Cancellation Notifications ─────────────────────────────────────────────

def admin_cancellation_notification(order: Dict[str, Any], reason: str) -> str:
    """Admin notification when order is cancelled."""
    return f"""❌ ORDER CANCELLED — PACE RESTAURANT

📋 Order ID: {order.get('order_id', 'N/A')}
👤 Customer: {order.get('customer_name', 'N/A')}
📞 Phone: {order.get('customer_phone', 'N/A')}

📝 Reason: {reason}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌟 Pace Restaurant | Est. 2004"""


def kitchen_cancellation_notification(order: Dict[str, Any], reason: str) -> str:
    """Kitchen notification when order is cancelled."""
    return f"""❌ ORDER CANCELLED

📋 Order ID: {order.get('order_id', 'N/A')}
📝 Reason: {reason}

Kitchen, please discard this order."""