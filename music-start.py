from flask import Flask, render_template, request, jsonify
import database
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import time
import pyautogui
import threading
import asyncio
from bleak import BleakClient
import mss
import pygetwindow as gw
import queue
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager, GlobalSystemMediaTransportControlsSessionPlaybackStatus

app = Flask(__name__)

# --- CONFIGURATION ---
MAC_ADDR = os.getenv("LED_MAC_ADDR", "XX:XX:XX:XX:XX:XX")
CHAR_UUID = os.getenv("LED_CHAR_UUID", "0000fff3-0000-1000-8000-00805f9b34fb")


# --- GLOBAL STATE ---
color_queue = queue.Queue()
current_color_hex = "7e0705031db95410ef" # Default Spotify Green
SYNC_MODE = "smart" # Options: "instant", "smart"
BLE_CONNECTED = False

class LEDCommand:
    """Models LED settings effectively."""
    
    @staticmethod
    def color(r, g, b):
        """Generates a static color command."""
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        return f"7e070503{r:02x}{g:02x}{b:02x}10ef"
        
    @staticmethod
    def mode(mode_id, speed):
        """
        Generates a dynamic mode command. 
        Usually mode_id ranges from 128 (0x80) to 159 (0x9f) for typical BLE controllers.
        Speed ranges from 1 (fastest) to 31 (slowest).
        """
        mode_id = max(0, min(255, int(mode_id)))
        speed = max(0, min(255, int(speed)))
        return f"7e0503{mode_id:02x}{speed:02x}ffef"

# --- UPDATED CONFIGURATION ---
PLAYLISTS = {
    "hype": {
        "uri": "spotify:playlist:0hBSTE8N0qNbBrXyVH5BUm", 
        "hex": "7e070503ff000010ef"  # Deep Red
    },
    "chill": {
        "uri": "spotify:playlist:3TKkZAP3k6FVMfnFqUMvpL", 
        "hex": "7e0705030000ff10ef"  # Cool Blue
    }, 
    "party": {
        "uri": "spotify:playlist:37i9dQZF1EIcsHAaTPt2VN", 
        "hex": "7e070503ff00ff10ef"  # Purple/Magenta
    },
    "italy": {
        "uri": "spotify:playlist:2QWl1UykngbHZoeoJsSP90", 
        "hex": "7e07050300ff0010ef"  # Green
    },
    "basketball": {
        "uri": "spotify:playlist:2Qd1EZ4mInBWokQPJu08e4",
        "hex": "7e070503ff8c0010ef"  # Basketball Orange
    },
    "brent and frank": {
        "uri": "spotify:playlist:20N27XDYMAJ9YPNQKTfJyq",
        "hex": "7e070503ff007f10ef"  # Pink
    },
    "summer": {
        "uri": "spotify:playlist:2qGRLh923i3eV11NFy0LSl",
        "hex": "7e070503ff450010ef"  # Sun Orange
    },
    "prince": {
        "uri": "spotify:playlist:3ECu80LqexsohmZebvuBnR",
        "hex": "7e07050380008010ef"  # Purple
    },
    "sade": {
        "uri": "spotify:playlist:7F50uIOaxN6xz3VRJXCq1G",
        "hex": "7e070503ffd70010ef"  # Silk Gold
    }
}

SONGS = {
    "oooo la la": {
        "uri": "spotify:track:5WDLRQ3VCdVrKw0njWe5E5",
        "hex": "7e070503ff000010ef"
    },
    "jarvis": {
        "uri": "spotify:track:39shmbIHICJ2Wxnk1fPSdz",
        "hex": "7e0705030000ff10ef"
    }
}

# --- DATABASE INITIALIZATION ---
# Seed the DB with current hardcoded values if it doesn't exist
database.init_db(PLAYLISTS, SONGS)
# ---------------------

