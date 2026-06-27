"""
Agent 1: Douyin Pet Video Downloader
Scrapes Douyin (douyin.com/jingxuan) for cute pet videos using Playwright.
Searches for keywords: 萌宠, 猫, 狗, 熊猫, 宠物
"""

import os
import re
import time
import logging
import hashlib
from pathlib import Path
from typing import List

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# Chinese keywords for pet videos on Douyin
PET_KEYWORDS = ["萌宠", "猫", "狗", "熊猫", "宠物"]

# Douyin pages to scrape
DOUYIN_JINGXUAN_URL = "https://www.douyin.com/jingxuan"

# Playwright config
HEADLESS = os.environ.get("HEADLESS", "1") == "1"
MAX_VIDEOS_PER_KEYWORD = int(os.environ.get("MAX_VIDEOS_PER_KEYWORD", "3"))


def _hash_video_id(url: str) -> str:
    """Generate a short hash from a video URL to use as filename."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _extract_video_url(page, item) -> str | None:
    """Try to extract a direct video URL from a Douyin feed item."""
    try:
        # Look for video element src
        video_el = item.query_selector("video")
        if video_el:
            src = video_el.get_attribute("src")
            if src and src.startswith("http"):
                return src

        # Try data attributes or links
        link = item.query_selector("a[href*='/video/']")
        if link:
            href = link.get_attribute("href")
            if href:
                return href
    except Exception as exc:
        logger.debug("Error extracting video URL: %s", exc)
    return None


def _scrape_pet_videos(page, keyword: str) -> List[str]:
    """Navigate to Douyin search for a keyword and collect video URLs."""
    video_urls: List[str] = []
    search_url = f"https://www.douyin.com/search/{keyword}"

    logger.info("Searching Douyin for keyword: %s", keyword)
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)  # let dynamic content load

        # Scroll down a few times to load more content
        for _ in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

        # Collect video links
        items = page.query_selector_all('a[href*="/video/"]')
        for item in items:
            href = item.get_attribute("href")
            if href and href not in video_urls:
                full_url = href if href.startswith("http") else f"https://www.douyin.com{href}"
                video_urls.append(full_url)
                if len(video_urls) >= MAX_VIDEOS_PER_KEYWORD:
                    break

    except Exception as exc:
        logger.error("Error scraping keyword '%s': %s", keyword, exc)

    logger.info("Found %d video URLs for keyword '%s'", len(video_urls), keyword)
    return video_urls


def _download_video(page, video_url: str, output_dir: str) -> str | None:
    """Download a single video from Douyin and save to output_dir."""
    try:
        page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Try to find the video source
        video_el = page.query_selector("video")
        if not video_el:
            logger.warning("No video element found at %s", video_url)
            return None

        src = video_el.get_attribute("src")
        if not src:
            # Try source elements
            source_el = page.query_selector("video source")
            if source_el:
                src = source_el.get_attribute("src")

        if not src:
            logger.warning("No video source found at %s", video_url)
            return None

        # Generate filename
        vid_hash = _hash_video_id(video_url)
        filename = f"douyin_pet_{vid_hash}.mp4"
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            logger.info("Already downloaded: %s", filepath)
            return filepath

        # Download using requests through page context
        logger.info("Downloading video: %s -> %s", video_url, filepath)
        page.evaluate(f"""
            async () => {{
                const resp = await fetch('{src}');
                const blob = await resp.blob();
                const arrayBuffer = await blob.arrayBuffer();
                const uint8Array = new Uint8Array(arrayBuffer);
                // Store to window for retrieval
                window._videoData = Array.from(uint8Array);
            }}
        """)

        video_data = page.evaluate("window._videoData")
        if video_data:
            with open(filepath, "wb") as f:
                f.write(bytes(video_data))
            file_size = os.path.getsize(filepath)
            if file_size < 10000:  # skip tiny/empty files
                logger.warning("File too small (%d bytes), skipping: %s", file_size, filepath)
                os.remove(filepath)
                return None
            logger.info("Downloaded %d bytes -> %s", file_size, filepath)
            return filepath
        else:
            logger.warning("Failed to retrieve video data for %s", video_url)
            return None

    except Exception as exc:
        logger.error("Error downloading %s: %s", video_url, exc)
        return None


def download_pet_videos(
    output_dir: str = "workspace/videos",
    already_done: List[str] | None = None,
) -> List[str]:
    """
    Main download function.
    Scrapes Douyin for pet videos and saves them to output_dir.
    Returns list of downloaded file paths.
    """
    already_done = already_done or []
    downloaded: List[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS == "1",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        all_video_urls: List[str] = []

        for keyword in PET_KEYWORDS:
            urls = _scrape_pet_videos(page, keyword)
            all_video_urls.extend(urls)
            time.sleep(2)  # polite delay between searches

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in all_video_urls:
            if url not in seen and url not in already_done:
                seen.add(url)
                unique_urls.append(url)

        logger.info("Total unique new video URLs to download: %d", len(unique_urls))

        for url in unique_urls[:MAX_VIDEOS_PER_KEYWORD * len(PET_KEYWORDS)]:
            result = _download_video(page, url, output_dir)
            if result:
                downloaded.append(result)
            time.sleep(1)  # polite delay

        browser.close()

    logger.info("Downloaded %d videos total.", len(downloaded))
    return downloaded


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = download_pet_videos()
    print(f"Downloaded {len(results)} videos:")
    for r in results:
        print(f"  - {r}")
