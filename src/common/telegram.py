"""
Telegram notification placeholder.
Replace with actual Telegram Bot API integration if needed.
"""

import os
import logging

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_notification(message: str, **kwargs):
    """Placeholder: would send a Telegram message."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram not configured. Skipping notification: %s", message)
        return
    # TODO: implement actual Telegram Bot API call
    logger.info("Telegram notification would be sent: %s", message)


def send_video(video_path: str, caption: str = ""):
    """Placeholder: would send a video via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram not configured. Skipping video send.")
        return
    # TODO: implement actual Telegram Bot API call
    logger.info("Telegram video send would happen: %s", video_path)
