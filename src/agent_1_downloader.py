"""
Agent 1: Bilibili Pet Video Downloader
Uses Bilibili search API + playurl API to find and download pet videos.
No cookies, no playwright, no yt-dlp - works on GitHub Actions.

Search keywords: 萌宠, 猫, 狗, 熊猫, 宠物, 柴犬, 布偶猫
"""

import os
import re
import json
import time
import hashlib
import logging
import random
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bilibili pet keywords
# ---------------------------------------------------------------------------
PET_KEYWORDS = ["猫咪搞笑 竖屏", "狗狗搞笑 竖屏", "猫 搞笑 竖屏", "狗 搞笑 竖屏", "猫咪日常 竖屏", "狗狗日常 竖屏", "宠物搞笑 竖屏", "布偶猫 竖屏", "柴犬 竖屏"]

# ---------------------------------------------------------------------------
# Bilibili API endpoints
# ---------------------------------------------------------------------------
BILIBILI_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/all/v2"
BILIBILI_VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
BILIBILI_PLAYURL_URL = "https://api.bilibili.com/x/player/playurl"

# ---------------------------------------------------------------------------
# HTTP config
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
}

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------
MAX_VIDEOS_PER_KEYWORD = int(os.environ.get("MAX_VIDEOS_PER_KEYWORD", "3"))
MAX_VIDEOS_TOTAL = int(os.environ.get("MAX_DOWNLOADS", "10"))


def _hash_video_id(bvid: str) -> str:
    """Generate a short hash from a video BV ID."""
    return hashlib.md5(bvid.encode()).hexdigest()[:12]


# ===== SEARCH ===============================================================

