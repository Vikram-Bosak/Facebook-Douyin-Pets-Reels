"""
SEO Metadata Generator for Pet Animal Videos
Generates viral English SEO metadata (title, description, hashtags) for US audience.
Uses NVIDIA API (free) for AI generation with template-based fallback.
"""

import os
import re
import json
import hashlib

try:
    from .logger import logger
except ImportError:
    from logger import logger


def clean_filename(filename):
    """Remove extension and clean up filename for topic extraction."""
    name_without_ext = os.path.splitext(filename)[0]
    cleaned = re.sub(r'[-_]', ' ', name_without_ext)
    return cleaned.strip()


def generate_seo_metadata(filename, media_type='reel', translated_text=''):
    """
    Generates SEO title, description, and hashtags for pet animal videos.
    Uses NVIDIA API (free) for AI-generated content-specific SEO.
    """
    nvidia_key = os.environ.get('NVIDIA_API_KEY')
    
    if nvidia_key:
        return generate_nvidia_seo(filename, nvidia_key, translated_text)
    else:
        logger.warning("NVIDIA_API_KEY not found. Using translated content for SEO.")
        return generate_fallback_metadata(filename, translated_text)


def generate_nvidia_seo(filename, api_key, translated_text=''):
    """Use NVIDIA Nemotron LLM for viral SEO generation."""
    try:
        import openai
        
        client = openai.OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            timeout=30.0
        )
        
        topic = clean_filename(filename)
        content_info = f"Video filename: {topic}"
        if translated_text:
            content_info += f"\nVideo content (translated from Chinese): {translated_text[:200]}"
        
        prompt = f"""Generate viral SEO metadata for a Facebook Reel about pets/animals.

{content_info}

Requirements:
1. Title: Short, catchy, uses emotional words, includes relevant emojis. Written in English. Max 60 characters.
   Focus on: cute pets, funny animals, heartwarming moments.
2. Description: 1-2 short sentences in English that create curiosity and encourage engagement.
   Add a CTA (Like, Follow, Share).
3. Hashtags: 5-8 trending hashtags for US audience. Include #viral #trending #fyp #reels #shorts.

Return ONLY valid JSON:
{{"title": "...", "description": "...", "hashtags": "#tag1 #tag2 ..."}}
"""
        
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            top_p=0.9,
            max_tokens=200
        )
        
        raw_text = response.choices[0].message.content.strip()
        
        # Extract JSON
        json_match = re.search(r'\{.*?\}', raw_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            return {
                'title': data.get('title', topic.title())[:60],
                'description': data.get('description', 'Amazing pet video! 🔥'),
                'hashtags': data.get('hashtags', '#viral #trending #fyp #reels #shorts')
            }
        
        # Fallback if JSON parsing fails
        return generate_fallback_metadata(filename, translated_text)
        
    except Exception as e:
        logger.error(f"NVIDIA SEO generation failed: {e}")
        return generate_fallback_metadata(filename, translated_text)


def generate_fallback_metadata(filename, translated_text=''):
    """Template-based fallback SEO metadata using translated content for uniqueness."""
    
    # Use translated text to understand video content
    content_lower = translated_text.lower() if translated_text else ''
    
    # Detect animal type from translated text
    is_dog = any(w in content_lower for w in ['dog', 'puppy', 'pup', 'woof', 'bark'])
    is_cat = any(w in content_lower for w in ['cat', 'kitten', 'meow', 'purr', 'kitty'])
    is_cute = any(w in content_lower for w in ['cute', 'adorable', 'sweet', 'fluffy', 'precious'])
    is_funny = any(w in content_lower for w in ['funny', 'laugh', 'silly', 'goofy', 'hilarious'])
    
    # Create engaging title based on content
    if is_dog and is_funny:
        titles = [
            "This Dog Is HILARIOUS! Wait Till You See This! 😂",
            "Funniest Dog Moment EVER! You Need to See This! 🐕",
            "LOL! This Dog Just Did Something Amazing! 🤣",
        ]
    elif is_dog:
        titles = [
            "This Dog Is SO CUTE It Will Melt Your Heart! 🐕",
            "Adorable Dog Moment That Will Make Your Day! 😍",
            "Look At This Precious Pup! Pure Cuteness! 💕",
        ]
    elif is_cat and is_funny:
        titles = [
            "This Cat Is FUNNIER Than You Think! 😹",
            "LOL! Cats Being Cats - Priceless Moments! 🐱",
            "Cat Fails Never Get Old! Watch This! 😂",
        ]
    elif is_cat:
        titles = [
            "This Cat Is Absolutely GORGEOUS! 😻",
            "Most Beautiful Cat You'll See Today! 🐱",
            "Precious Kitty Moment - So Sweet! 💕",
        ]
    elif is_cute:
        titles = [
            "This Pet Is SO CUTE It Should Be Illegal! 🥺",
            "Maximum Cuteness Achieved! Can't Look Away! 😍",
            "The CUTEST Thing You'll See Today! 💕",
        ]
    else:
        titles = [
            "Amazing Pet Moment You NEED to See! 🔥",
            "Incredible Animal Video Going VIRAL! 🚨",
            "This Will Make Your Day! Pure Joy! ✨",
        ]
    
    def get_deterministic_choice(fn, lst):
        h = int(hashlib.md5(fn.encode('utf-8')).hexdigest(), 16)
        return lst[h % len(lst)]
    
    title = get_deterministic_choice(filename, titles)
    
    # Generate description from translation
    if translated_text and len(translated_text) > 10:
        description = f"{translated_text[:150]}\n\nLike & Share if this made your day! ❤️"
    else:
        description = "This pet video is breaking the internet! You have to see this to believe it! 💥\n\nLike & Share if this made your day! ❤️"
    
    # Generate hashtags based on content
    hashtags = ['#viral', '#trending', '#fyp', '#reels', '#shorts']
    if is_dog:
        hashtags.extend(['#dog', '#dogs', '#puppy', '#dogsoftiktok'])
    elif is_cat:
        hashtags.extend(['#cat', '#cats', '#kitten', '#catsoftiktok'])
    else:
        hashtags.extend(['#pets', '#animals', '#cute', '#adorable'])
    
    hashtags_str = ' '.join(hashtags[:10])
    
    return {
        'title': title,
        'description': description,
        'hashtags': hashtags_str
    }


def format_caption(seo_metadata):
    """Combines title, description, and hashtags into final Facebook caption format."""
    return f"{seo_metadata['title']}\n\n{seo_metadata['description']}\n\n{seo_metadata['hashtags']}"
