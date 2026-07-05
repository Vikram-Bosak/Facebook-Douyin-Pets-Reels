"""
Chinese to English Video Translation Pipeline (Pet Videos)

Pipeline:
1. Extract audio from video (ffmpeg)
2. Transcribe Chinese audio -> text (OpenAI Whisper)
3. Translate Chinese text -> English (OpenAI GPT)
4. Generate English TTS audio (3-tier: OpenAI TTS -> Kokoro ONNX -> edge-tts)
5. Separate vocals from BGM (Demucs)
6. Merge translated audio with original video + copyright-free BGM
7. Generate SRT subtitles (Chinese + English)
"""

import os
import sys
import json
import subprocess
import tempfile
import asyncio
from pathlib import Path

try:
    from .logger import logger
except ImportError:
    from logger import logger


# ============================================================
# STEP 1: Extract Audio from Video
# ============================================================

def extract_audio(video_path, output_audio_path=None):
    """Extract audio track from video file using ffmpeg."""
    if output_audio_path is None:
        base = os.path.splitext(video_path)[0]
        output_audio_path = f"{base}_audio.wav"

    logger.info(f"Extracting audio from: {video_path}")

    try:
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            output_audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            logger.error(f"FFmpeg audio extraction failed: {result.stderr}")
            return None

        logger.info(f"Audio extracted successfully: {output_audio_path}")
        return output_audio_path

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg audio extraction timed out")
        return None
    except FileNotFoundError:
        logger.error("FFmpeg not found. Please install FFmpeg.")
        return None
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        return None


# ============================================================
# STEP 2: Transcribe Chinese Audio -> Text (Whisper)
# ============================================================

def transcribe_chinese_audio(audio_path, use_api=True):
    """Transcribe Chinese audio to text with timestamps."""
    logger.info(f"Transcribing Chinese audio: {audio_path}")

    if use_api:
        return _transcribe_with_openai_api(audio_path)
    else:
        return _transcribe_with_local_whisper(audio_path)


def _transcribe_with_openai_api(audio_path):
    """Use OpenAI Whisper API for transcription."""
    try:
        from openai import OpenAI

        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY not found, falling back to local whisper")
            return _transcribe_with_local_whisper(audio_path)

        client = OpenAI(api_key=api_key)

        with open(audio_path, 'rb') as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="zh",
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )

        segments = []
        for seg in response.segments:
            segments.append({
                'start': seg['start'],
                'end': seg['end'],
                'text': seg['text'].strip()
            })

        logger.info(f"Transcribed {len(segments)} segments via OpenAI API")
        return segments

    except Exception as e:
        logger.error(f"OpenAI API transcription failed: {e}")
        return _transcribe_with_local_whisper(audio_path)


def _transcribe_with_local_whisper(audio_path):
    """Use local openai-whisper package for transcription."""
    try:
        import whisper

        logger.info("Loading local Whisper model (base)...")
        model = whisper.load_model("base")

        result = model.transcribe(
            audio_path,
            language="zh",
            task="transcribe",
            verbose=False
        )

        segments = []
        for seg in result.get('segments', []):
            segments.append({
                'start': seg['start'],
                'end': seg['end'],
                'text': seg['text'].strip()
            })

        logger.info(f"Transcribed {len(segments)} segments locally")
        return segments

    except ImportError:
        logger.error("whisper package not installed. Run: pip install openai-whisper")
        return []
    except Exception as e:
        logger.error(f"Local Whisper transcription failed: {e}")
        return []


# ============================================================
# STEP 3: Translate Chinese Text -> English (OpenAI GPT)
# ============================================================

def translate_segments_to_english(segments):
    """Translate Chinese text segments to English using OpenAI GPT."""
    if not segments:
        return []

    logger.info(f"Translating {len(segments)} segments to English...")

    batches = _create_translation_batches(segments, max_chars=2000)

    translated_segments = []
    for batch in batches:
        batch_texts = [s['text'] for s in batch]
        batch_translations = _translate_batch(batch_texts)

        for i, seg in enumerate(batch):
            english_text = batch_translations[i] if i < len(batch_translations) else seg['text']
            translated_segments.append({
                'start': seg['start'],
                'end': seg['end'],
                'chinese': seg['text'],
                'english': english_text
            })

    logger.info(f"Translated {len(translated_segments)} segments")
    return translated_segments


