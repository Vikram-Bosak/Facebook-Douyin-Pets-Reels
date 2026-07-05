import os
import logging

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None
    logger.warning("requests library not installed. Telegram notifications disabled.")

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
    TELEGRAM_REPORT_CHAT_ID = os.environ.get("TELEGRAM_REPORT_CHAT_ID", TELEGRAM_CHAT_ID)
except Exception:
    TELEGRAM_BOT_TOKEN = None
    TELEGRAM_CHAT_ID = None
    TELEGRAM_REPORT_CHAT_ID = None


def _is_configured():
    """Check if Telegram is configured and requests is available."""
    if requests is None:
        return False
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_REPORT_CHAT_ID:
        return False
    return True


def send_message(message: str, chat_id: str = None) -> None:
    if not _is_configured():
        logger.info("Telegram not configured. Message: %s", message[:100])
        return
    target_chat = chat_id or TELEGRAM_REPORT_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get("ok") and "result" in result:
            return result["result"].get("message_id")
    except Exception as e:
        logger.warning("Failed to send Telegram message: %s", e)
    return None


def edit_message_text(message_id: int, new_text: str, chat_id: str = None) -> bool:
    if not _is_configured():
        return False
    target_chat = chat_id or TELEGRAM_REPORT_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": target_chat,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Failed to edit Telegram message text: %s", e)
        return False


def send_video(video_path: str, caption: str = "", chat_id: str = None):
    if not _is_configured():
        logger.info("Telegram not configured. Cannot send video: %s", video_path)
        return None, None

    if not os.path.exists(video_path):
        logger.warning("Video file %s not found.", video_path)
        return None, None

    target_chat = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    data = {
        "chat_id": target_chat,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        with open(video_path, 'rb') as video_file:
            files = {'video': video_file}
            response = requests.post(url, data=data, files=files, timeout=60)
            response.raise_for_status()
            result = response.json()
            if result.get("ok") and "result" in result:
                msg_id = result["result"].get("message_id")
                video_obj = result["result"].get("video", {})
                file_id = video_obj.get("file_id")
                return msg_id, file_id
    except Exception as e:
        logger.warning("Failed to send Telegram video: %s", e)
    return None, None


def download_video_from_telegram(file_id: str, output_path: str) -> bool:
    if not _is_configured():
        logger.info("Telegram not configured. Cannot download video.")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("ok") and "result" in result:
            file_path = result["result"].get("file_path")
            if not file_path:
                return False
            download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            with requests.get(download_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
    except Exception as e:
        logger.warning("Failed to download video from Telegram: %s", e)
    return False


def edit_message_caption(message_id: int, new_caption: str, chat_id: str = None) -> bool:
    if not _is_configured():
        return False
    target_chat = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageCaption"
    payload = {
        "chat_id": target_chat,
        "message_id": message_id,
        "caption": new_caption,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Failed to edit Telegram message caption: %s", e)
        return False


def get_run_details() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "Unknown")
    workflow = os.environ.get("GITHUB_WORKFLOW", "Unknown")
    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"<b>Run ID:</b> {run_id}\n<b>Workflow:</b> {workflow}\n<b>Time:</b> {current_time}"


def report_download_start():
    msg = f"🟢 <b>Chinese Reel Download Started</b>\n{get_run_details()}"
    send_message(msg)


def report_download_complete(source_url: str):
    msg = f"✅ <b>Chinese Reel Download Completed</b>\n<b>Source:</b> {source_url}\n{get_run_details()}"
    send_message(msg)


def report_edit_start():
    msg = f"🟡 <b>Video Editing Started</b>\n{get_run_details()}"
    send_message(msg)


def report_edit_complete():
    msg = f"✅ <b>Video Editing Completed</b>\n{get_run_details()}"
    send_message(msg)


def report_upload_complete(platform: str, url: str, title: str, description: str):
    msg = (
        f"🚀 <b>{platform} Upload Completed</b>\n"
        f"<b>URL:</b> {url}\n"
        f"<b>Title:</b> {title}\n"
        f"<b>Description:</b> {description}\n"
        f"{get_run_details()}"
    )
    send_message(msg)


def report_final_summary(summary_data: dict):
    job_status = summary_data.get('job_status', 'Success')
    fb_url = summary_data.get('fb_url', 'N/A')
    yt_url = summary_data.get('yt_url', 'N/A')

    fb_err = summary_data.get('fb_err', 'Unknown Error')
    yt_err = summary_data.get('yt_err', 'Unknown Error')

    fb_status = "Success" if fb_url not in ["Failed", "N/A"] else f"Failed ({fb_err})"
    yt_status = "Success" if yt_url not in ["Failed", "N/A"] else f"Failed ({yt_err})"

    title = summary_data.get('title', 'Automated Chinese Reel')
    description = summary_data.get('description', '')
    original_file = summary_data.get('original_file', 'unknown_video.mp4')

    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repo_name = os.environ.get("GITHUB_REPOSITORY", "Vikram-Bosak/Facebook-Viral-Chinese-Reels")
    workflow_url = f"https://github.com/{repo_name}/actions/runs/{run_id}" if run_id else f"https://github.com/{repo_name}/actions"
    repo_url = f"https://github.com/{repo_name}"

    msg = (
        f"✅ <b>Upload Successfully Completed</b>\n"
        f"🎬 <b>Video Name:</b>\n"
        f"{original_file}\n\n"
        f"✅ DOWNLOADED\n"
        f"✏️ EDITED\n"
        f"📅 SCHEDULED\n"
        f"🚀 UPLOADED\n"
        f"✔️ COMPLETED\n\n"
        f"📤 <b>Facebook Upload Status:</b> {fb_status}\n"
        f"📤 <b>YouTube Upload Status:</b> {yt_status}\n\n"
        f"🏷️ <b>SEO Title:</b>\n"
        f"{title}\n\n"
        f"📝 <b>Description:</b>\n"
        f"{description}\n\n"
        f"Original Title: {original_file}\n"
        f"Source: {original_file}\n\n"
        f"🔗 <b>Facebook Reel URL:</b>\n"
        f"{fb_url}\n\n"
        f"▶️ <b>YouTube Video URL:</b>\n"
        f"{yt_url}\n\n"
        f"📦 <b>GitHub Repository:</b>\n"
        f"{repo_url}\n\n"
        f"📄 <b>Workflow Run:</b>\n"
        f"{workflow_url}"
    )
    send_message(msg)
