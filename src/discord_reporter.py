import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

def send_discord_message(message: str) -> None:
    """
    Sends a message to Discord using a Webhook.
    """
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("Discord configuration (DISCORD_WEBHOOK_URL) is missing. Skipping Discord notification.")
        # Fallback print to terminal logs
        print(message)
        return

    # Clean HTML tags from message since Discord uses Markdown instead of HTML
    clean_message = message.replace("<b>", "**").replace("</b>", "**")
    clean_message = clean_message.replace("🔄", "🔄").replace("✅", "✅").replace("❌", "❌")
    
    payload = {
        "content": clean_message
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Discord message: {e}")

def get_run_details() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "Local")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"**Run ID:** {run_id}\n**Time:** {current_time}"

def report_progress(step: str, detail: str = ""):
    """Sends a real-time progress update to Discord."""
    msg = f"🔄 **Pipeline Progress**\n**Step:** {step}\n"
    if detail:
        msg += f"**Detail:** {detail}\n"
    msg += f"\n{get_run_details()}"
    send_discord_message(msg)

def report_success(filename: str, title: str, fb_url: str, remaining_queue: int, media_type: str = "reel"):
    """Reports a successful upload to Discord."""
    msg = (
        f"✅ **Upload Successful!**\n\n"
        f"🎬 **File:** {filename}\n"
        f"🏷️ **Title:** {title}\n"
        f"📦 **Type:** {media_type.upper()}\n"
        f"🔗 **Link:** {fb_url}\n"
        f"📋 **Remaining in Queue:** {remaining_queue}\n\n"
        f"{get_run_details()}"
    )
    send_discord_message(msg)

def report_failure(filename: str, error_msg: str, remaining_queue: int, media_type: str = "reel"):
    """Reports a pipeline failure to Discord."""
    msg = (
        f"❌ **Pipeline Failure!**\n\n"
        f"🎬 **File:** {filename}\n"
        f"📦 **Type:** {media_type.upper() if filename != 'System Health Check' else 'N/A'}\n"
        f"⚠️ **Error:** {error_msg}\n"
        f"📋 **Remaining in Queue:** {remaining_queue}\n\n"
        f"{get_run_details()}"
    )
    send_discord_message(msg)
