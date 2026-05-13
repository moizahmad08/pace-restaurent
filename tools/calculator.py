"""
Calculator Tools — Pace Restaurant
Bill calculation, item formatting, and mutton detection.
"""

from typing import List, Dict, Any


MUTTON_KEYWORDS = [
    "mutton", "lamb", "gosht", "bheja", "kheyma", "kasmaal",
    "mutton karahi", "mutton biryani", "mutton pulao",
    "bheja fry", "bheja karahi"
]


def has_mutton_item(items: List[Dict[str, Any]]) -> bool:
    """Check if any item in the order contains mutton."""
    for item in items:
        name = (item.get("name", "") or "").lower()
        if any(keyword in name for keyword in MUTTON_KEYWORDS):
            return True
    return False


def format_items_plain_text(items: List[Dict[str, Any]]) -> str:
    """Format order items as plain text for database."""
    if not items:
        return "No items"

    lines = []
    for item in items:
        name = item.get("name", "Unknown")
        qty = item.get("quantity", 1)
        price = item.get("unit_price", 0)
        total = qty * price

        # Include variant info if present
        variant = item.get("variant", "")
        if variant:
            name = f"{name} ({variant})"

        # Include thaal type if present
        thaal = item.get("thal_type", "")
        if thaal:
            thaal_emoji = "🥡" if thaal == "Disposable" else "🫕"
            name = f"{name} {thal_emoji}"

        lines.append(f"• {name} × {qty} = Rs. {total}")

    return "\n".join(lines)


def calculate_bill(items: List[Dict[str, Any]]) -> dict:
    """
    Calculate bill totals and format billing text.
    Returns dict with billing_text, subtotal, delivery_charges, total.
    """
    if not items:
        return {
            "billing_text": "No items in order.",
            "subtotal": 0,
            "delivery_charges": "N/A",
            "total": 0,
        }

    subtotal = sum(
        (item.get("unit_price", 0) or 0) * (item.get("quantity", 1) or 1)
        for item in items
    )

    # For delivery, don't show fixed charges (matches n8n prompt)
    delivery_charges = "Delivery charges will apply"
    total = subtotal

    # Build billing text
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "📋 YOUR ITEMS:",
    ]

    for item in items:
        name = item.get("name", "Unknown")
        qty = item.get("quantity", 1)
        price = item.get("unit_price", 0)
        line_total = qty * price

        variant = item.get("variant", "")
        if variant:
            name = f"{name} ({variant})"

        thaal = item.get("thal_type", "")
        if thaal:
            thaal_emoji = "🥡" if thaal == "Disposable" else "🫕"
            name = f"{name} — {thal_emoji} {thal}"

        lines.append(f"• {name} × {qty}")
        lines.append(f"  Rs. {price} each = Rs. {line_total}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "💰 BILLING:",
        f"  Subtotal:          Rs. {subtotal}",
        f"  Delivery Charge:   {delivery_charges}",
        f"                     ──────────",
        f"  TOTAL:             Rs. {total} + delivery charges",
        "💵 Payment: Cash on Delivery",
    ])

    billing_text = "\n".join(lines)

    return {
        "billing_text": billing_text,
        "subtotal": subtotal,
        "delivery_charges": delivery_charges,
        "total": total,
    }