# --- BLUETOOTH PERSISTENT WORKER ---
async def ble_async_worker():
    """Background task that stays connected to the LEDs."""
    global BLE_CONNECTED
    print("DEBUG: BLE Async worker is starting...")
    while True:
        try:
            print(f"Connecting to LEDs at {MAC_ADDR}...", flush=True)
            async with BleakClient(MAC_ADDR) as client:
                BLE_CONNECTED = True
                print(f"BLE Connected to {MAC_ADDR}!", flush=True)
                while True:
                    try:
                        # Wait for a color update from the queue
                        # Using a thread-safe way to get from the queue
                        loop = asyncio.get_event_loop()
                        hex_val = await loop.run_in_executor(None, lambda: color_queue.get(timeout=2.0))
                        print(f"BLE Worker: Sending {hex_val}", flush=True)
                        
                        # Optimise for efficient time transfer: skip to latest if flooded
                        while not color_queue.empty():
                            hex_val = color_queue.get()
                        
                        if client.is_connected:
                            # response=False makes the write much faster (no handshake)
                            await client.write_gatt_char(CHAR_UUID, bytes.fromhex(hex_val), response=False)
                            print(f"Instant BLE Update: {hex_val}")
                        else:
                            # Re-queue the color and reconnect
                            color_queue.put(hex_val)
                            break
                    except queue.Empty:
                        if not client.is_connected:
                            break
                        continue
        except Exception as e:
            BLE_CONNECTED = False
            print(f"BLE Worker Connection Error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

def ble_worker():
    """Thread entry point."""
    print("DEBUG: BLE Thread Started.")
    try:
        asyncio.run(ble_async_worker())
    except Exception as e:
        print(f"BLE Thread Error: {e}")

async def _async_execute_playback(playlist_uri, led_hex, is_song=False):
    print(f"Opening: {playlist_uri}", flush=True)
    
    # 1. Open the URI (this forces Spotify to the front)
    os.system(f"start {playlist_uri}")
    
    # IF INSTANT MODE: Trigger LEDs now
    if SYNC_MODE == "instant":
        print("Instant Sync: Triggering LEDs immediately.")
        color_queue.put(led_hex)

    # 2. Give Spotify a moment to load and become active
    await asyncio.sleep(1.5)
    
    # 3. Check current status to avoid redundant "Play" commands (which can act as Pause)
    try:
        sm = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        session = next((s for s in sm.get_sessions() if "Spotify" in s.source_app_user_model_id), None)
        if session:
            pb = session.get_playback_info()
            if pb and pb.playback_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                # For songs, if it's already playing, we definitely don't want to press Enter/Click
                if is_song:
                    print("Track already playing. Syncing LEDs.", flush=True)
                    color_queue.put(led_hex)
                    return True
                # For playlists, it might be the OLD song. We'll proceed with the click 
                # but only if we haven't confirmed it's the new playlist yet.
    except: pass

    def is_spotify_green(r, g, b):
        # Spotify green is roughly #1DB954 (29, 185, 84) or #1ED760 (30, 215, 96)
        # We check for a strong green component and low red/blue
        return g >= 180 and r < 110 and b < 160 and g > r + 70

    # 4. Hybrid approach: Scan the Active Window for the green Play button
    def click_play_button():
        try:
            mx, my = pyautogui.position()
            win = gw.getActiveWindow()
            
            # Check if active window is Spotify (could be "Spotify" or "Song Name - Artist")
            is_likely_spotify = win and ("Spotify" in win.title or " - " in win.title or playlist_uri in win.title)
            
            if win and is_likely_spotify:
                # Check pixel under cursor
                if win.left <= mx <= win.right and win.top <= my <= win.bottom:
                    with mss.mss() as sct:
                        pixel_check = sct.grab({"top": my, "left": mx, "width": 1, "height": 1})
                        b, g, r = pixel_check.pixel(0, 0)
                        if is_spotify_green(r, g, b):
                            print(f"Cursor already at {mx}, {my} (Spotify Green). Clicking!")
                            pyautogui.click(mx, my)
                            return True

                # Fallback: Scan the window
                search_region = {"top": win.top, "left": win.left, "width": win.width, "height": win.height}
                with mss.mss() as sct:
                    screenshot = sct.grab(search_region)
                    width, height = screenshot.width, screenshot.height
                    max_y = int(height * 0.8) # Scan more of the window
                    
                    for x in range(0, width, 15): # Faster scan
                        for y in range(0, max_y, 15):
                            b, g, r = screenshot.pixel(x, y)
                            if is_spotify_green(r, g, b):
                                screen_x = search_region["left"] + x
                                screen_y = search_region["top"] + y
                                print(f"Found Play Button at {screen_x}, {screen_y}. Moving and Clicking...")
                                pyautogui.moveTo(screen_x, screen_y, duration=0.2)
                                pyautogui.click(screen_x, screen_y)
                                return True
            return False
        except Exception as e:
            print(f"Play button scan failed: {e}")
            return False

    if is_song:
        print("Track detected: Pressing Enter to ensure playback.")
        # Only press enter if it's NOT already playing (checked above)
        pyautogui.press('enter')
    else:
        # For playlists, we click the big Play button
        clicked = click_play_button()
        if not clicked:
            print("Could not find green play button. Trying Enter key fallback...")
            pyautogui.press('enter')
    
    # If we already triggered in instant mode, we can stop here or just let the smart sync confirm it
    if SYNC_MODE == "instant":
        return True

    # 4. Use Windows Media Controls to guarantee perfect LED sync
    try:
        sessions_manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    except Exception as e:
        print(f"Failed to get session manager: {e}")
        color_queue.put(led_hex)
        return False
    
    print("Smart Sync: Waiting for playback confirmation...")
    for attempt in range(20): # 20 attempts * 0.2s = 4 seconds max
        sessions = sessions_manager.get_sessions()
        session = next((s for s in sessions if "Spotify" in s.source_app_user_model_id), None)
        
        if session:
            playback_info = session.get_playback_info()
            if playback_info and playback_info.playback_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                print("Confirmed: OS reports song is playing. Syncing LEDs now.", flush=True)
                color_queue.put(led_hex)
                return True
                
            print("OS reports not playing yet. Forcing play command...", flush=True)
            await session.try_play_async()
            
        await asyncio.sleep(0.2)
        
    print("Warning: Could not confirm playback via OS, syncing LEDs anyway.")
    color_queue.put(led_hex)
    return False

def execute_playback(playlist_uri, led_hex, is_song=False):
    # Run the async playback logic in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_async_execute_playback(playlist_uri, led_hex, is_song=is_song))
    loop.close()
    return result

async def _async_get_spotify_status():
    try:
        sessions_manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        session = sessions_manager.get_current_session()
        if session:
            playback_info = session.get_playback_info()
            is_playing = playback_info and playback_info.playback_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING
            
            media_props = await session.try_get_media_properties_async()
            if media_props and media_props.title:
                title = f"{media_props.artist} - {media_props.title}" if media_props.artist else media_props.title
            else:
                title = "Unknown"
            
            return {
                "playing": is_playing,
                "title": title if is_playing else "Paused",
                "color": current_color_hex,
                "ble_connected": BLE_CONNECTED,
                "sync_mode": SYNC_MODE
            }
    except Exception as e:
        print(f"Status error: {e}")
    return {
        "playing": False, 
        "title": "Spotify Closed", 
        "color": current_color_hex,
        "ble_connected": BLE_CONNECTED,
        "sync_mode": SYNC_MODE
    }

def get_spotify_status():
    """Check playback via Windows Media Controls for 100% accuracy."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_async_get_spotify_status())
    loop.close()
    return result

@app.route('/status', methods=['GET'])
def playback_status():
    return get_spotify_status()

@app.route('/', methods=['GET'])
def index():
    all_moods = database.get_all_moods()
    # Categorize for the template
    db_playlists = {m['name']: {'uri': m['uri'], 'hex': m['hex_color'], 'id': m['id']} for m in all_moods if not m['is_song']}
    db_songs = {m['name']: {'uri': m['uri'], 'hex': m['hex_color'], 'id': m['id']} for m in all_moods if m['is_song']}
    return render_template('index.html', playlists=db_playlists, songs=db_songs)

@app.route('/api/moods', methods=['POST'])
def add_new_mood():
    data = request.json
    name = data.get('name')
    uri = data.get('uri')
    hex_color = data.get('hex_color', '7e0705031db95410ef')
    is_song = data.get('is_song', False)
    
    if database.add_mood(name, uri, hex_color, is_song):
        return {"status": "success"}
    return {"status": "error", "message": "Mood already exists"}, 400

@app.route('/api/moods/<int:mood_id>', methods=['PUT'])
def update_existing_mood(mood_id):
    data = request.json
    name = data.get('name')
    uri = data.get('uri')
    hex_color = data.get('hex_color')
    
    database.update_mood(mood_id, name, uri, hex_color)
    return {"status": "success"}

@app.route('/api/moods/<int:mood_id>', methods=['DELETE'])
def delete_existing_mood(mood_id):
    database.delete_mood(mood_id)
    return {"status": "success"}

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    global SYNC_MODE
    if request.method == 'POST':
        data = request.json
        SYNC_MODE = data.get('sync_mode', SYNC_MODE)
        return {"status": "success", "sync_mode": SYNC_MODE}
    return {"sync_mode": SYNC_MODE}

from flask import request

@app.route('/api/led/color', methods=['POST'])
def api_led_color():
    data = request.json
    r, g, b = data.get('r', 0), data.get('g', 0), data.get('b', 0)
    hex_cmd = LEDCommand.color(r, g, b)
    
    global current_color_hex
    current_color_hex = hex_cmd
    
    color_queue.put(hex_cmd)
    return {"status": "success", "color": hex_cmd}

@app.route('/api/led/mode', methods=['POST'])
def api_led_mode():
    data = request.json
    mode_id = data.get('mode', 128)
    speed = data.get('speed', 10)
    hex_cmd = LEDCommand.mode(mode_id, speed)
    
    global current_color_hex
    current_color_hex = hex_cmd
    
    color_queue.put(hex_cmd)
    return {"status": "success", "color": hex_cmd}

@app.route('/<name>', methods=['GET'])
def trigger_mood(name):
    # Fetch from database instead of hardcoded dicts
    target = database.get_mood_by_name(name)
    
    if target:
        print(f"Received request for /{name}")
        is_song = target['is_song']
        
        # Update global state
        global current_color_hex
        current_color_hex = target["hex_color"]
        
        # Launch Spotify & Playback in a separate thread
        threading.Thread(
            target=execute_playback, 
            args=(target["uri"], current_color_hex), 
            kwargs={"is_song": is_song}, 
            daemon=True
        ).start()
        
        return {"status": "success", "message": f"Activating {name}"}, 200
    return {"status": "error", "message": f"Mood '{name}' not found"}, 404

if __name__ == '__main__':
    # Start the persistent BLE worker in the background
    threading.Thread(target=ble_worker, daemon=True).start()
    
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 5000))
    print(f"Server starting on http://{host}:{port}")
    app.run(host=host, port=port)

