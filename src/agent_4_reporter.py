"""
Agent 4: Reporter
Sends Discord webhook reports and performs workspace cleanup.
"""

import os
import json
import html

try:
    from src.discord_reporter import send_discord_message
except ImportError:
    from discord_reporter import send_discord_message


def main():
    print("Starting Agent 4: Reporter")
    report_path = "workspace/report.json"

    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            try:
                report = json.load(f)
            except json.JSONDecodeError:
                report = {}
    else:
        report = {}

    # Default values
    video_name = html.escape(report.get('video_name', 'N/A'))
    download_status = html.escape(report.get('download_status', 'Failed / Unknown'))
    editing_status = html.escape(report.get('editing_status', 'N/A'))
    seo_title = html.escape(report.get('seo_title', 'N/A'))
    description = html.escape(report.get('description', 'N/A'))
    raw_video_url = html.escape(report.get('source_url', 'N/A'))

    fb_url = html.escape(report.get('facebook_url', report.get('fb_url', 'N/A')))
    yt_url = html.escape(report.get('youtube_url', report.get('yt_url', 'N/A')))
    fb_err = report.get('fb_err', '')
    yt_err = report.get('yt_err', '')

    # Determine per-platform status accurately
    fb_status = "Success" if "facebook.com" in fb_url or "fb.com" in fb_url else ("Failed" if fb_err else "N/A")
    yt_status = "Success" if "youtube.com" in yt_url or "youtu.be" in yt_url else ("Failed" if yt_err else "Skipped")
    overall_status = "Success" if fb_status == "Success" or yt_status == "Success" else "Failed"

    # GitHub Action Variables
    repo = os.environ.get('GITHUB_REPOSITORY') or "Vikram-Bosak/Facebook-Douyin-Pets-Reels"
    run_id = os.environ.get('GITHUB_RUN_ID')
    repo_url = f"https://github.com/{repo}"
    run_url = f"{repo_url}/actions/runs/{run_id}" if run_id else f"{repo_url}/actions"

    emoji_status = "✅" if overall_status == "Success" else "❌"

    message = (
        f"✅ Pipeline Run Completed\n\n"
        f"🎬 Video Name:\n{video_name}\n\n"
        f"📤 Facebook Upload Status: {fb_status}\n"
        f"📤 YouTube Upload Status: {yt_status}\n\n"
        f"🏷️ SEO Title:\n{seo_title}\n\n"
        f"📝 Description:\n{description}\n\n"
        f"Original File: {video_name}.mp4\n\n"
        f"🔗 Raw Video URL:\n{raw_video_url}\n\n"
        f"🔗 Facebook Reel URL:\n{fb_url}\n\n"
        f"▶️ YouTube Video URL:\n{yt_url}\n\n"
        f"📦 GitHub Repository:\n{repo_url}\n\n"
        f"📄 Workflow Run:\n{run_url}"
    )

    if "No new video" in download_status:
        print("No new video to process. Skipping Discord notification.")
    else:
        send_discord_message(message)

    # Selective cleanup
    print("Performing selective cleanup of temporary files...")
    temp_files = [
        "workspace/video_data.json",
        "workspace/report.json",
        "workspace/raw_video.mp4"
    ]
    for tf in temp_files:
        if os.path.exists(tf):
            try:
                os.remove(tf)
                print(f"Removed: {tf}")
            except Exception as e:
                print(f"Could not remove {tf}: {e}")

    # Clean edited files
    edited_dir = "workspace/edited"
    if os.path.exists(edited_dir):
        for filename in os.listdir(edited_dir):
            if filename.startswith("edited_") or filename.startswith("raw_video"):
                filepath = os.path.join(edited_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        print(f"Removed: {filepath}")
                except Exception as e:
                    print(f"Could not remove {filepath}: {e}")


if __name__ == "__main__":
    main()
