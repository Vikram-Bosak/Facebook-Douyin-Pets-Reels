"""
Agent 2: Douyin Pet Video Editor
- Generates Chinese headlines via Nvidia API
- Creates yellow border overlay with PIL
- Composites to 1080x1920 format with FFmpeg
- Saves edited video to workspace/edited/
"""

import os
import re
import json
import logging
import subprocess
import random
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Nvidia API for headline generation
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_API_URL = os.environ.get(
    "NVIDIA_API_URL",
    "https://integrate.api.nvidia.com/v1/chat/completions",
)
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

# Output dimensions
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

# Overlay style
BORDER_COLOR = (255, 255, 0)  # yellow
BORDER_WIDTH = 12
FONT_SIZE = 64
TEXT_COLOR = (255, 255, 255)  # white text
TEXT_SHADOW_COLOR = (0, 0, 0)  # black shadow
HEADLINE_POSITION_Y = 1600  # near bottom

# Fallback headlines if API is unavailable
FALLBACK_HEADLINES = [
    "萌宠日常太治愈了",
    "这只猫咪也太可爱了吧",
    "狗狗的搞笑瞬间",
    "大熊猫的悠闲时光",
    "宠物界的颜值天花板",
    "看完心情瞬间变好",
    "治愈系萌宠合集",
    "你家毛孩子也这样吗",
]


def _generate_headline() -> str:
    """Generate a catchy Chinese headline using Nvidia API or fallback."""
    if not NVIDIA_API_KEY:
        logger.warning("No NVIDIA_API_KEY set, using fallback headline")
        return random.choice(FALLBACK_HEADLINES)

    try:
        import httpx

        prompt = (
            "你是一个短视频标题生成器。根据萌宠视频生成一个吸引人的中文标题（15字以内）。"
            "要求：使用表情符号，语气活泼，适合抖音风格。只输出标题，不要其他内容。"
        )

        resp = httpx.post(
            NVIDIA_API_URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": NVIDIA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 64,
                "temperature": 0.8,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        headline = data["choices"][0]["message"]["content"].strip()
        # Clean up: remove quotes and extra whitespace
        headline = headline.strip("\"'「」""")
        if len(headline) > 30:
            headline = headline[:28] + "…"
        return headline

    except Exception as exc:
        logger.error("Nvidia API headline generation failed: %s", exc)
        return random.choice(FALLBACK_HEADLINES)


def _create_overlay_image(headline: str) -> str:
    """Create a 1080x1920 transparent overlay with yellow border and headline text."""
    img = Image.new("RGBA", (OUTPUT_WIDTH, OUTPUT_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw yellow border
    draw.rectangle(
        [0, 0, OUTPUT_WIDTH - 1, OUTPUT_HEIGHT - 1],
        outline=BORDER_COLOR,
        width=BORDER_WIDTH,
    )
    # Second inner border for double-border effect
    draw.rectangle(
        [BORDER_WIDTH + 4, BORDER_WIDTH + 4,
         OUTPUT_WIDTH - BORDER_WIDTH - 5, OUTPUT_HEIGHT - BORDER_WIDTH - 5],
        outline=BORDER_COLOR,
        width=4,
    )

    # Load a font (try system CJK fonts, fallback to default)
    font = None
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, FONT_SIZE)
                break
            except Exception:
                continue
    if font is None:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", FONT_SIZE)
        except Exception:
            font = ImageFont.load_default()

    # Draw headline text with shadow
    bbox = draw.textbbox((0, 0), headline, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = (OUTPUT_WIDTH - text_w) // 2
    text_y = HEADLINE_POSITION_Y

    # Shadow
    shadow_offset = 3
    draw.text((text_x + shadow_offset, text_y + shadow_offset),
              headline, font=font, fill=TEXT_SHADOW_COLOR)
    # Main text
    draw.text((text_x, text_y), headline, font=font, fill=TEXT_COLOR)

    # Save overlay
    overlay_path = "workspace/edited/_overlay.png"
    os.makedirs(os.path.dirname(overlay_path), exist_ok=True)
    img.save(overlay_path, "PNG")
    logger.info("Created overlay image: %s", overlay_path)
    return overlay_path


def _get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                video_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception as exc:
        logger.warning("Could not get duration: %s", exc)
        return 15.0  # default


def _edit_with_ffmpeg(input_path: str, overlay_path: str, output_path: str):
    """
    Use FFmpeg to:
    1. Scale video to fill 1080x1920 (pad if needed)
    2. Overlay the border + headline image
    """
    duration = _get_video_duration(input_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", overlay_path,
        "-filter_complex",
        (
            # Scale source to fit within 1080x1920, pad to exact size
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
            # Overlay the border + headline on top
            "[1:v]overlay=0:0"
        ),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(min(duration, 60)),  # cap at 60 seconds
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info("Running FFmpeg: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.error("FFmpeg stderr: %s", result.stderr[-500:] if result.stderr else "")
        raise RuntimeError(f"FFmpeg failed with code {result.returncode}")


def edit_video(
    input_path: str,
    output_dir: str = "workspace/edited",
) -> Optional[str]:
    """
    Edit a single video:
    1. Generate headline
    2. Create overlay
    3. Composite with FFmpeg
    Returns output path or None on failure.
    """
    if not os.path.exists(input_path):
        logger.error("Input video not found: %s", input_path)
        return None

    # Generate headline
    headline = _generate_headline()
    logger.info("Generated headline: %s", headline)

    # Create overlay
    overlay_path = _create_overlay_image(headline)

    # Build output path
    basename = os.path.basename(input_path)
    output_path = os.path.join(output_dir, f"edited_{basename}")
    os.makedirs(output_dir, exist_ok=True)

    # Run FFmpeg
    try:
        _edit_with_ffmpeg(input_path, overlay_path, output_path)
    except Exception as exc:
        logger.error("FFmpeg editing failed for %s: %s", input_path, exc)
        return None

    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        logger.info("Edited video saved: %s (%d bytes)", output_path, file_size)
        return output_path
    else:
        logger.error("Output file not created: %s", output_path)
        return None


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python agent_2_editor.py <input_video_path>")
        sys.exit(1)
    result = edit_video(sys.argv[1])
    if result:
        print(f"Edited video: {result}")
    else:
        print("Editing failed.")
        sys.exit(1)
