"""
Audio Service — Pace Restaurant
Audio message transcription using OpenAI Whisper.
"""

import logging
import io
import httpx
from typing import Optional
from openai import AsyncOpenAI
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

client = AsyncOpenAI(api_key=settings.openai_api_key)

# Evolution API for getting audio base64
EVOLUTION_URL = settings.evolution_api_url
EVOLUTION_KEY = settings.evolution_api_key
EVOLUTION_INSTANCE = settings.evolution_instance


async def get_audio_base64(message_data: dict) -> Optional[str]:
    """
    Get base64 audio from Evolution API.
    message_data should be the full message object from webhook.
    """
    async with httpx.AsyncClient() as client:
        try:
            url = f"{EVOLUTION_URL}/chat/getBase64FromMediaMessage/{EVOLUTION_INSTANCE}"
            resp = await client.post(
                url,
                headers={
                    "apikey": EVOLUTION_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "message": message_data,
                    "convertToMp4": True,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("base64")
        except Exception as e:
            logger.error(f"get_audio_base64 error: {e}")
            return None


async def transcribe_audio_message(message_data: dict) -> str:
    """
    Transcribe an audio message using OpenAI Whisper.
    Returns the transcribed text.
    """
    try:
        # Get base64 audio
        base64_audio = await get_audio_base64(message_data)
        if not base64_audio:
            logger.warning("No base64 audio returned")
            return ""

        # Convert base64 to bytes
        audio_bytes = bytes.fromhex(base64_audio) if base64_audio.startswith("0x") else base64_audio.encode() if isinstance(base64_audio, str) else base64_audio

        # For base64 string, decode directly
        if isinstance(base64_audio, str):
            import base64 as b64
            audio_bytes = b64.b64decode(base64_audio)

        # Create a file-like object
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.ogg"

        # Transcribe with Whisper
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ur",  # Urdu/English mixed
        )

        transcribed = response.text.strip()
        logger.info(f"Transcription: {transcribed[:100]}")
        return transcribed

    except Exception as e:
        logger.error(f"transcribe_audio_message error: {e}")
        return ""


async def transcribe_from_url(audio_url: str) -> str:
    """
    Alternative: Transcribe audio from a direct URL.
    Downloads the audio first, then transcribes.
    """
    try:
        # Download the audio
        async with httpx.AsyncClient() as http:
            resp = await http.get(audio_url, timeout=60.0)
            resp.raise_for_status()
            audio_bytes = resp.content

        # Create file-like object
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.mp3"

        # Transcribe
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ur",
        )

        return response.text.strip()

    except Exception as e:
        logger.error(f"transcribe_from_url error: {e}")
        return ""