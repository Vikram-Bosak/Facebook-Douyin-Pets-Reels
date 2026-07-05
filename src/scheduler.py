"""
Scheduler: Master Orchestrator for Pet Reels Pipeline
Runs the full pipeline: Scan → Download → Translate/Edit → Upload → Report
"""

import os
import sys
import json
import time
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

    # 2. Run the full pipeline via main_agent (download + edit + upload + report)
    try:
        # Import and run the full pipeline from main_agent
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        from main_agent import run_pipeline

        report_progress("Starting Full Pipeline", "Download + Edit + Upload + Report")
        run_pipeline()

        logger.info("Full pipeline completed successfully.")

    except Exception as e:
        error_msg = f"Unexpected error during scheduling: {e}"
        logger.error(error_msg)
        report_failure("pipeline", error_msg, max(0, max_daily - recent_count - 1))


if __name__ == "__main__":
    main()
