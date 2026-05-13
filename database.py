import sqlite3
import os

DB_PATH = "led_remote.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(initial_playlists=None, initial_songs=None):
    """Initialize the database and seed it with hardcoded data if empty."""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS moods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            uri TEXT NOT NULL,
            hex_color TEXT NOT NULL,
            is_song BOOLEAN NOT NULL
        )
    ''')
    
    # Check if empty
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM moods')
    if cursor.fetchone()[0] == 0:
        print("Seeding database with initial data...")
        if initial_playlists:
            for name, data in initial_playlists.items():
                conn.execute(
                    'INSERT INTO moods (name, uri, hex_color, is_song) VALUES (?, ?, ?, ?)',
                    (name, data['uri'], data['hex'], False)
                )
        if initial_songs:
            for name, data in initial_songs.items():
                conn.execute(
                    'INSERT INTO moods (name, uri, hex_color, is_song) VALUES (?, ?, ?, ?)',
                    (name, data['uri'], data['hex'], True)
                )
        conn.commit()
    conn.close()

def get_all_moods():
    conn = get_db_connection()
    moods = conn.execute('SELECT * FROM moods').fetchall()
    conn.close()
    return [dict(m) for m in moods]

def get_mood_by_name(name):
    conn = get_db_connection()
    mood = conn.execute('SELECT * FROM moods WHERE name = ?', (name,)).fetchone()
    conn.close()
    return dict(mood) if mood else None

def add_mood(name, uri, hex_color, is_song):
    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO moods (name, uri, hex_color, is_song) VALUES (?, ?, ?, ?)',
            (name, uri, hex_color, is_song)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_mood(mood_id, name, uri, hex_color):
    conn = get_db_connection()
    conn.execute(
        'UPDATE moods SET name = ?, uri = ?, hex_color = ? WHERE id = ?',
        (name, uri, hex_color, mood_id)
    )
    conn.commit()
    conn.close()

def delete_mood(mood_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM moods WHERE id = ?', (mood_id,))
    conn.commit()
    conn.close()
