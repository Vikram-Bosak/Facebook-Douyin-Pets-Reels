#!/usr/bin/env python3
"""
Facebook-Douyin-Pets-Reels - Main Pipeline Agent
Searches Bilibili for pet videos and downloads them using the
playurl API (no yt-dlp, no cookies needed).

Output: raw pet video clips in workspace/videos/
"""

import os
import sys
import logging
import json
from pathlib import Path

from src.agent_1_downloader import download_pet_videos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---- configuration ----
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "workspace"))
VIDEOS_DIR = WORKSPACE / "videos"
STATE_FILE = WORKSPACE / "state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"downloaded": [], "edited": []}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def ensure_dirs():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def run_pipeline():
    logger.info("=== Facebook-Douyin-Pets-Reels Pipeline Start ===")
    ensure_dirs()
    state = load_state()

    # Step 1: download videos from Bilibili
    logger.info("Step 1: Downloading pet videos from Bilibili...")
    downloaded = download_pet_videos(
        output_dir=str(VIDEOS_DIR),
        already_done=state.get("downloaded", []),
    )
    if not downloaded:
        logger.warning("No new videos downloaded. Pipeline ending.")
        return

    # Step 2: summary
    logger.info("Pipeline complete. Downloaded %d videos.", len(downloaded))
    logger.info("Videos saved to: %s", VIDEOS_DIR)

    # update state
    state["downloaded"] = list(set(state.get("downloaded", []) + downloaded))
    save_state(state)


if __name__ == "__main__":
    try:
        run_pipeline()
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        sys.exit(1)