def _create_translation_batches(segments, max_chars=2000):
    """Group segments into batches for efficient API calls."""
    batches = []
    current_batch = []
    current_chars = 0

    for seg in segments:
        seg_chars = len(seg['text'])
        if current_chars + seg_chars > max_chars and current_batch:
            batches.append(current_batch)
            current_batch = [seg]
            current_chars = seg_chars
        else:
            current_batch.append(seg)
            current_chars += seg_chars

    if current_batch:
        batches.append(current_batch)

    return batches


def _translate_batch(texts):
    """Translate a batch of Chinese texts to English using OpenAI GPT or Google Translate fallback."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        try:
            from openai import OpenAI
            base_url = os.environ.get('OPENAI_API_BASE_URL')
            model = os.environ.get('OPENAI_API_MODEL', 'gpt-4o-mini')

            if base_url:
                client = OpenAI(api_key=api_key, base_url=base_url)
            else:
                client = OpenAI(api_key=api_key)

            numbered_texts = "\n".join([f"{i+1}. {t}" for i, t in enumerate(texts)])

            system_prompt = (
                "You are an expert funny translator and creative script writer specializing in "
                "translating Chinese viral pet animal videos for a US audience. "
                "Your task is to translate and adapt the following segments into highly natural, "
                "engaging, and colloquial American English. "
                "IMPORTANT: Filter out all duplicate loop/stuttering words like 'I I I I' "
                "that happen due to video edits or sound effects. "
                "Restructure them into clean, engaging sentences. "
                "Make the script funny, dramatic, and interesting, matching the timing "
                "of the original segments. "
                "Ensure the translation is concise so that it can be spoken in a similar "
                "duration as the original Chinese segment. "
                "Return ONLY the translations, one per line, numbered to match the input format."
            )

            user_prompt = f"Translate these Chinese pet video segments to English:\n\n{numbered_texts}"

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            result = response.choices[0].message.content.strip()

            import re
            translations = []
            for line in result.split('\n'):
                line = line.strip()
                if not line:
                    continue
                cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
                if cleaned:
                    translations.append(cleaned)

            while len(translations) < len(texts):
                translations.append(texts[len(translations)])

            logger.info(f"Translated {len(translations)} segments via OpenAI API")
            return translations[:len(texts)]
        except Exception as e:
            logger.error(f"OpenAI translation failed: {e}. Falling back to Google Translate.")

    # Fallback to Google Translate
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='zh-CN', target='en')
        translations = []
        for text in texts:
            if not text.strip():
                translations.append(text)
                continue
            try:
                translated = translator.translate(text)
                translations.append(translated if translated else text)
            except Exception as e:
                logger.warning(f"Translation failed for segment: {e}")
                translations.append(text)
        logger.info(f"Translated {len(translations)} segments via Google Translate (free)")
        return translations
    except ImportError:
        logger.error("deep-translator not installed. Run: pip install deep-translator")
        return texts
    except Exception as e:
        logger.error(f"Free translation error: {e}")
        return texts


# ============================================================
# STEP 4: Generate English TTS Audio
# ============================================================

def get_audio_duration(path):
    """Get the duration of an audio file using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0', path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(res.stdout.strip())
    except Exception as e:
        logger.error(f"Error getting audio duration for {path}: {e}")
        return 0.0


_kokoro_instance = None

def get_kokoro():
    """Load Kokoro ONNX TTS model (singleton)."""
    global _kokoro_instance
    if _kokoro_instance is None:
        try:
            user_site = os.path.expanduser('~/.local/lib/python3.12/site-packages')
            if user_site not in sys.path:
                sys.path.append(user_site)
            from kokoro_onnx import Kokoro
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(base_dir, 'assets', 'kokoro', 'kokoro-v1.0.onnx')
            voices_path = os.path.join(base_dir, 'assets', 'kokoro', 'voices-v1.0.bin')
            if not os.path.exists(model_path):
                model_path = 'assets/kokoro/kokoro-v1.0.onnx'
                voices_path = 'assets/kokoro/voices-v1.0.bin'
            if os.path.exists(model_path) and os.path.exists(voices_path):
                logger.info(f"Initializing Kokoro ONNX model from {model_path}...")
                _kokoro_instance = Kokoro(model_path, voices_path)
            else:
                logger.warning(f"Kokoro model files not found. Fallback to edge-tts.")
        except Exception as e:
            logger.error(f"Failed to load Kokoro: {e}")
    return _kokoro_instance


