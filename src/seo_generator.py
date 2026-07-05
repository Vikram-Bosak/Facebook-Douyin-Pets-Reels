"""
SEO Metadata Generator for Pet Animal Videos
Generates viral English SEO metadata (title, description, hashtags) for US audience.
Uses OpenAI GPT for AI generation with template-based fallback.
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


def generate_seo_metadata(filename, media_type='reel'):
    """
    Generates SEO title, description, and hashtags for pet animal videos.
    Optimized for US audience with English content.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.warning("OPENAI_API_KEY not found. Using fallback metadata generator.")
        return generate_fallback_metadata(filename)

    base_url = os.environ.get('OPENAI_API_BASE_URL')
    model = os.environ.get('OPENAI_API_MODEL', 'gpt-3.5-turbo')

    if base_url:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

    topic = clean_filename(filename)

    content_type_str = "Facebook Reel" if media_type == 'reel' else "Facebook Photo Post"
    video_str = "short vertical video (Facebook Reel / YouTube Shorts)" if media_type == 'reel' else "stunning pet photo"
    hashtag_str = "#Reels #viral" if media_type == 'reel' else "#PhotoOfTheDay #viral"

    system_prompt = (
        "You are an expert Social Media Manager specializing in viral pet animal content "
        "for Facebook and YouTube Shorts targeting a United States audience. "
        "Your goal is to maximize engagement, click-through rate, and virality among American viewers. "
        "All generated titles, descriptions, and hashtags must be in English. "
        "Use emotionally engaging words, curiosity gaps, and trending formats popular on US social media. "
        "Focus on cuteness, funny moments, and heartwarming pet content."
    )

    user_prompt = f"""
Generate viral SEO metadata for a {video_str} about: "{topic}".

Requirements:
1. Title: Short, catchy, uses emotional words, includes relevant emojis. Written in English. Max 60 characters.
   Focus on: cute pets, funny animals, heartwarming moments, pet tricks, adorable reactions.
2. Description: 1-2 short sentences in English that create curiosity and encourage engagement. Use American English.
   Add a CTA (Like, Follow, Share, Comment).
3. Hashtags: 5-8 highly relevant and trending hashtags for US audience. Mix viral tags with pet-specific tags. Include {hashtag_str}.

US Audience Pet Hashtag Guidelines:
- Always include popular US viral tags: #viral #trending #fyp #foryou #explore #reels #shorts
- Add pet-specific tags: #pets #animals #dogs #cats #cute #adorable #funny #petsoftiktok
- Use English hashtags for maximum reach in the US market

Format the output exactly as JSON:
{{
    "title": "...",
    "description": "...",
    "hashtags": "#tag1 #tag2 ..."
}}
"""

    try:
        params = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "timeout": 45.0
        }
        if "gpt-" in model:
            params["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**params)

        result_json = response.choices[0].message.content.strip()

        # Clean markdown code blocks
        if result_json.startswith("```"):
            result_json = re.sub(r'^```(?:json)?\n', '', result_json)
            result_json = re.sub(r'\n```$', '', result_json)
            result_json = result_json.strip()

        data = json.loads(result_json)

        return {
            'title': data.get('title', topic.title()),
            'description': data.get('description', f"Incredible pet video! You need to see this!"),
            'hashtags': data.get('hashtags', "#viral #trending #pets #animals #cute #reels #shorts")
        }

    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        return generate_fallback_metadata(filename)


def generate_fallback_metadata(filename):
    """Template-based fallback SEO metadata with pet-specific categories."""

    def get_deterministic_choice(fn, lst):
        h = int(hashlib.md5(fn.encode('utf-8')).hexdigest(), 16)
        return lst[h % len(lst)]

    topic = clean_filename(filename)
    topic_title = topic.title()

    words = [w.lower() for w in re.findall(r'\w+', topic) if len(w) > 2]
    stopwords = {
        'the', 'and', 'for', 'you', 'with', 'from', 'this', 'that',
        'are', 'was', 'were', 'has', 'have', 'had', 'its', 'their', 'our',
        'your', 'his', 'her', 'she', 'him', 'them', 'who', 'whom', 'which'
    }
    keywords = [w for w in words if w not in stopwords]

    # ---- Pet Category Detection ----
    dog_keywords = {
        'dog', 'puppy', 'dogs', 'puppies', 'shiba', 'husky', 'golden',
        'retriever', 'bulldog', 'poodle', 'corgi', 'chihuahua', 'terrier',
        'beagle', 'labrador', 'maltese', 'pomeranian', 'samoyed'
    }
    cat_keywords = {
        'cat', 'kitten', 'cats', 'kittens', 'persian', 'siamese', 'ragdoll',
        'bengal', 'maine', 'coons', 'scottish', 'fold', 'sphynx', 'tabby'
    }
    cute_keywords = {
        'cute', 'adorable', 'sweet', 'baby', 'tiny', 'little', 'fluffy',
        'soft', 'cuddly', 'sweetheart', 'lovely', 'precious'
    }
    funny_keywords = {
        'funny', 'hilarious', 'comedy', 'laugh', 'joke', 'meme',
        'fail', 'silly', 'stupid', 'goofy', 'dork', 'derp'
    }
    wild_keywords = {
        'panda', 'fox', 'raccoon', 'hedgehog', 'hamster', 'rabbit', 'bunny',
        'parrot', 'bird', 'turtle', 'fish', 'squirrel', 'otter', 'deer'
    }

    is_dog = any(k in dog_keywords for k in keywords)
    is_cat = any(k in cat_keywords for k in keywords)
    is_cute = any(k in cute_keywords for k in keywords)
    is_funny = any(k in funny_keywords for k in keywords)
    is_wild = any(k in wild_keywords for k in keywords)

    common_viral_tags = ['#viral', '#trending', '#fyp', '#foryou', '#explore', '#reels', '#shorts']

    # ---- Pet-Specific Templates ----
    if is_dog and is_funny:
        titles = [
            "This Dog Is Funnier Than Most Humans! 😂",
            "Wait For It... This Dog Just Did THE FUNNIEST Thing! 🤣",
            "Dogs Being Derpy: This One Wins! 🐕",
            "This Dog's Reaction Is PRICELESS! 🤯",
            "POV: Your Dog Just Broke the Internet! 🚨"
        ]
        descriptions = [
            "I can't stop laughing at this dog! Share with someone who needs a good laugh! 😂",
            "This is hands down the funniest dog video you'll see today! Follow for daily laughs! 🐾",
            "Warning: This video may cause uncontrollable laughter! Tag a dog lover! 🐕"
        ]
        cat_tags = ['#dog', '#dogs', '#funny', '#dogsoftiktok', '#funnydogs', '#puppy', '#dogsbeingdogs', '#derpy']
    elif is_dog:
        titles = [
            "This Dog Is the CUTEST Thing Ever! 🐕",
            "My Heart Can't Handle This Dog! So Precious! 😍",
            "You Won't BELIEVE How Adorable This Dog Is! 🥺",
            "The Most Beautiful Dog You'll See Today! ✨",
            "This Puppy Just Stole My Heart! 💕"
        ]
        descriptions = [
            "This is the most adorable dog video on the internet right now! Must share! 💕",
            "Warning: Extreme cuteness ahead! This dog will make your day! 🐾",
            "The purest form of happiness captured on camera. Share the love! 😍"
        ]
        cat_tags = ['#dog', '#dogs', '#puppy', '#cute', '#adorable', '#doglovers', '#goldenretriever', '#dogsoftiktok']
    elif is_cat and is_funny:
        titles = [
            "This Cat Just Did Something UNTHINKABLE! 😱",
            "Cats Are Weird: This One Proves It! 🤣",
            "Wait For It... Cat Fails Never Get Old! 😂",
            "This Cat's Reaction Is HILARIOUS! 🐱",
            "CATS: Natural Born Comedians! 😹"
        ]
        descriptions = [
            "This cat just proved they're the funniest pets ever! Share with a cat person! 😂",
            "I laughed so hard at this! Cats are literally comedians in disguise! 🐱",
            "If you think cats are boring, this video will change your mind! Follow for more! 😹"
        ]
        cat_tags = ['#cat', '#cats', '#funny', '#catsoftiktok', '#funnycat', '#catsbeingcats', '#catmemes', '#cathumor']
    elif is_cat:
        titles = [
            "This Cat Is So PRECIOUS I Can't Handle It! 🐱",
            "The Most Beautiful Cat You'll Ever See! 😻",
            "Cuteness Overload: This Cat Is EVERYTHING! 🥺",
            "You Need to See This Adorable Cat Right Now! 💕",
            "This Kitty Is Pure Perfection! ✨"
        ]
        descriptions = [
            "This is the cutest cat video on the internet! Cat lovers, you NEED to see this! 😻",
            "Prepare for maximum cuteness! This cat will brighten your entire day! 🐱",
            "The most adorable moment you'll see today. Share with every cat lover you know! 💕"
        ]
        cat_tags = ['#cat', '#cats', '#kitten', '#cute', '#adorable', '#catlovers', '#catsoftiktok', '#kittens']
    elif is_cute:
        titles = [
            "This Pet Is SO CUTE It Should Be Illegal! 🥺",
            "Maximum Cuteness Achieved! You Can't Look Away! 😍",
            "The Cutest Thing You'll See All Day! 💕",
            "Warning: This Video May Cause Heart Melting! 🫠",
            "I'm Not Crying, YOU'RE Crying! So Adorable! 😭"
        ]
        descriptions = [
            "This is peak cuteness! You have to share this with someone who loves animals! 💕",
            "My heart just exploded watching this! The sweetest video ever! 🥺",
            "If this doesn't make you smile, nothing will! Follow for more adorable content! 😍"
        ]
        cat_tags = ['#cute', '#adorable', '#pets', '#animals', '#sweet', '#precious', '#lovely', '#heartwarming']
    elif is_funny:
        titles = [
            "Pets Being HILARIOUS! This Is Comedy Gold! 😂",
            "This Animal's Reaction Is PRICELESS! 🤣",
            "Funniest Pet Moment of the Year! Watch Till End! 🏆",
            "I Can't Stop Watching This! Too Funny! 🤣",
            "Wait For It... The Ending Is EVERYTHING! 😱"
        ]
        descriptions = [
            "This is the funniest pet video you'll see this week! Tag someone who needs to laugh! 😂",
            "Warning: Watching this in public may cause loud laughter! Share the joy! 🤣",
            "Pets are nature's comedians! This video proves it! Follow for daily laughs! 🏆"
        ]
        cat_tags = ['#funny', '#pets', '#animals', '#comedy', '#hilarious', '#laugh', '#viral', '#meme']
    elif is_wild:
        titles = [
            "This Animal Is UNREAL! Nature Is Amazing! 🌿",
            "You Won't BELIEVE This Wildlife Moment! 🤯",
            "Nature's Most Beautiful Creature Caught on Camera! ✨",
            "This Wild Animal Just Did Something Incredible! 🔥",
            "The Wonders of Nature in One Video! 🌎"
        ]
        descriptions = [
            "Nature never stops surprising us! This incredible animal moment will blow your mind! 🌿",
            "The beauty of wildlife captured in one stunning video! Share the wonder! ✨",
            "This is why animals are amazing! Watch till the end for a surprise! 🔥"
        ]
        cat_tags = ['#wildlife', '#animals', '#nature', '#wild', '#beautiful', '#naturelovers', '#amazing', '#cute']
    else:
        titles = [
            "Wait For It... This Pet Is INCREDIBLE! 😱",
            "POV: You Just Witnessed Pure Cuteness! 🤯",
            "This Animal Video Is Going VIRAL Right Now! 🔥",
            "You Won't BELIEVE What This Pet Just Did! 🚨",
            "The Most Adorable Animal Moment EVER! 💥"
        ]
        descriptions = [
            "This pet video is breaking the internet! You have to see this to believe it! 💥",
            "The most incredible animal footage you'll see today. Share with your friends! 👇",
            "This moment is absolutely unreal. Don't miss this! 🔥"
        ]
        cat_tags = ['#pets', '#animals', '#cute', '#adorable', '#viral', '#trending', '#fyp', '#amazing']

    # ---- Build Hashtags ----
    title_template = get_deterministic_choice(filename, titles)
    desc_template = get_deterministic_choice(filename, descriptions)

    title = title_template.format(topic=topic_title)
    if len(title) > 60:
        title = title[:57] + "..."

    base_desc = desc_template.format(topic=topic_title)

    # US CTAs
    ctas = [
        "Like & Share if this made your day! ❤️",
        "Follow for more cute pets! 📲",
        "Tag a pet lover who needs to see this! 👇",
        "Drop a comment if you agree! 💬",
        "Share this with your friends! ✈️",
        "Smash that like button! 👍",
        "Don't forget to follow for daily cuteness! 🔔"
    ]
    cta = get_deterministic_choice(filename + "_cta", ctas)
    description = f"{base_desc}\n\n{cta}"

    # Pet-specific keyword database
    KEYWORDS_DATABASE = {
        'dog': ['dogs', 'dogsoftiktok', 'doglovers', 'puppylove'],
        'puppy': ['puppies', 'puppylove', 'puppyeyes', 'puppiesofinstagram'],
        'cat': ['cats', 'catsoftiktok', 'catlovers', 'kitten'],
        'kitten': ['kittens', 'kittenssoftiktok', 'kittenlove', 'babykittens'],
        'golden': ['goldenretriever', 'goldendoodle', 'goldenlove'],
        'husky': ['huskies', 'huskiesoftiktok', 'huskylife', 'huskylove'],
        'shiba': ['shiba', 'shibainu', 'shibasofinstagram', 'shibalove'],
        'corgi': ['corgis', 'corgisofinstagram', 'corgilove', 'corgination'],
        'panda': ['pandas', 'pandacutest', 'pandalove', 'cutepanda'],
        'fox': ['foxes', 'foxlove', 'foxlife', 'cute fox'],
        'bunny': ['bunnies', 'bunnylove', 'rabbitsofinstagram', 'bunnylife'],
        'hamster': ['hamsters', 'hamsterlove', 'hamsterlife', 'cutehamster'],
        'cute': ['cutepets', 'cutest', 'adorable', 'cutenessoverload'],
        'funny': ['funnypets', 'funnyanimals', 'funnydogs', 'funnycat'],
        'baby': ['babypets', 'babyanimals', 'babypuppy', 'babykitten'],
        'fluffy': ['fluffypets', 'fluffy', 'fluffycat', 'fluffydog'],
    }

    hash_tags_set = {'#viral', '#trending', '#fyp', '#foryou', '#explore', '#reels', '#shorts'}
    for tag in cat_tags:
        hash_tags_set.add(tag.lower())
    for k in keywords:
        if k in KEYWORDS_DATABASE:
            for extra in KEYWORDS_DATABASE[k]:
                hash_tags_set.add(f"#{extra}")
    for k in keywords:
        if len(k) > 2:
            hash_tags_set.add(f"#{k}")

    ordered_tags = ['#viral', '#trending', '#fyp', '#reels', '#shorts']
    for tag in sorted(hash_tags_set):
        if tag not in ordered_tags:
            ordered_tags.append(tag)

    final_tags = ordered_tags[:10]
    hashtags_str = " ".join(final_tags)

    return {
        'title': title,
        'description': description,
        'hashtags': hashtags_str
    }


def format_caption(seo_metadata):
    """Combines title, description, and hashtags into final Facebook caption format."""
    return f"{seo_metadata['title']}\n\n{seo_metadata['description']}\n\n{seo_metadata['hashtags']}"
