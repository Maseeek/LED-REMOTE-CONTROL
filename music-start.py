from flask import Flask, render_template, request, jsonify
import database
import os
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
MAC_ADDR = "BE:37:FC:00:3C:49" 
CHAR_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"  

# --- GLOBAL STATE ---
color_queue = queue.Queue()
current_color_hex = "7e0705031db95410ef" # Default Spotify Green

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
        "uri": "spotify:track:5WDLRQ3VCdVrKw0njWe5E5", # Example song
        "hex": "7e070503ff000010ef"  # red
    },
    "jarvis":{
        "uri": "spotify:track:39shmbIHICJ2Wxnk1fPSdz",
        "hex": "7e0705030000ff10ef" # deep blue
    }
}
# --- DATABASE INITIALIZATION ---
# Seed the DB with current hardcoded values if it doesn't exist
database.init_db(PLAYLISTS, SONGS)
# ---------------------

# --- BLUETOOTH PERSISTENT WORKER ---
def ble_worker():
    """Background thread that stays connected to the LEDs."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def run():
        while True:
            try:
                print(f"Connecting to LEDs at {MAC_ADDR}...")
                async with BleakClient(MAC_ADDR) as client:
                    print("BLE Connected! Ready for instant updates.")
                    while True:
                        try:
                            # Wait for a color update from the queue
                            # Using a small timeout so we can check connection status
                            hex_val = color_queue.get(timeout=1.0)
                            
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
                print(f"BLE Worker Connection Error: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

    loop.run_until_complete(run())

async def _async_execute_playback(playlist_uri, led_hex, is_song=False):
    print(f"Opening: {playlist_uri}")
    
    # 0. Force Pause first. If a song is already playing, we want it to stop
    # so we don't accidentally sync LEDs to the OLD song's PLAYING status.
    try:
        sm = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        for s in sm.get_sessions():
            if "Spotify" in s.source_app_user_model_id:
                await s.try_pause_async()
                break
    except: pass

    # 1. Open the URI (this forces Spotify to the front)
    os.system(f"start {playlist_uri}")
    
    # 2. Give Spotify a moment to load the page and become the active window
    await asyncio.sleep(1.5)
    
    def is_spotify_green(r, g, b):
        return g > 185 and r < 100 and b < 150 and g > r + 80

    # 3. Hybrid approach: Scan the Active Window for the green Play button
    def click_play_button():
        try:
            # First, check if the mouse is ALREADY over the play button (User tip)
            mx, my = pyautogui.position()
            
            # Since 'start' brings Spotify to the front, it should be the active window
            win = gw.getActiveWindow()
            
            if win:
                # Check pixel under cursor if it's within the window
                if win.left <= mx <= win.right and win.top <= my <= win.bottom:
                    with mss.mss() as sct:
                        # Grab just the pixel under the mouse
                        pixel_check = sct.grab({"top": my, "left": mx, "width": 1, "height": 1})
                        b, g, r = pixel_check.pixel(0, 0)
                        if is_spotify_green(r, g, b):
                            print(f"Cursor already at {mx}, {my} (Spotify Green). Clicking!")
                            pyautogui.click(mx, my)
                            return True

                # Fallback: Scan the window if the cursor wasn't on the button
                search_region = {"top": win.top, "left": win.left, "width": win.width, "height": win.height}
                
                with mss.mss() as sct:
                    screenshot = sct.grab(search_region)
                    width, height = screenshot.width, screenshot.height
                    max_y = int(height * 0.6) # Play button is usually in the top half
                    
                    # Scan for Spotify Green
                    for x in range(0, width, 10):
                        for y in range(0, max_y, 10):
                            b, g, r = screenshot.pixel(x, y)
                            if is_spotify_green(r, g, b):
                                screen_x = search_region["left"] + x
                                screen_y = search_region["top"] + y
                                print(f"Found Play Button at {screen_x}, {screen_y}. Clicking...")
                                pyautogui.click(screen_x, screen_y, duration=0.1)
                                return True
            return False
        except Exception as e:
            print(f"Play button scan failed: {e}")
            return False

    if is_song:
        print("Track detected: Using Enter method directly.")
        # Ensure Spotify is active before pressing enter
        try:
            spotify_windows = [w for w in gw.getWindowsWithTitle('Spotify') if w.width > 200]
            if spotify_windows:
                spotify_windows[0].activate()
                await asyncio.sleep(0.5)
        except: pass
        pyautogui.press('enter')
    else:
        clicked = click_play_button()
        if not clicked:
            print("Could not find green play button. Trying Enter key fallback...")
            pyautogui.press('enter')
    
    # 4. Use Windows Media Controls to guarantee perfect LED sync
    try:
        sessions_manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    except Exception as e:
        print(f"Failed to get session manager: {e}")
        color_queue.put(led_hex)
        return False
    
    for attempt in range(12): # 12 attempts * 0.5s = 6 seconds max
        sessions = sessions_manager.get_sessions()
        session = next((s for s in sessions if "Spotify" in s.source_app_user_model_id), None)
        
        if session:
            playback_info = session.get_playback_info()
            if playback_info and playback_info.playback_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                print("Confirmed: OS reports song is playing. Syncing LEDs now.")
                color_queue.put(led_hex)
                return True
                
            print("OS reports not playing yet. Forcing play command...")
            await session.try_play_async()
            
        await asyncio.sleep(0.5)
        
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
                "color": current_color_hex
            }
    except Exception as e:
        print(f"Status error: {e}")
    return {"playing": False, "title": "Spotify Closed", "color": current_color_hex}

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
    
    print("Server starting on http://0.0.0.0:5000")
    print(f"Playlists: {list(PLAYLISTS.keys())}")
    print(f"Songs: {list(SONGS.keys())}")
    app.run(host='0.0.0.0', port=5000)
