"""
Agent 2: Pet Video Editor
- Generates Chinese headlines via Nvidia API
- Creates yellow border overlay with PIL
- Composites to 1080x1920 format with FFmpeg
- Applies anti-copyright filters (speed, crop, color, pitch)
- Integration with translation pipeline
"""

import os
import re
import json
import logging
import subprocess
import shutil
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
        headline = headline.strip("\"'「」\"\"")
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

    # Yellow border
    draw.rectangle(
        [0, 0, OUTPUT_WIDTH - 1, OUTPUT_HEIGHT - 1],
        outline=BORDER_COLOR,
        width=BORDER_WIDTH,
    )
    # Double border effect
    draw.rectangle(
        [BORDER_WIDTH + 4, BORDER_WIDTH + 4,
         OUTPUT_WIDTH - BORDER_WIDTH - 5, OUTPUT_HEIGHT - BORDER_WIDTH - 5],
        outline=BORDER_COLOR,
        width=4,
    )

    # Load font (try CJK fonts first, then fallback)
    font = None
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        os.path.join(os.path.dirname(__file__), '..', 'assets', 'NotoSansSC-Regular.ttf'),
        os.path.join(os.path.dirname(__file__), '..', 'assets', 'BebasNeue-Regular.ttf'),
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

    shadow_offset = 3
    draw.text((text_x + shadow_offset, text_y + shadow_offset),
              headline, font=font, fill=TEXT_SHADOW_COLOR)
    draw.text((text_x, text_y), headline, font=font, fill=TEXT_COLOR)

    # Save overlay
    overlay_path = "workspace/edited/_overlay.png"
    os.makedirs(os.path.dirname(overlay_path), exist_ok=True)
    img.save(overlay_path, "PNG")
    logger.info(f"Created overlay image: {overlay_path}")
    return overlay_path


def _get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", video_path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception as exc:
        logger.warning("Could not get duration: %s", exc)
        return 15.0


