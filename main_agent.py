#!/usr/bin/env python3
"""
Facebook-Douyin-Pets-Reels - Main Pipeline Agent
Downloads pet videos from Douyin and edits them into 1080x1920 reels
with Chinese headlines, yellow border overlay, and Nvidia API captions.
"""

import os
import sys
import logging
import json
from pathlib import Path

from src.agent_1_downloader import download_pet_videos
from src.agent_2_editor import edit_video
from src.common.limits import check_daily_limits, increment_counter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---- configuration ----
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "workspace"))
VIDEOS_DIR = WORKSPACE / "videos"
EDITED_DIR = WORKSPACE / "edited"
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
    EDITED_DIR.mkdir(parents=True, exist_ok=True)


def run_pipeline():
    logger.info("=== Facebook-Douyin-Pets-Reels Pipeline Start ===")
    ensure_dirs()
    state = load_state()

    # Step 0: check daily limits
    if not check_daily_limits():
        logger.warning("Daily limit reached. Skipping this run.")
        return

    # Step 1: download videos from Douyin
    logger.info("Step 1: Downloading pet videos from Douyin...")
    downloaded = download_pet_videos(
        output_dir=str(VIDEOS_DIR),
        already_done=state.get("downloaded", []),
    )
    if not downloaded:
        logger.warning("No new videos downloaded. Pipeline ending.")
        return

    # Step 2: edit each video
    logger.info("Step 2: Editing videos (overlay + headline)...")
    edited_files = []
    for video_path in downloaded:
        try:
            result = edit_video(
                input_path=video_path,
                output_dir=str(EDITED_DIR),
            )
            if result:
                edited_files.append(result)
                increment_counter()
        except Exception as exc:
            logger.error("Error editing %s: %s", video_path, exc)

    # Step 3: summary
    logger.info("Pipeline complete. Edited %d / %d videos.", len(edited_files), len(downloaded))
    logger.info("Edited videos saved to: %s", EDITED_DIR)

    # update state
    state["downloaded"] = list(set(state.get("downloaded", []) + downloaded))
    state["edited"] = list(set(state.get("edited", []) + edited_files))
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