def generate_segment_tts(text, voice, output_path):
    """Generate a single TTS audio chunk using OpenAI TTS -> Kokoro ONNX -> edge-tts."""
    # 1st: OpenAI TTS
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            openai_voice = 'onyx'
            voice_lower = voice.lower()
            if 'christopher' in voice_lower or 'guy' in voice_lower or 'eric' in voice_lower or 'male' in voice_lower:
                openai_voice = 'onyx'
            elif 'samantha' in voice_lower or 'jenny' in voice_lower or 'aria' in voice_lower or 'female' in voice_lower:
                openai_voice = 'nova'
            elif voice in ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']:
                openai_voice = voice

            response = client.audio.speech.create(
                model="tts-1",
                voice=openai_voice,
                input=text,
                speed=0.9
            )
            response.stream_to_file(output_path)
            return True
        except Exception as e:
            logger.error(f"OpenAI TTS failed: {e}. Falling back.")

    # 2nd: Kokoro ONNX
    try:
        kokoro = get_kokoro()
        if kokoro:
            kokoro_voice = "af_sarah"
            voice_lower = voice.lower()
            if 'guy' in voice_lower or 'male' in voice_lower or 'christopher' in voice_lower or 'george' in voice_lower:
                kokoro_voice = "bm_george"
            elif 'bella' in voice_lower:
                kokoro_voice = "af_bella"
            elif 'heart' in voice_lower:
                kokoro_voice = "af_heart"
            elif 'michael' in voice_lower:
                kokoro_voice = "am_michael"
            elif 'nicole' in voice_lower or 'emma' in voice_lower:
                kokoro_voice = "bf_emma"
            elif voice.startswith("af_") or voice.startswith("am_") or voice.startswith("bf_") or voice.startswith("bm_"):
                kokoro_voice = voice

            samples, sample_rate = kokoro.create(text, voice=kokoro_voice, speed=0.9, lang="en-us")
            import soundfile as sf
            sf.write(output_path, samples, sample_rate)
            return True
    except Exception as e:
        logger.error(f"Kokoro TTS generation failed: {e}. Falling back to edge-tts.")

    # 3rd: edge-tts (free fallback)
    try:
        import edge_tts
        asyncio.run(edge_tts.Communicate(text, voice, rate="-20%").save(output_path))
        return True
    except Exception as e:
        logger.error(f"edge-tts failed for text '{text}': {e}")
        return False


def generate_english_tts(segments, output_audio_path=None, video_path=None):
    """Generate English TTS audio from translated segments and align to video timeline."""
    if not segments:
        return None

    if output_audio_path is None:
        output_audio_path = os.path.join(tempfile.gettempdir(), "tts_output.mp3")

    logger.info(f"Generating and aligning English TTS for {len(segments)} segments...")

    # Calculate total duration
    total_duration = 60.0
    if video_path:
        try:
            probe_cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0', video_path
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            total_duration = float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Could not read video duration: {e}. Defaulting to max segment end.")
            total_duration = max(s['end'] for s in segments) + 1.0
    else:
        total_duration = max(s['end'] for s in segments) + 1.0

    voice = os.environ.get('TTS_VOICE', 'en-US-ChristopherNeural')
    temp_dir = tempfile.gettempdir()

    # Step 1: Create silent base audio track
    silent_base = os.path.join(temp_dir, "silent_base.wav")
    try:
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=stereo',
            '-t', str(total_duration),
            silent_base
        ], capture_output=True, check=True)
    except Exception as e:
        logger.error(f"Failed to generate silent base audio: {e}")
        return None

    # Step 2: Generate and adjust each segment
    adjusted_segments = []
    inputs = ['-i', silent_base]
    filter_complex_parts = []

    for idx, seg in enumerate(segments):
        text = seg.get('english', '').strip()
        if not text:
            continue

        start = seg['start']
        end = seg['end']
        target_dur = end - start
        if target_dur <= 0:
            continue

        temp_seg_raw = os.path.join(temp_dir, f"seg_raw_{idx}.mp3")
        if generate_segment_tts(text, voice, temp_seg_raw):
            actual_dur = get_audio_duration(temp_seg_raw)
            if actual_dur <= 0:
                continue

            temp_seg_final = temp_seg_raw

            # Speed up if TTS is longer than original segment
            if actual_dur > target_dur:
                speed = actual_dur / target_dur
                speed = min(speed, 1.05)  # cap at 1.05x

                if speed > 2.0:
                    filters = ["atempo=2.0", f"atempo={speed/2.0:.4f}"]
                else:
                    filters = [f"atempo={speed:.4f}"]

                temp_seg_speed = os.path.join(temp_dir, f"seg_speed_{idx}.wav")
                try:
                    subprocess.run([
                        'ffmpeg', '-y', '-i', temp_seg_raw,
                        '-filter:a', ",".join(filters),
                        temp_seg_speed
                    ], capture_output=True, check=True)
                    temp_seg_final = temp_seg_speed
                except Exception as e:
                    logger.error(f"Failed to speed up segment {idx}: {e}")

            input_idx = len(inputs) // 2
            inputs.extend(['-i', temp_seg_final])
            delay_ms = int(start * 1000)
            filter_complex_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[a{input_idx}]")
            adjusted_segments.append(f"[a{input_idx}]")

    if not adjusted_segments:
        logger.warning("No valid TTS segments were generated.")
        return silent_base

    # Step 3: Mix all delayed segments on silent base
    mix_inputs = "".join(adjusted_segments)
    filter_graph = ";".join(filter_complex_parts)
    filter_graph += f";[0:a]{mix_inputs}amix=inputs={len(adjusted_segments)+1}:duration=first:dropout_transition=0:normalize=0[outa]"

    cmd = ['ffmpeg', '-y'] + inputs + [
        '-filter_complex', filter_graph,
        '-map', '[outa]',
        '-ar', '44100',
        '-ac', '2',
        output_audio_path
    ]

    try:
        logger.info("Mixing audio segments into final aligned audio track...")
        subprocess.run(cmd, capture_output=True, check=True)
        return output_audio_path
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg mixing failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return None