def _edit_with_ffmpeg(input_path: str, overlay_path: str, output_path: str):
    """Use FFmpeg to scale to 9:16 (1080x1920) and overlay the headline border."""
    duration = _get_video_duration(input_path)
    max_duration = min(duration, 179)  # Cap at 2min 59s for Reels

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", overlay_path,
        "-filter_complex",
        (
            # 9:16 conversion: scale to fill 1080x1920, crop excess, overlay headline
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "[1:v]overlay=0:0"
        ),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", str(max_duration),
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info("Running FFmpeg compositing...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.error("FFmpeg stderr: %s", result.stderr[-500:] if result.stderr else "")
        raise RuntimeError(f"FFmpeg failed with code {result.returncode}")
def _add_watermark(input_path: str, output_path: str):
    """Add a subtle channel name watermark to the video using FFmpeg drawtext."""
    watermark_text = os.environ.get("WATERMARK_TEXT", "DailyPetJoy")
    logger.info(f"Adding watermark '{watermark_text}' to video...")

    try:
        # Find a usable font
        font_path = None
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
        for fp in font_candidates:
            if os.path.exists(fp):
                font_path = fp
                break

        font_opt = f"fontfile={font_path}:" if font_path else ""

        # Subtle watermark: low opacity (0.15), bottom-right, small font
        drawtext = (
            f"drawtext={font_opt}"
            f"text='{watermark_text}':"
            f"fontsize=28:"
            f"fontcolor=white@0.15:"
            f"x=w-tw-20:"
            f"y=h-th-20:"
            f"shadowcolor=black@0.1:"
            f"shadowx=1:shadowy=1"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", drawtext,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"Watermark FFmpeg failed: {result.stderr[-300:]}")
            return
        logger.info(f"Watermark added: {output_path}")
    except Exception as e:
        logger.error(f"Error adding watermark: {e}")


def apply_copyright_filters(video_path):
    """Apply anti-copyright filters: speed 1.05x, crop 5%, brightness +5%, pitch shift."""
    logger.info("Applying Anti-Copyright Filters (Speed 1.05x, Crop 5%, Brightness +5%, Pitch shift)...")
    temp_path = video_path.replace(".mp4", "_clean.mp4")

    try:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        shutil.move(video_path, temp_path)

        cmd = [
            'ffmpeg', '-y',
            '-i', temp_path,
            '-vf', "setpts=PTS/1.05,crop=w=iw*0.95:h=ih*0.95,scale=iw:ih,eq=brightness=0.05:contrast=1.05:saturation=1.1",
            '-af', "asetrate=44100*1.05,aresample=44100",
            video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0:
            logger.info(f"Anti-Copyright filters applied: {video_path}")
        else:
            logger.error(f"Anti-Copyright filter failed: {res.stderr}. Restoring original.")
            if os.path.exists(video_path):
                os.remove(video_path)
            shutil.move(temp_path, video_path)

        if os.path.exists(temp_path):
            os.remove(temp_path)
    except Exception as e:
        logger.error(f"Error applying anti-copyright filters: {e}")
        if os.path.exists(temp_path) and not os.path.exists(video_path):
            shutil.move(temp_path, video_path)


def overlay_on_pet_template(video_path, output_path):
    """
    Overlays video onto the Daily Pet Joy template.
    Template: assets/pet_template.jpg (932x1280 native)
    Output: 1080x1920 (Reels format)
    Content area: X=28, Y=104, W=876, H=1080 (in 932x1280 template)
    """
    logger.info("Applying pet template overlay to video...")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(base_dir, 'assets', 'pet_template.jpg')
    if not os.path.exists(template_path):
        template_path = 'assets/pet_template.jpg'

    if not os.path.exists(template_path):
        logger.error(f"Pet template not found at {template_path}. Skipping overlay.")
        return video_path

    try:
        # Template is 932x1280, output must be 1080x1920
        # Scale template to fill width (1080px), center vertically
        scale = 1080 / 932  # = 1.159
        scaled_h = int(1280 * scale)  # = 1483
        y_offset = (1920 - scaled_h) // 2  # = 218 (black bar at top/bottom)

        # Content area in scaled template (exact coordinates)
        content_x = int(28 * scale)    # = 32
        content_y = int(104 * scale) + y_offset  # = 339
        content_w = int(876 * scale)   # = 1015
        content_h = int(1080 * scale)  # = 1252

        # Video: scale to fill content area exactly, crop excess
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', f'color=c=black:s=1080x1920:d=1',  # black canvas
            '-i', template_path,
            '-i', video_path,
            '-filter_complex',
            (
                # Scale template to 1080 width, center vertically on black canvas
                f'[1:v]scale=1080:-2:force_original_aspect_ratio=decrease[tmp_scaled];'
                # Place scaled template centered on black canvas
                f'[0:v][tmp_scaled]overlay=(W-w)/2:{y_offset}[tmp_placed];'
                # Scale video to fill content area exactly, crop excess
                f'[2:v]scale={content_w}:{content_h}:force_original_aspect_ratio=increase,'
                f'crop={content_w}:{content_h}[vid];'
                # Overlay video onto template at content area
                f'[tmp_placed][vid]overlay={content_x}:{content_y}[outv]'
            ),
            '-map', '[outv]',
            '-map', '2:a',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'copy',
            '-t', '179',  # max 2min 59s for Reels
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"FFmpeg template overlay failed: {result.stderr[-300:]}")
            return video_path

        logger.info(f"Video overlaid on pet template: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error during template overlay: {e}")
        return video_path


def validate_aspect_ratio(video_path) -> bool:
    """Check if video has 9:16 aspect ratio."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'json', video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, check=True, timeout=15)
        info = json.loads(result.stdout)
        streams = info.get('streams', [])
        if not streams:
            return False
        width = streams[0].get('width')
        height = streams[0].get('height')
        if not width or not height:
            return False
        ratio = width / height
        return 0.55 <= ratio <= 0.58
    except Exception as e:
        logger.warning(f"Error checking aspect ratio: {e}")
        return False


def process_video(video_data) -> dict:
    """
    Main video processing entry point.
    Handles translation (if enabled), editing, and anti-copyright filters.
    """
    logger.info("Starting Agent 2: Video Editor")

    raw_video_path = video_data.get('local_path', "workspace/raw_video.mp4")
    title = video_data.get('title', 'Unknown Video')
    edited_video_path = f"workspace/edited/edited_{video_data.get('id', 'video')}.mp4"

    if not os.path.exists(raw_video_path):
        logger.error(f"Raw video not found at {raw_video_path}.")
        video_data["editing_status"] = "Failed"
        return video_data

    # Translation step if enabled
    translate_enabled = os.environ.get('ENABLE_TRANSLATION', 'false').lower() == 'true'
    if translate_enabled:
        logger.info("Translating Chinese video to English...")
        try:
            try:
                from .translator import translate_video
            except ImportError:
                from translator import translate_video

            output_dir = "workspace"
            sub_lang = os.environ.get('SUBTITLE_LANGUAGE', 'english')
            translation_result = translate_video(
                raw_video_path,
                output_dir=output_dir,
                burn_subtitles=False,
                subtitle_language=sub_lang
            )
            if translation_result and translation_result.get('english_video'):
                translated_video = translation_result['english_video']
                if os.path.exists(translated_video):
                    video_data["editing_status"] = "Success"
                    video_data["seo_title"] = title
                    video_data["edited_path"] = edited_video_path
                    os.makedirs(os.path.dirname(edited_video_path), exist_ok=True)
                    shutil.copy2(translated_video, edited_video_path)
                    logger.info(f"Translated video saved at: {edited_video_path}")

                    apply_copyright_filters(edited_video_path)

                    # Add subtle watermark
                    watermarked_path = edited_video_path.replace(".mp4", "_wm.mp4")
                    _add_watermark(edited_video_path, watermarked_path)
                    if os.path.exists(watermarked_path):
                        shutil.move(watermarked_path, edited_video_path)

                    # Cleanup
                    if raw_video_path != translated_video and os.path.exists(raw_video_path):
                        try:
                            os.remove(raw_video_path)
                        except:
                            pass
                    try:
                        os.remove(translated_video)
                    except:
                        pass
                    return video_data
        except Exception as e:
            logger.error(f"Translation failed: {e}. Proceeding with original video.")

    # Non-translation path: mute speech + add BGM + 9:16 + watermark
    logger.info(f"Processing video (no dubbing): {title}")

    os.makedirs(os.path.dirname(edited_video_path), exist_ok=True)

    try:
        # Step 1: Convert to 9:16 (1080x1920)
        headline = _generate_headline()
        overlay_path = _create_overlay_image(headline)
        _edit_with_ffmpeg(raw_video_path, overlay_path, edited_video_path)
        if os.path.exists(overlay_path):
            os.remove(overlay_path)

        # Step 2: Mute Chinese speech, keep SFX, add BGM
        try:
            from .translator import mute_speech_keep_sfx
        except ImportError:
            from translator import mute_speech_keep_sfx

        muted_path = edited_video_path.replace(".mp4", "_muted.mp4")
        muted_result = mute_speech_keep_sfx(edited_video_path, muted_path)
        if muted_result and os.path.exists(muted_result):
            shutil.move(muted_result, edited_video_path)
            logger.info("Speech muted + BGM applied")
        else:
            logger.warning("Mute speech failed, using video as-is")

        # Step 3: Copyright filters
        apply_copyright_filters(edited_video_path)

        # Step 4: Watermark
        watermarked_path = edited_video_path.replace(".mp4", "_wm.mp4")
        _add_watermark(edited_video_path, watermarked_path)
        if os.path.exists(watermarked_path):
            shutil.move(watermarked_path, edited_video_path)

        video_data["editing_status"] = "Success"
        video_data["seo_title"] = title
        video_data["edited_path"] = edited_video_path

        # Cleanup
        if os.path.exists(raw_video_path):
            os.remove(raw_video_path)
        return video_data
    except Exception as e:
        logger.error(f"Editing failed: {e}")
        video_data["editing_status"] = "Failed"
        return video_data


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python agent_2_editor.py <input_video_path>")
        sys.exit(1)
    data = {"id": "test", "title": "test video", "local_path": sys.argv[1]}
    result = process_video(data)
    if result.get("editing_status") == "Success":
        print(f"Edited video: {result.get('edited_path')}")
    else:
        print("Editing failed.")
        sys.exit(1)
