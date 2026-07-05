#!/usr/bin/env python3
"""
Health Check Script for Pet Reels Pipeline
Verifies all components are working before running the pipeline.
"""

import os
import sys
import json
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()

def check_ffmpeg():
    """Check if ffmpeg is installed."""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False

def check_python_packages():
    """Check if required Python packages are installed."""
    required = ['requests', 'PIL', 'ffmpeg', 'openai', 'dotenv']
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return missing

def check_facebook_token():
    """Verify Facebook access token is valid."""
    token = os.environ.get('FB_ACCESS_TOKEN')
    page_id = os.environ.get('FB_PAGE_ID')
    if not token or not page_id:
        return False, "FB_ACCESS_TOKEN or FB_PAGE_ID not set"
    
    try:
        url = f"https://graph.facebook.com/v19.0/me?access_token={token}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return True, "Facebook token valid"
        else:
            data = resp.json()
            error = data.get('error', {})
            return False, f"Facebook error: {error.get('message', 'Unknown')} (code: {error.get('code')})"
    except Exception as e:
        return False, f"Facebook connection failed: {e}"

def check_discord_webhook():
    """Verify Discord webhook is configured."""
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        return False, "DISCORD_WEBHOOK_URL not set"
    return True, "Discord webhook configured"

def check_telegram():
    """Verify Telegram bot is configured."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return False, "Telegram not configured (optional)"
    return True, "Telegram configured"

def check_bilibili_api():
    """Test Bilibili API connectivity."""
    try:
        url = "https://api.bilibili.com/x/web-interface/search/all/v2"
        params = {"keyword": "萌宠", "page": "1", "search_type": "video"}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        if data.get('code') == 0:
            return True, "Bilibili API accessible"
        else:
            return False, f"Bilibili API error: {data.get('message')}"
    except Exception as e:
        return False, f"Bilibili connection failed: {e}"

def check_template():
    """Check if pet template exists."""
    template_paths = [
        'assets/pet_template.jpg',
        os.path.join(os.path.dirname(__file__), 'assets', 'pet_template.jpg'),
    ]
    for path in template_paths:
        if os.path.exists(path):
            return True, f"Pet template found: {path}"
    return False, "Pet template not found"

def main():
    print("=" * 50)
    print("🐾 Pet Reels Pipeline - Health Check")
    print("=" * 50)
    
    checks = [
        ("FFmpeg", check_ffmpeg),
        ("Bilibili API", check_bilibili_api),
        ("Pet Template", check_template),
        ("Facebook Token", check_facebook_token),
        ("Discord Webhook", check_discord_webhook),
        ("Telegram Bot", check_telegram),
    ]
    
    all_ok = True
    for name, check_fn in checks:
        try:
            result = check_fn()
            if isinstance(result, tuple):
                ok, msg = result
            else:
                ok, msg = result, "OK" if result else "FAILED"
            
            status = "✅" if ok else "❌"
            print(f"{status} {name}: {msg}")
            if not ok:
                all_ok = False
        except Exception as e:
            print(f"❌ {name}: Error - {e}")
            all_ok = False
    
    # Check Python packages
    missing = check_python_packages()
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        all_ok = False
    else:
        print("✅ Python packages: All installed")
    
    print("=" * 50)
    if all_ok:
        print("🎉 All checks passed! Pipeline is ready.")
    else:
        print("⚠️  Some checks failed. Fix issues before running pipeline.")
    print("=" * 50)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
