import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def get_youtube_client():
    token_json_str = os.environ.get('YOUTUBE_TOKEN_JSON')
    creds = None
    
    if token_json_str:
        try:
            token_data = json.loads(token_json_str)
            creds = Credentials.from_authorized_user_info(token_data)
        except Exception as e:
            print(f"Error parsing YOUTUBE_TOKEN_JSON from env: {e}")
    
    # Fallback to local file for testing
    if not creds and os.path.exists('youtube_token.json'):
        try:
            creds = Credentials.from_authorized_user_file('youtube_token.json')
        except Exception as e:
            print(f"Error reading youtube_token.json: {e}")
            
    if not creds:
        raise Exception("YouTube credentials not found. Please set YOUTUBE_TOKEN_JSON.")
        
    return build('youtube', 'v3', credentials=creds)

def upload_to_youtube(video_path, title, description):
    print("Initializing YouTube upload...")
    youtube = get_youtube_client()
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['viral', 'trending', 'fyp', 'foryou', 'shorts', 'reels', 'entertainment', 'amazing', 'incredible', 'mustsee'],
            'categoryId': '24' # Entertainment
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }
    
    # Call the API's videos.insert method to create and upload the video.
    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=MediaFileUpload(video_path, chunksize=1024*1024, resumable=True)
    )
    
    print("Uploading video to YouTube Shorts...")
    response = None
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%...")
            
    video_id = response.get('id')
    video_url = f"https://www.youtube.com/shorts/{video_id}"
    print(f"Upload Complete! Video URL: {video_url}")
    return video_url
