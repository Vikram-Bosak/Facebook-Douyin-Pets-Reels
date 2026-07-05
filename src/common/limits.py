import os
import json
from datetime import datetime

LIMITS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp", "daily_limits.json")

MAX_DOWNLOADS = 5
MAX_EDITS = 5
MAX_UPLOADS = 5

def _load_limits():
    today = datetime.utcnow().date().isoformat()
    if os.path.exists(LIMITS_FILE):
        try:
            with open(LIMITS_FILE, "r") as f:
                data = json.load(f)
                if data.get("date") == today:
                    return data
        except Exception as e:
            print(f"Error loading limits: {e}")
            pass
            
    # Reset limits for today
    return {
        "date": today,
        "downloads": 0,
        "edits": 0,
        "uploads": 0
    }

def _save_limits(data):
    os.makedirs(os.path.dirname(LIMITS_FILE), exist_ok=True)
    try:
        with open(LIMITS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving limits: {e}")

# Downloader API
def can_download() -> bool:
    data = _load_limits()
    return data.get("downloads", 0) < MAX_DOWNLOADS

def increment_download():
    data = _load_limits()
    data["downloads"] = data.get("downloads", 0) + 1
    _save_limits(data)
    print(f"Daily Downloads count updated: {data['downloads']}/{MAX_DOWNLOADS}")

# Editor API
def can_edit() -> bool:
    data = _load_limits()
    return data.get("edits", 0) < MAX_EDITS

def increment_edit():
    data = _load_limits()
    data["edits"] = data.get("edits", 0) + 1
    _save_limits(data)
    print(f"Daily Edits count updated: {data['edits']}/{MAX_EDITS}")

# Uploader API
def can_upload() -> bool:
    data = _load_limits()
    return data.get("uploads", 0) < MAX_UPLOADS

def increment_upload():
    data = _load_limits()
    data["uploads"] = data.get("uploads", 0) + 1
    _save_limits(data)
    print(f"Daily Uploads count updated: {data['uploads']}/{MAX_UPLOADS}")
