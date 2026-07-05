"""
Scheduler: Master Orchestrator for Pet Reels Pipeline
Runs the full pipeline: Scan → Download → Translate/Edit → Upload → Report
"""

import os
import sys
import json
import time
import subprocess
import random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add src/ to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger('scheduler')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from agent_1_downloader import run_downloader, save_to_history

try:
    from discord_reporter import report_success, report_failure, report_progress
except ImportError:
    def report_progress(a, b=""): logger.info(f"Progress: {a} - {b}")
    def report_success(a, b, c, d): logger.info(f"Success: {a}")
    def report_failure(a, b, c): logger.error(f"Failure: {a} - {b}")

HISTORY_LOG_FILE = 'workspace/processed_history.json'
QUEUE_FILE = 'workspace/queue.json'


def load_processed_history():
    if os.path.exists(HISTORY_LOG_FILE):
        try:
            with open(HISTORY_LOG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_processed_history(history):
    os.makedirs(os.path.dirname(HISTORY_LOG_FILE), exist_ok=True)
    with open(HISTORY_LOG_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def clean_and_count_recent_uploads():
    history = load_processed_history()
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(hours=24)

    recent_uploads = []
    for item in history:
        try:
            upload_time = datetime.fromisoformat(item['timestamp'])
            if upload_time >= one_day_ago:
                recent_uploads.append(item)
        except Exception:
            pass

    save_processed_history(recent_uploads)
    return len(recent_uploads)


def update_queue_status(video_id, status):
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, 'r') as f:
                queue = json.load(f)
            for item in queue:
                if item['id'] == video_id:
                    item['status'] = status
            with open(QUEUE_FILE, 'w') as f:
                json.dump(queue, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating queue status: {e}")


def main():
    load_dotenv()
    logger.info("=== Pet Reels Pipeline: Automated Scheduler Cycle ===")

    # 1. Clean history and check quota
    recent_count = clean_and_count_recent_uploads()
    max_daily = int(os.environ.get('MAX_DAILY_UPLOADS', 6))
    logger.info(f"Processed videos in last 24 hours: {recent_count}/{max_daily}")

    if recent_count >= max_daily:
        logger.info(f"Daily quota of {max_daily} videos reached. Skipping.")
        return

    # 2. Run scan to populate queue
    logger.info("Scanning for new pet videos...")
    next_video = run_downloader()

    if not next_video:
        logger.info("No new pet videos available.")
        return

    video_id = next_video['id']
    source_url = next_video['source_url']
    title = next_video['title']

    logger.info(f"Processing video ID {video_id}: {title}")
    report_progress("Starting Processing Pipeline", f"Video ID: {video_id}\nTitle: {title}")

    # Update status to PROCESSING
    update_queue_status(video_id, "PROCESSING")

    # 3. Execute download, translation, editing
    try:
        python_exe = sys.executable
        cmd = [python_exe, 'run_pipeline.py', source_url]
        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            error_msg = f"Pipeline failed (code {result.returncode}): {result.stderr}"
            logger.error(error_msg)
            report_failure("output_dubbed_reel.mp4", error_msg, max_daily - recent_count - 1)
            update_queue_status(video_id, "FAILED")
            return

        logger.info("Translation and rendering completed successfully!")

        # Random delay (1-15 min) for human-like upload behavior
        random_delay = random.randint(1, 900)
        logger.info(f"Random jitter delay: {random_delay}s (~{random_delay/60:.1f} min)")
        time.sleep(random_delay)

        # Write state for agent_3_uploader
        os.makedirs("workspace", exist_ok=True)
        final_video_path = os.path.abspath("output_dubbed_reel.mp4")

        video_data_state = {
            "id": video_id,
            "title": title,
            "seo_title": title,
            "source_url": source_url,
            "local_path": os.path.abspath("workspace/raw_video.mp4"),
            "edited_path": final_video_path,
            "editing_status": "Success"
        }
        with open("workspace/video_data.json", "w") as f:
            json.dump(video_data_state, f, indent=2)

        report_data = {
            "video_name": title,
            "download_status": "Success",
            "editing_status": "Success",
            "upload_status": "PENDING",
            "seo_title": title,
            "description": "N/A",
            "facebook_url": "N/A",
            "youtube_url": "N/A",
            "source_url": source_url
        }
        with open("workspace/report.json", "w") as f:
            json.dump(report_data, f, indent=2)

        # 4. Upload
        uploader_script = os.path.join(os.path.dirname(__file__), 'agent_3_uploader.py')
        if os.path.exists(uploader_script):
            try:
                logger.info("Triggering Agent 3: Facebook + YouTube Uploader...")
                upload_res = subprocess.run(
                    [python_exe, uploader_script],
                    capture_output=True, text=True, timeout=300
                )
                logger.info(f"Agent 3 stdout: {upload_res.stdout}")
                if upload_res.stderr:
                    logger.warning(f"Agent 3 stderr: {upload_res.stderr}")
            except Exception as e:
                logger.error(f"Error running uploader: {e}")

        # 5. Save to history
        save_to_history(video_id)
        update_queue_status(video_id, "COMPLETED")

        history = load_processed_history()
        history.append({
            "id": video_id,
            "title": title,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        save_processed_history(history)

        # 6. Run Reporter
        reporter_script = os.path.join(os.path.dirname(__file__), 'agent_4_reporter.py')
        if os.path.exists(reporter_script):
            try:
                logger.info("Triggering Agent 4: Reporter...")
                subprocess.run(
                    [python_exe, reporter_script],
                    capture_output=True, text=True, timeout=120
                )
            except Exception as e:
                logger.error(f"Error running reporter: {e}")

        logger.info(f"Video {video_id} processed, uploaded, and logged.")

    except Exception as e:
        error_msg = f"Unexpected error during scheduling: {e}"
        logger.error(error_msg)
        report_failure("output_dubbed_reel.mp4", error_msg, max(0, max_daily - recent_count - 1))
        update_queue_status(video_id, "FAILED")


if __name__ == "__main__":
    main()