# ============================================================
# STEP 5: Vocal Separation + BGM
# ============================================================

def separate_vocals(audio_path, output_dir):
    """Separate vocals from BGM/effects using Demucs."""
    logger.info("Running Demucs vocal separator on audio...")
    try:
        import sys
        user_site = os.path.expanduser('~/.local/lib/python3.12/site-packages')
        if user_site not in sys.path:
            sys.path.append(user_site)

        venv_dir = os.path.dirname(sys.executable)
        demucs_venv = os.path.join(venv_dir, 'demucs.exe')
        if os.path.exists(demucs_venv):
            demucs_executable = demucs_venv
        else:
            demucs_executable = os.path.expanduser('~/.local/bin/demucs')
            if not os.path.exists(demucs_executable):
                demucs_executable = 'demucs'

        cmd = [demucs_executable, '-o', output_dir, audio_path]
        logger.info(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            logger.error(f"Demucs separation failed: {result.stderr}")
            return None

        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        bg_audio_path = os.path.join(output_dir, 'htdemucs', base_name, 'other.wav')

        if os.path.exists(bg_audio_path):
            logger.info(f"Vocals separated. BGM/SFX: {bg_audio_path}")
            return bg_audio_path
        else:
            logger.error(f"Demucs output not found at: {bg_audio_path}")
            return None

    except Exception as e:
        logger.error(f"Error running Demucs: {e}")
        return None


def download_default_bgm():
    """Download copyright-free background music if not present."""
    try:
        import requests
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets'))
        os.makedirs(assets_dir, exist_ok=True)
        bgm_path = os.path.join(assets_dir, 'cute-lofi.mp3')
        if not os.path.exists(bgm_path):
            logger.info("Downloading default copyright-free background music...")
            url = "https://raw.githubusercontent.com/jungcookgf/valentines-day/main/cute-lofi.mp3"
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            with open(bgm_path, 'wb') as f:
                f.write(r.content)
            logger.info(f"Downloaded default BGM: {bgm_path}")
        return bgm_path
    except Exception as e:
        logger.error(f"Error downloading default BGM: {e}")
        return None


# ============================================================
# STEP 5b: Merge Translated Audio with Original Video
# ============================================================

def merge_audio_with_video(video_path, audio_path, bg_music_path=None, output_path=None):
    """Mix original background audio (vocals removed) with English TTS + copyright-free BGM."""
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_english{ext}"

    logger.info("Merging translated audio with video...")

    new_bgm_path = download_default_bgm()

    try:
        is_sfx_separated = bg_music_path and bg_music_path.endswith('other.wav') and os.path.exists(bg_music_path)

        if new_bgm_path and os.path.exists(new_bgm_path):
            if is_sfx_separated:
                # SFX(90%) + English(60%) + BGM(8%)
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_path, '-i', bg_music_path, '-i', audio_path,
                    '-stream_loop', '-1', '-i', new_bgm_path,
                    '-filter_complex',
                    '[1:a]volume=0.9[sfx];[2:a]volume=0.6[fg];[3:a]volume=0.08[bg];[sfx][fg][bg]amix=inputs=3:duration=first:dropout_transition=0[outa]',
                    '-map', '0:v:0', '-map', '[outa]',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    output_path
                ]
            else:
                # English(60%) + BGM(8%)
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_path, '-i', audio_path,
                    '-stream_loop', '-1', '-i', new_bgm_path,
                    '-filter_complex',
                    '[1:a]volume=0.6[fg];[2:a]volume=0.08[bg];[fg][bg]amix=inputs=2:duration=first:dropout_transition=0[outa]',
                    '-map', '0:v:0', '-map', '[outa]',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    output_path
                ]
        else:
            if is_sfx_separated:
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_path, '-i', bg_music_path, '-i', audio_path,
                    '-filter_complex',
                    '[1:a]volume=1.0[sfx];[2:a]volume=1.0[fg];[sfx][fg]amix=inputs=2:duration=first:dropout_transition=0[outa]',
                    '-map', '0:v:0', '-map', '[outa]',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    output_path
                ]
            else:
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_path, '-i', audio_path,
                    '-map', '0:v:0', '-map', '1:a',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    output_path
                ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"FFmpeg merge failed: {result.stderr}")
            return None

        logger.info(f"Video with mixed audio created: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error merging audio: {e}")
        return None


