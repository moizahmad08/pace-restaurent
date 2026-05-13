"""
Configuration — Pace Restaurant
Loads from environment variables.
"""

import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Settings singleton — loads from environment variables."""

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Evolution API
    EVOLUTION_API_URL: str = os.getenv("EVOLUTION_API_URL", "")
    EVOLUTION_API_KEY: str = os.getenv("EVOLUTION_API_KEY", "")
    EVOLUTION_INSTANCE: str = os.getenv("EVOLUTION_INSTANCE", "moiz")

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # Restaurant
    RESTAURANT_NAME: str = os.getenv("RESTAURANT_NAME", "Pace Restaurant")
    ADMIN_1_WHATSAPP: str = os.getenv("ADMIN_1_WHATSAPP", "923306874242")
    ADMIN_1_INSTANCE: str = os.getenv("ADMIN_1_INSTANCE", "One")
    ADMIN_2_WHATSAPP: str = os.getenv("ADMIN_2_WHATSAPP", "923299881590")
    ADMIN_2_INSTANCE: str = os.getenv("ADMIN_2_INSTANCE", "moiz")
    KITCHEN_WHATSAPP: str = os.getenv("KITCHEN_WHATSAPP", "923306874242")
    KITCHEN_INSTANCE: str = os.getenv("KITCHEN_INSTANCE", "moiz")
    MINIMUM_DELIVERY_ORDER: int = int(os.getenv("MINIMUM_DELIVERY_ORDER", "300"))

    # App
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8001"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    def __init__(self):
        # Validate required fields
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")
        if not self.EVOLUTION_API_URL:
            raise ValueError("EVOLUTION_API_URL is required")
        if not self.SUPABASE_URL:
            raise ValueError("SUPABASE_URL is required")

    def __getattr__(self, item):
        # Map lowercase attribute access to uppercase fields
        upper_item = item.upper()
        if hasattr(self, upper_item):
            return getattr(self, upper_item)
        raise AttributeError(f"'Settings' object has no attribute '{item}'")


@lru_cache
def get_settings() -> Settings:
    return Settings()


# For backward compatibility
settings = get_settings()