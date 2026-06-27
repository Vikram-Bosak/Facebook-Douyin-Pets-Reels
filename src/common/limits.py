"""
Daily processing limits to stay under API quotas and avoid overuse.
"""

import os
import json
from pathlib import Path

MAX_DOWNLOADS_PER_DAY = int(os.environ.get("MAX_DOWNLOADS", "10"))
MAX_EDITS_PER_DAY = int(os.environ.get("MAX_EDITS", "10"))
STATE_DIR = Path(os.environ.get("WORKSPACE_DIR", "workspace"))
COUNTER_FILE = STATE_DIR / "daily_counter.json"


def _load_counter() -> dict:
    if COUNTER_FILE.exists():
        return json.loads(COUNTER_FILE.read_text())
    return {"count": 0}


def _save_counter(data: dict):
    COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    COUNTER_FILE.write_text(json.dumps(data, indent=2))


def get_today_count() -> int:
    data = _load_counter()
    return data.get("count", 0)


def check_daily_limits() -> bool:
    """Return True if we are still under the daily limit."""
    return get_today_count() < MAX_EDITS_PER_DAY


def increment_counter():
    data = _load_counter()
    data["count"] = data.get("count", 0) + 1
    _save_counter(data)


def reset_counter():
    _save_counter({"count": 0})
