"""
Agent 3: Facebook + YouTube Uploader
Generates SEO metadata, uploads to Facebook Reels and YouTube Shorts.
"""

import os
import sys
import re
import time
from dotenv import load_dotenv

try:
    from src.facebook_uploader import upload_reel
    from src.youtube_uploader import upload_to_youtube
except ImportError:
    from facebook_uploader import upload_reel
    from youtube_uploader import upload_to_youtube

load_dotenv()


def run_upload(video_data):
    """Main upload agent: SEO generation + Facebook upload + YouTube upload."""
    logger.info("Starting Agent 3: Facebook + YouTube Uploader")

    edited_video_path = video_data.get('edited_path')
    title = video_data.get('title', 'Unknown Video')
    headline = video_data.get('seo_title', '')
    source_url = video_data.get('source_url', '')

    if not edited_video_path or not os.path.exists(edited_video_path):
        logger.error("No edited video found to upload.")
        return video_data

    if video_data.get("editing_status") != "Success":
        logger.error(f"Editing did not succeed (Status: {video_data.get('editing_status')}). Skipping upload.")
        if os.path.exists(edited_video_path):
            os.remove(edited_video_path)
        return video_data

    # Construct Facebook Caption
    logger.info(f"Original Title: {title}")

    # Translate title to English if it's Chinese
    english_title = title
    try:
        from deep_translator import GoogleTranslator
        english_title = GoogleTranslator(source='auto', target='en').translate(title)
        print(f"Translated Title: {english_title}")
    except Exception as e:
        print(f"Failed to translate title: {e}")

    # Generate viral English SEO metadata
    try:
        try:
            from src.seo_generator import generate_seo_metadata, format_caption
        except ImportError:
            from seo_generator import generate_seo_metadata, format_caption

        clean_title = re.sub(r'^\d{2}:\d{2}\s+\d+\.?\d*万\s*', '', english_title).strip()
        seo_data = generate_seo_metadata(clean_title, media_type='reel')
        fb_caption = format_caption(seo_data)
        headline = seo_data.get('title', clean_title)
        video_data["seo_title"] = headline
        print(f"Generated SEO Caption:\n{fb_caption}")
    except Exception as e:
        print(f"Failed to generate SEO metadata: {e}")
        fb_caption = f"{headline or english_title}\n\n#viral #trending #fyp #foryou #reels #shorts #pets #animals #cute"

    video_data["description"] = fb_caption

    delay_seconds = 2
    time.sleep(delay_seconds)

    # Facebook Upload
    try:
        print(f"Uploading to Facebook with caption:\n{fb_caption}")
        fb_url = upload_reel(edited_video_path, fb_caption)
        print(f"Successfully uploaded to Facebook: {fb_url}")
        video_data["upload_status"] = "Success"
        video_data["fb_url"] = fb_url
    except Exception as e:
        print(f"Failed to upload to Facebook: {e}")
        video_data["upload_status"] = "Failed"
        video_data["fb_err"] = str(e)

    # YouTube Upload (only if Facebook upload succeeded)
    if video_data.get("upload_status") == "Success":
        has_yt_creds = os.environ.get('YOUTUBE_TOKEN_JSON') or os.path.exists('youtube_token.json')
        if has_yt_creds:
            try:
                time.sleep(2)
                yt_title = title[:100]
                yt_desc = f"{fb_caption}\n#shorts"
                yt_url = upload_to_youtube(edited_video_path, yt_title, yt_desc)
                video_data["yt_url"] = yt_url
            except Exception as e:
                print(f"Failed to upload to YouTube: {e}")
                video_data["yt_err"] = str(e)
        else:
            print("YouTube credentials not found. Skipping YouTube upload.")
            video_data["yt_url"] = "Skipped (Not configured)"

    # Cleanup edited video after upload
    if os.path.exists(edited_video_path):
        os.remove(edited_video_path)

    return video_data


import logging
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    import json
    state_file = "workspace/video_data.json"

    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            video_data = json.load(f)

        updated_data = run_upload(video_data)

        with open(state_file, "w") as f:
            json.dump(updated_data, f, indent=2)

        print(f"Uploader finished. Status: {updated_data.get('upload_status')}")
    else:
        print("No active video_data.json found. Skipping uploader.")
