"""
Screen Access — Cross-platform screen capture.
"""

import base64
from io import BytesIO
from loguru import logger
from PIL import Image

try:
    import mss
except ImportError:
    mss = None


def capture_screen_base64() -> str | None:
    """
    Takes a screenshot of the primary monitor and returns it as a base64 encoded JPEG.
    Used for feeding into Vision LLMs.
    """
    if not mss:
        logger.error("mss is not installed. Cannot take screenshot.")
        return None

    try:
        with mss.mss() as sct:
            # Monitor 1 is usually the primary monitor
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            # Scale down slightly to save tokens if it's very large
            max_size = (1920, 1080)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Encode as JPEG
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=80)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            return img_str
    except Exception as e:
        logger.error(f"Failed to capture screen: {e}")
        return None