# ============================================================
# STEP 6: Generate Subtitle Files (SRT)
# ============================================================

def _format_srt_time(seconds):
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_subtitles(segments, output_dir=None, filename="subtitles"):
    """Generate SRT subtitle files for both Chinese and English."""
    if output_dir is None:
        output_dir = tempfile.gettempdir()

    os.makedirs(output_dir, exist_ok=True)

    zh_srt_path = os.path.join(output_dir, f"{filename}_chinese.srt")
    en_srt_path = os.path.join(output_dir, f"{filename}_english.srt")
    dual_srt_path = os.path.join(output_dir, f"{filename}_dual.srt")

    zh_lines = []
    en_lines = []
    dual_lines = []

    for i, seg in enumerate(segments, 1):
        start = _format_srt_time(seg['start'])
        end = _format_srt_time(seg['end'])
        zh_text = seg.get('chinese', '')
        en_text = seg.get('english', '')

        zh_lines.append(f"{i}\n{start} --> {end}\n{zh_text}\n")
        en_lines.append(f"{i}\n{start} --> {end}\n{en_text}\n")
        dual_lines.append(f"{i}\n{start} --> {end}\n{zh_text}\n{en_text}\n")

    with open(zh_srt_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(zh_lines))
    with open(en_srt_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(en_lines))
    with open(dual_srt_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(dual_lines))

    logger.info(f"Subtitle files generated: {zh_srt_path}, {en_srt_path}, {dual_srt_path}")

    return {
        'chinese': zh_srt_path,
        'english': en_srt_path,
        'dual': dual_srt_path
    }


def burn_subtitles_into_video(video_path, srt_path, output_path=None, language='english'):
    """Burn (hardcode) subtitles into the video."""
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_subtitled{ext}"

    logger.info(f"Burning {language} subtitles into video...")

    try:
        if language == 'chinese':
            style = "FontName=Noto Sans SC,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2,MarginV=60"
        elif language == 'dual':
            style = "FontName=Noto Sans SC,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2,MarginV=50"
        else:
            style = "FontName=Arial,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2,MarginV=60"

        escaped_srt = srt_path.replace('\\', '/').replace(':', '\\:')

        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', f"subtitles='{escaped_srt}':force_style='{style}'",
            '-c:a', 'copy',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"Subtitle burn failed: {result.stderr}")
            return None

        logger.info(f"Video with burned subtitles: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error burning subtitles: {e}")
        return None


# ============================================================
# UTILITY: Trim video to max 59s for Reels
# ============================================================

