"""
Text-to-Speech service using edge-tts.
"""

import base64
import re
from loguru import logger
import edge_tts

# We'll use a female neural voice by default
DEFAULT_VOICE = "en-US-AriaNeural"

def _clean_text_for_speech(text: str) -> str:
    """Remove markdown and special characters that TTS shouldn't read."""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`[^`]+`', '', text)
    # Remove bold/italic markers
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'\*', '', text)
    # Remove headers, blockquotes
    text = re.sub(r'[#>\-_]', '', text)
    return text.strip()

async def generate_speech_base64(text: str, emotional_state: str = "neutral") -> str | None:
    """
    Generate speech for the given text and return as base64 string.
    """
    clean_text = _clean_text_for_speech(text)
    if not clean_text:
        return None

    try:
        # Optional: Adjust voice/pitch/rate based on emotional_state
        # For edge-tts, we can pass pitch and rate string e.g., rate="+10%", pitch="-5Hz"
        rate = "+0%"
        pitch = "+0Hz"
        
        if "happy" in emotional_state or "excited" in emotional_state:
            rate = "+10%"
            pitch = "+5Hz"
        elif "sad" in emotional_state or "tired" in emotional_state:
            rate = "-10%"
            pitch = "-5Hz"
            
        communicate = edge_tts.Communicate(clean_text, DEFAULT_VOICE, rate=rate, pitch=pitch)
        
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
                
        if not audio_data:
            return None
            
        return base64.b64encode(audio_data).decode("utf-8")
        
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return None
