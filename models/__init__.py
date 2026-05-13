"""
Models — Pace Restaurant
"""

from pydantic import BaseModel, Field
from typing import Optional


class ProcessedMessage(BaseModel):
    """Parsed and enriched message from Evolution API."""
    message_id: str
    remote_jid: str
    remote_jid_alt: str
    from_me: bool = False
    message_text: str = ""
    message_type: str = "conversation"
    raw_msg_type: str = ""
    is_audio: bool = False
    is_ptt: bool = False
    audio_url: Optional[str] = None
    audio_mimetype: Optional[str] = None
    audio_raw: Optional[dict] = None
    is_open: bool = False
    is_closing_soon: bool = False
    current_hour: int = 0
    unique_order_id: str = ""
    push_name: Optional[str] = None
    current_time_islamabad: str = ""


class OrderPayload(BaseModel):
    """Order data structure for database."""
    order_id: str
    guest_name: str
    phone: str
    order_type: str = "Delivery"
    delivery: str = ""
    dine_pickup_time: str = ""
    items: str = ""
    special_instructions: str = "None"
    subtotal: float = 0
    delivery_charges: str = "N/A"
    total_amount: float = 0
    status: str = "Pending Confirmation"
    order_date: str = ""
    order_time: str = ""


class MenuItem(BaseModel):
    """Menu item from database."""
    id: int
    name: str
    category: str
    price: float
    description: Optional[str] = None
    available: bool = True