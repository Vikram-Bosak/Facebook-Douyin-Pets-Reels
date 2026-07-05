#!/usr/bin/env python3
"""
run_pipeline.py - Single video pipeline
Called by scheduler.py with a video URL.
Downloads → Edits → Saves output as output_dubbed_reel.mp4
"""

import os
import sys
import shutil
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger('run_pipeline')
    logging.basicConfig(level=logging.INFO)


def run_single_video_pipeline(video_path):
    """Process a single video: edit and output."""
    logger.info(f"Processing video: {video_path}")

    # Import editor
    try:
        from agent_2_editor import process_video
    except ImportError:
        from src.agent_2_editor import process_video

    video_data = {
        "id": os.path.splitext(os.path.basename(video_path))[0],
        "title": os.path.basename(video_path),
        "local_path": video_path,
    }

    result = process_video(video_data)

    if result.get('editing_status') == 'Success' and result.get('edited_path'):
        final_output = "output_dubbed_reel.mp4"
        shutil.copy2(result['edited_path'], final_output)

        print("\n" + "="*50)
        print("SUCCESS: Video downloaded, translated, and edited!")
        print(f"Final Video: {os.path.abspath(final_output)}")
        print("="*50 + "\n")
        return True
    else:
        logger.error("Failed to process video.")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_pipeline.py <video_url_or_path>")
        sys.exit(1)

    source = sys.argv[1]

    # If it's a URL, try to download first
    if source.startswith("http"):
        logger.info(f"Downloading from URL: {source}")
        try:
            from agent_1_downloader import download_pet_videos
        except ImportError:
            from src.agent_1_downloader import download_pet_videos

        os.makedirs("workspace/videos", exist_ok=True)
        downloaded = download_pet_videos(output_dir="workspace/videos")
        if not downloaded:
            logger.error("Download failed")
            sys.exit(1)
        video_path = downloaded[0]
    else:
        video_path = source

    if not os.path.exists(video_path):
        logger.error(f"Video not found: {video_path}")
        sys.exit(1)

    success = run_single_video_pipeline(video_path)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
