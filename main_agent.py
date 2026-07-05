#!/usr/bin/env python3
"""
Facebook-Douyin-Pets-Reels - Main Pipeline Agent
Full E2E pipeline: Download → Edit → Upload → Report

This is the primary entry point called by GitHub Actions.
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---- Configuration ----
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "workspace"))
VIDEOS_DIR = WORKSPACE / "videos"
EDITED_DIR = WORKSPACE / "edited"
STATE_FILE = WORKSPACE / "state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"downloaded": [], "uploaded": []}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def ensure_dirs():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    EDITED_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE.mkdir(parents=True, exist_ok=True)


def run_pipeline():
    logger.info("=== Facebook-Douyin-Pets-Reels Pipeline Start ===")
    ensure_dirs()
    state = load_state()

    # ---- Step 1: Download pet videos from Bilibili ----
    logger.info("Step 1/4: Downloading pet videos from Bilibili...")
    try:
        from src.agent_1_downloader import download_pet_videos
        downloaded = download_pet_videos(
            output_dir=str(VIDEOS_DIR),
            already_done=state.get("downloaded", []),
        )
    except ImportError:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        from agent_1_downloader import download_pet_videos
        downloaded = download_pet_videos(
            output_dir=str(VIDEOS_DIR),
            already_done=state.get("downloaded", []),
        )

    if not downloaded:
        logger.warning("No new videos downloaded. Pipeline ending.")
        return

    logger.info(f"Downloaded {len(downloaded)} videos.")
    state["downloaded"] = list(set(state.get("downloaded", []) + [str(v) for v in downloaded]))

    # ---- Step 2: Edit videos (overlay, translate if enabled) ----
    logger.info("Step 2/4: Editing videos...")
    try:
        from src.agent_2_editor import process_video, validate_aspect_ratio
    except ImportError:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        from agent_2_editor import process_video, validate_aspect_ratio

    edited_videos = []
    for video_path in downloaded:
        try:
            if not os.path.exists(video_path):
                logger.warning(f"Video not found: {video_path}")
                continue

            # Check aspect ratio
            if not validate_aspect_ratio(video_path):
                logger.info(f"Skipping {video_path} - not 9:16 aspect ratio")
                continue

            video_data = {
                "id": Path(video_path).stem,
                "title": Path(video_path).stem,
                "local_path": str(video_path),
            }
            result = process_video(video_data)

            if result.get("editing_status") == "Success" and result.get("edited_path"):
                edited_videos.append(result)
                logger.info(f"Edited: {result['edited_path']}")
            else:
                logger.error(f"Editing failed for {video_path}")
        except Exception as e:
            logger.error(f"Error editing video {video_path}: {e}. Skipping to next video.")
            continue

    if not edited_videos:
        logger.warning("No videos were successfully edited.")
        return

    # ---- Step 3: Upload to Facebook + YouTube ----
    logger.info("Step 3/4: Uploading videos...")
    try:
        from src.agent_3_uploader import run_upload
    except ImportError:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        from agent_3_uploader import run_upload

    for video_data in edited_videos:
        try:
            result = run_upload(video_data)
            fb_status = result.get("upload_status", "Failed")
            logger.info(f"Upload result: {fb_status}")

            # Write report for agent_4
            report_data = {
                "video_name": result.get("title", "N/A"),
                "download_status": "Success",
                "editing_status": result.get("editing_status", "N/A"),
                "upload_status": result.get("upload_status", "N/A"),
                "seo_title": result.get("seo_title", "N/A"),
                "description": result.get("description", "N/A"),
                "facebook_url": result.get("fb_url", "N/A"),
                "youtube_url": result.get("yt_url", "N/A"),
                "source_url": result.get("source_url", "N/A"),
            }
            report_path = WORKSPACE / "report.json"
            report_path.write_text(json.dumps(report_data, indent=2))
        except Exception as e:
            logger.error(f"Upload failed for video {video_data.get('title', 'unknown')}: {e}")
            # Write a failure report so reporter can still run
            report_data = {
                "video_name": video_data.get("title", "N/A"),
                "download_status": "Success",
                "editing_status": video_data.get("editing_status", "N/A"),
                "upload_status": "Failed",
                "seo_title": video_data.get("seo_title", "N/A"),
                "description": "N/A",
                "facebook_url": "Failed",
                "youtube_url": "N/A",
                "source_url": video_data.get("source_url", "N/A"),
            }
            report_path = WORKSPACE / "report.json"
            report_path.write_text(json.dumps(report_data, indent=2))

    # ---- Step 4: Report + Cleanup ----
    logger.info("Step 4/4: Reporting and cleanup...")
    try:
        from src.agent_4_reporter import main as run_reporter
    except ImportError:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        from agent_4_reporter import main as run_reporter

    try:
        run_reporter()
    except Exception as e:
        logger.error(f"Reporter failed: {e}")

    # Update state
    try:
        save_state(state)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

    logger.info("=== Pipeline Complete ===")
    logger.info(f"Videos downloaded: {len(downloaded)}")
    logger.info(f"Videos edited: {len(edited_videos)}")


if __name__ == "__main__":
    try:
        run_pipeline()
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        sys.exit(1)
