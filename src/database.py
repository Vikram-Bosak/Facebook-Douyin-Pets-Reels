import sqlite3
import os
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database')
DB_PATH = os.path.join(DB_DIR, 'reels.db')

def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            seo_title TEXT,
            description TEXT,
            hashtags TEXT,
            upload_time DATETIME,
            facebook_url TEXT,
            status TEXT DEFAULT 'pending',
            file_hash TEXT UNIQUE
        )
    ''')
    
    # Run migration to add attempts column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE reels ADD COLUMN attempts INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        # Column already exists
        pass
        
    # Run migration to add media_type column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE reels ADD COLUMN media_type TEXT DEFAULT 'reel'")
    except sqlite3.OperationalError:
        # Column already exists
        pass
        
    conn.commit()
    conn.close()

def is_duplicate(filename, file_hash=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if file_hash:
        cursor.execute('SELECT status FROM reels WHERE filename = ? OR file_hash = ?', (filename, file_hash))
    else:
        cursor.execute('SELECT status FROM reels WHERE filename = ?', (filename,))
        
    rows = cursor.fetchall()
    conn.close()
    
    for row in rows:
        status = row[0]
        if status in ('uploaded', 'failed'):
            return True
    return False

def insert_media(filename, file_hash=None, media_type='reel'):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO reels (filename, file_hash, status, attempts, media_type)
            VALUES (?, ?, 'pending', 0, ?)
        ''', (filename, file_hash, media_type))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def update_reel_metadata(filename, seo_title, description, hashtags):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE reels 
        SET seo_title = ?, description = ?, hashtags = ?
        WHERE filename = ?
    ''', (seo_title, description, hashtags, filename))
    conn.commit()
    conn.close()

def mark_reel_uploaded(filename, facebook_url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE reels 
        SET status = 'uploaded', facebook_url = ?, upload_time = ?, attempts = 0
        WHERE filename = ?
    ''', (facebook_url, datetime.now().isoformat(), filename))
    conn.commit()
    conn.close()

def mark_reel_failed(filename):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE reels 
        SET status = 'failed'
        WHERE filename = ?
    ''', (filename,))
    conn.commit()
    conn.close()

def get_daily_upload_count(media_type='reel'):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT COUNT(*) FROM reels 
        WHERE status = 'uploaded' AND date(upload_time) = ? AND media_type = ?
    ''', (today, media_type))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_reel_status(filename, file_hash=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if file_hash:
        cursor.execute('SELECT status, attempts FROM reels WHERE filename = ? OR file_hash = ?', (filename, file_hash))
    else:
        cursor.execute('SELECT status, attempts FROM reels WHERE filename = ?', (filename,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None, 0

def increment_attempts(filename):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE reels 
        SET attempts = attempts + 1
        WHERE filename = ?
    ''', (filename,))
    cursor.execute('SELECT attempts FROM reels WHERE filename = ?', (filename,))
    result = cursor.fetchone()
    attempts = result[0] if result else 0
    conn.commit()
    conn.close()
    return attempts

def reset_attempts(filename):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE reels SET attempts = 0 WHERE filename = ?', (filename,))
    conn.commit()
    conn.close()

init_db()
