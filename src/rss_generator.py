"""
RSS Generator for Bilibili Pet Videos
Generates an RSS feed of pet video URLs from Bilibili search results.
The RSS feed is written to workspace/rss/feed.xml for the downloader to consume.
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import List, Dict, Any
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

import httpx

logger = logging.getLogger(__name__)

# Bilibili pet keywords
PET_KEYWORDS = ["萌宠", "猫", "狗", "熊猫", "宠物", "柴犬", "布偶猫"]

# Bilibili search API
BILIBILI_SEARCH_URL = "https://api.bilibili.com/x/web-interface/wbi/search/all/v2"

# User-Agent
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

RSS_OUTPUT_DIR = os.environ.get("RSS_OUTPUT_DIR", "workspace/rss")
RSS_FEED_FILE = "feed.xml"


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
        with httpx.Client(headers=HEADERS, timeout=15) as client:
            resp = client.get(BILIBILI_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            logger.warning(
                "Bilibili API returned code %d: %s",
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
                        "description": re.sub(
                            r"<[^>]+>", "", item.get("description", "")
                        ),
                    })

        logger.info(
            "Bilibili RSS search '%s': found %d videos", keyword, len(videos)
        )
        return videos

    except Exception as exc:
        logger.error("Bilibili search failed for '%s': %s", keyword, exc)
        return []


def _build_rss_xml(videos: List[Dict[str, Any]], keyword: str) -> str:
    """Build RSS XML string from list of video dicts."""
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = f"Bilibili Pet Videos - {keyword}"
    SubElement(channel, "link").text = "https://www.bilibili.com"
    SubElement(channel, "description").text = f"Auto-generated RSS feed for pet videos: {keyword}"

    for video in videos:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = video.get("title", "Untitled")
        SubElement(item, "link").text = video.get("url", "")
        SubElement(item, "description").text = video.get("description", "")
        SubElement(item, "guid").text = video.get("bvid", "")
        SubElement(item, "author").text = video.get("author", "")
        if video.get("duration"):
            SubElement(item, "duration").text = video["duration"]

    raw_xml = tostring(rss, encoding="unicode", xml_declaration=False)
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    try:
        pretty = parseString(xml_declaration + raw_xml).toprettyxml(indent="  ")
        # Remove extra xml declaration added by toprettyxml
        lines = pretty.split("\n")
        if lines[0].startswith("<?xml"):
            lines[0] = xml_declaration.strip()
        return "\n".join(lines)
    except Exception:
        return xml_declaration + raw_xml


def generate_rss(
    output_dir: str | None = None,
    keywords: List[str] | None = None,
) -> str:
    """
    Generate RSS feed from Bilibili pet video search results.
    Returns the path to the generated RSS file.
    """
    output_dir = output_dir or RSS_OUTPUT_DIR
    keywords = keywords or PET_KEYWORDS
    os.makedirs(output_dir, exist_ok=True)

    all_videos: List[Dict[str, Any]] = []
    seen_bvids = set()

    for keyword in keywords:
        videos = _search_bilibili(keyword)
        for v in videos:
            bvid = v.get("bvid", "")
            if bvid and bvid not in seen_bvids:
                seen_bvids.add(bvid)
                all_videos.append(v)
        time.sleep(1)  # polite delay

    logger.info("Total unique videos for RSS: %d", len(all_videos))

    if not all_videos:
        logger.warning("No videos found, generating empty RSS feed")

    rss_xml = _build_rss_xml(all_videos, "萌宠合集")
    rss_path = os.path.join(output_dir, RSS_FEED_FILE)
    Path(rss_path).write_text(rss_xml, encoding="utf-8")
    logger.info("RSS feed written to: %s (%d items)", rss_path, len(all_videos))

    return rss_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = generate_rss()
    print(f"RSS feed generated: {path}")