def _search_bilibili(keyword: str, page: int = 1) -> List[Dict[str, Any]]:
    """
    Search Bilibili for videos matching keyword.
    Returns list of dicts with bvid, title, url, etc.
    """
    params = {
        "keyword": keyword,
        "page": str(page),
        "search_type": "video",
        "order": "totalrank",
    }

    try:
        resp = requests.get(BILIBILI_SEARCH_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            logger.warning(
                "Bilibili search API returned code %d: %s",
                data.get("code"),
                data.get("message", "unknown error"),
            )
            return []

        result = data.get("data", {})
        sections = result.get("result", [])

        videos: List[Dict[str, Any]] = []
        for section in sections:
            if section.get("result_type") == "video":
                for item in section.get("data", []):
                    bvid = item.get("bvid", "")
                    if not bvid:
                        continue
                    title = re.sub(r"<[^>]+>", "", item.get("title", ""))
                    videos.append({
                        "bvid": bvid,
                        "title": title,
                        "url": f"https://www.bilibili.com/video/{bvid}",
                        "duration": item.get("duration", ""),
                        "author": item.get("author", ""),
                    })

        logger.info("Bilibili search '%s': found %d videos", keyword, len(videos))
        return videos

    except Exception as exc:
        logger.error("Bilibili search failed for '%s': %s", keyword, exc)
        return []


# ===== DOWNLOAD VIA PLAYURL API =============================================

def _get_video_info(bvid: str) -> Optional[Dict[str, Any]]:
    """Get video info including dimensions from the view API."""
    try:
        resp = requests.get(
            BILIBILI_VIEW_URL,
            params={"bvid": bvid},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            logger.warning("view API error for %s: %s", bvid, data.get("message"))
            return None

        video_data = data.get("data", {})
        cid = video_data.get("cid")
        if not cid:
            pages = video_data.get("pages", [])
            if pages:
                cid = pages[0].get("cid")

        if not cid:
            logger.warning("No CID found for %s", bvid)
            return None

        # Get dimensions from stat or other fields
        width = video_data.get("width", 0)
        height = video_data.get("height", 0)

        # Try to get from dimension field
        dimension = video_data.get("dimension", {})
        if dimension:
            width = dimension.get("width", width)
            height = dimension.get("height", height)

        return {
            "cid": cid,
            "width": width,
            "height": height,
            "title": video_data.get("title", ""),
            "duration": video_data.get("duration", 0),
        }

    except Exception as exc:
        logger.error("Failed to get video info for %s: %s", bvid, exc)
        return None


def _get_cid(bvid: str) -> Optional[int]:
    """Get CID for a video via the view API."""
    info = _get_video_info(bvid)
    return info["cid"] if info else None


def _get_stream_url(bvid: str, cid: int) -> Optional[str]:
    """Get a direct download URL from the playurl API (qn=16 = 360p, no login needed)."""
    try:
        params = {
            "bvid": bvid,
            "cid": cid,
            "qn": 16,          # 360p — available without login
            "fnval": 1,        # return DURL format (single mp4 URL)
            "fourk": 0,
        }
        resp = requests.get(
            BILIBILI_PLAYURL_URL,
            params=params,
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            logger.warning("playurl API error for %s: %s", bvid, data.get("message"))
            return None

        # fnval=1 → DURL format
        durl = data.get("data", {}).get("durl", [])
        if durl:
            url = durl[0].get("url")
            if url:
                logger.info("Got stream URL for %s (size ~%d bytes)",
                            bvid, durl[0].get("size", 0))
                return url

        # Fallback: try DASH format (fnval=16) → pick first video stream
        dash = data.get("data", {}).get("dash")
        if dash:
            videos = dash.get("video", [])
            if videos:
                # pick lowest resolution for speed
                streams = sorted(videos, key=lambda v: v.get("bandwidth", 999999))
                stream_url = streams[0].get("baseUrl") or streams[0].get("base_url")
                if stream_url:
                    logger.info("Got DASH stream URL for %s", bvid)
                    return stream_url

        logger.warning("No stream URL in playurl response for %s", bvid)
        return None

    except Exception as exc:
        logger.error("Failed to get stream URL for %s: %s", bvid, exc)
        return None


def _download_stream(url: str, output_path: str, max_retries: int = 3) -> Optional[str]:
    """Download a video stream with retry + resume support."""
    for attempt in range(1, max_retries + 1):
        dl_headers = {
            **HEADERS,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
        }

        # Resume support: if partial file exists, continue from where we left off
        existing_size = 0
        if os.path.exists(output_path):
            existing_size = os.path.getsize(output_path)
            if existing_size > 0:
                dl_headers["Range"] = f"bytes={existing_size}-"
                logger.info("Resuming download from %d bytes (attempt %d/%d)",
                           existing_size, attempt, max_retries)

        try:
            resp = requests.get(url, headers=dl_headers, stream=True, timeout=180)
            resp.raise_for_status()

            # If resuming, server should return 206 Partial Content
            mode = "ab" if existing_size > 0 and resp.status_code == 206 else "wb"
            if mode == "wb":
                existing_size = 0  # Reset if starting fresh

            total = existing_size
            stall_count = 0
            last_progress = time.time()

            with open(output_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=128 * 1024):  # 128KB chunks
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
                        last_progress = time.time()
                        stall_count = 0
                    else:
                        stall_count += 1
                        # If no data for 30 seconds, consider stalled
                        if time.time() - last_progress > 30:
                            logger.warning("Download stalled at %d bytes, retrying...", total)
                            break

            if total < 10_000:
                logger.warning("Downloaded file too small (%d bytes), removing", total)
                if os.path.exists(output_path):
                    os.remove(output_path)
                return None

            logger.info("Downloaded %d bytes → %s (attempt %d)", total, output_path, attempt)
            return output_path

        except Exception as exc:
            logger.error("Stream download attempt %d/%d failed: %s", attempt, max_retries, exc)
            # Don't remove partial file — next attempt will resume
            if attempt < max_retries:
                wait = attempt * 5
                logger.info("Waiting %ds before retry...", wait)
                time.sleep(wait)

    # All retries failed — clean up
    logger.error("All %d download attempts failed for %s", max_retries, output_path)
    if os.path.exists(output_path):
        os.remove(output_path)
    return None


def _download_video_bilibili(
    bvid: str,
    output_dir: str,
    filename_prefix: str = "bilibili_pet",
) -> Optional[str]:
    """
    Full download pipeline for a single Bilibili video:
      1. Get video info (dimensions, CID)
      2. Filter: only portrait/vertical videos (9:16 or taller)
      3. Get stream URL via playurl API
      4. Download with requests
    Returns the local file path or None.
    """
    vid_hash = _hash_video_id(bvid)

    # Check if already downloaded
    for ext in ("mp4", "flv", "mkv", "webm"):
        existing = os.path.join(output_dir, f"{filename_prefix}_{vid_hash}.{ext}")
        if os.path.exists(existing) and os.path.getsize(existing) > 10_000:
            logger.info("Already downloaded: %s", existing)
            return existing

    # Step 1: get video info (CID + dimensions)
    info = _get_video_info(bvid)
    if info is None:
        return None

    cid = info["cid"]
    width = info.get("width", 0)
    height = info.get("height", 0)

    # Step 2: PORTRAIT FILTER — only download vertical/portrait videos
    if width > 0 and height > 0:
        ratio = width / height
        if ratio > 0.8:  # Landscape or square — skip
            logger.info("Skipping LANDSCAPE video %s (%dx%d, ratio %.2f) — need portrait 9:16",
                       bvid, width, height, ratio)
            return None
        logger.info("Portrait video confirmed %s (%dx%d, ratio %.2f) ✓",
                    bvid, width, height, ratio)
    else:
        logger.info("Dimensions unknown for %s — proceeding with download", bvid)

    time.sleep(0.5)

    # Step 2: get stream URL
    stream_url = _get_stream_url(bvid, cid)
    if stream_url is None:
        return None

    time.sleep(0.5)

    # Step 3: download
    # Try to guess extension from URL
    ext = "mp4"
    url_lower = stream_url.lower()
    if ".flv" in url_lower:
        ext = "flv"
    output_path = os.path.join(output_dir, f"{filename_prefix}_{vid_hash}.{ext}")

    result = _download_stream(stream_url, output_path)
    return result


# ===== MAIN PUBLIC FUNCTION =================================================

def download_pet_videos(
    output_dir: str = "workspace/videos",
    already_done: List[str] | None = None,
) -> List[str]:
    """
    Main download function.
    Searches Bilibili for pet videos and downloads up to MAX_VIDEOS_TOTAL.
    Returns list of downloaded file paths.
    """
    already_done = already_done or []
    downloaded: List[str] = []
    os.makedirs(output_dir, exist_ok=True)

    # Collect candidate videos
    all_candidates: List[Dict[str, Any]] = []

    keywords = PET_KEYWORDS.copy()
    random.shuffle(keywords)

    for keyword in keywords:
        videos = _search_bilibili(keyword)
        for v in videos:
            bvid = v["bvid"]
            if bvid not in already_done and v["url"] not in already_done:
                all_candidates.append(v)
            if len(all_candidates) >= MAX_VIDEOS_TOTAL:
                break
        if len(all_candidates) >= MAX_VIDEOS_TOTAL:
            break
        time.sleep(1)

    logger.info("Total unique new videos to download: %d", len(all_candidates))

    # Download videos — try up to 5 candidates per run (some may fail)
    attempts = 0
    max_attempts = min(len(all_candidates), 5)

    for candidate in all_candidates:
        if attempts >= max_attempts or len(downloaded) >= MAX_VIDEOS_TOTAL:
            break
        attempts += 1
        bvid = candidate["bvid"]
        logger.info("Attempting download %d/%d: [%s] %s",
                     attempts, max_attempts, candidate.get("title", "")[:40], bvid)

        result = _download_video_bilibili(bvid, output_dir)
        if result:
            downloaded.append(result)

        time.sleep(1)

    logger.info("Downloaded %d videos total.", len(downloaded))
    return downloaded


# ===== CLI ENTRY POINT ======================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = download_pet_videos()
    print(f"Downloaded {len(results)} videos:")
    for r in results:
        print(f"  - {r}")