def trim_video_to_59s(video_path, output_dir):
    """Trims video to 59 seconds if longer."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0', video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        duration = float(res.stdout.strip())

        if duration > 59.0:
            logger.info(f"Video is {duration:.2f}s. Trimming to 59s...")
            base = os.path.basename(video_path)
            trimmed_path = os.path.join(output_dir, f"trimmed_{base}")
            trim_cmd = [
                'ffmpeg', '-y', '-i', video_path,
                '-ss', '0', '-t', '59',
                '-c:v', 'libx264', '-c:a', 'aac', '-crf', '18',
                trimmed_path
            ]
            subprocess.run(trim_cmd, capture_output=True, check=True, timeout=300)
            logger.info(f"Video trimmed: {trimmed_path}")
            return trimmed_path
        else:
            logger.info(f"Video is {duration:.2f}s. No trimming needed.")
            return video_path
    except Exception as e:
        logger.error(f"Error trimming video: {e}")
        return video_path


# ============================================================
# MAIN TRANSLATION PIPELINE
# ============================================================

def translate_video(video_path, output_dir=None, burn_subtitles=True, subtitle_language='dual'):
    """
    Complete pipeline: Chinese video -> English dubbed video with subtitles.

    Returns:
        Dict with paths to all generated files, or None on failure
    """
    logger.info("=== Starting Translation Pipeline ===")
    logger.info(f"Input video: {video_path}")

    if output_dir is None:
        output_dir = os.path.dirname(video_path) or '.'

    os.makedirs(output_dir, exist_ok=True)

    # Trim if needed
    original_video_path = video_path
    video_path = trim_video_to_59s(video_path, output_dir)

    temp_files = []
    if video_path != original_video_path:
        temp_files.append(video_path)

    try:
        # Step 1: Extract audio
        logger.info("Step 1/6: Extracting audio...")
        audio_path = extract_audio(video_path)
        if not audio_path:
            raise Exception("Failed to extract audio from video")
        temp_files.append(audio_path)

        # Separate vocals from BGM
        bg_music_path = separate_vocals(audio_path, output_dir)
        if bg_music_path:
            temp_files.append(bg_music_path)
        else:
            logger.warning("Demucs separation failed. Using original audio as background.")
            bg_music_path = audio_path

        # Step 2: Transcribe Chinese
        logger.info("Step 2/6: Transcribing Chinese audio...")
        use_api = bool(os.environ.get('OPENAI_API_KEY'))
        segments = transcribe_chinese_audio(audio_path, use_api=use_api)
        if not segments:
            raise Exception("Failed to transcribe audio")
        logger.info(f"Transcribed {len(segments)} segments")

        # Step 3: Translate to English
        logger.info("Step 3/6: Translating to English...")
        translated = translate_segments_to_english(segments)
        if not translated:
            raise Exception("Failed to translate segments")

        # Step 4: Generate English TTS
        logger.info("Step 4/6: Generating English TTS...")
        tts_path = os.path.join(output_dir, "tts_english.mp3")
        tts_audio = generate_english_tts(translated, tts_path, video_path=video_path)
        if not tts_audio:
            raise Exception("Failed to generate TTS audio")
        temp_files.append(tts_audio)

        # Step 5: Merge audio
        logger.info("Step 5/6: Merging translated audio with video...")
        english_video = merge_audio_with_video(
            video_path, tts_audio,
            bg_music_path=bg_music_path,
            output_path=os.path.join(output_dir, "video_english.mp4")
        )
        if not english_video:
            raise Exception("Failed to merge audio with video")
        temp_files.append(english_video)

        # Step 6: Generate subtitles
        logger.info("Step 6/6: Generating subtitles...")
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        srt_files = generate_subtitles(translated, output_dir, base_name)

        final_video = english_video

        # Optionally burn subtitles
        if burn_subtitles and srt_files.get(subtitle_language):
            subtitled_video = burn_subtitles_into_video(
                english_video,
                srt_files[subtitle_language],
                os.path.join(output_dir, f"{base_name}_final.mp4"),
                language=subtitle_language
            )
            if subtitled_video:
                final_video = subtitled_video

        # Cleanup temp files
        for f in temp_files:
            if f != final_video and f != bg_music_path and os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

        result = {
            'original': video_path,
            'english_video': final_video,
            'subtitles': srt_files,
            'segments': translated,
            'segment_count': len(translated)
        }

        logger.info("=== Translation Complete ===")
        logger.info(f"English video: {final_video}")
        return result

    except Exception as e:
        logger.error(f"Translation pipeline failed: {e}")
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        return None


# ============================================================
# CLI Entry Point
# ============================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python translator.py <video_path> [output_dir]")
        sys.exit(1)

    video = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else None

    result = translate_video(video, out_dir)

    if result:
        print(f"\n✅ Translation successful!")
        print(f"English video: {result['english_video']}")
        print(f"Segments translated: {result['segment_count']}")
    else:
        print("\n❌ Translation failed!")
        sys.exit(1)
