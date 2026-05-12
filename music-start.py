from flask import Flask, render_template
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
    "sex": {
        "uri": "spotify:track:5WDLRQ3VCdVrKw0njWe5E5", # Example song
        "hex": "7e070503ff000010ef"  # red
    },
    "jarvis":{
        "uri": "spotify:track:39shmbIHICJ2Wxnk1fPSdz",
        "hex": "7e0705030000ff10ef" # deep blue
    }
}
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

async def _async_execute_playback(playlist_uri, led_hex):
    print(f"Opening: {playlist_uri}")
    os.system(f"start {playlist_uri}")
    
    # Give Spotify a moment to process the URI
    await asyncio.sleep(1.0)
    
    try:
        sessions_manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    except Exception as e:
        print(f"Failed to get session manager: {e}")
        color_queue.put(led_hex)
        return False
    
    # Wait for playback to actually start, force it if needed
    for attempt in range(15): # 15 attempts * 0.4s = 6 seconds max
        session = sessions_manager.get_current_session()
        if session:
            playback_info = session.get_playback_info()
            if playback_info and playback_info.playback_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                print("Successfully playing! Syncing LEDs precisely now...")
                color_queue.put(led_hex)
                return True
                
            print("Not playing yet. Forcing play command...")
            await session.try_play_async()
            # If we sent play, wait a tiny bit longer before checking again
            await asyncio.sleep(0.2)
            
        await asyncio.sleep(0.4)
        
    print("Failed to verify playback start. Falling back to immediate LED sync.")
    color_queue.put(led_hex)
    return False

def execute_playback(playlist_uri, led_hex, is_song=False):
    # Run the async playback logic in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_async_execute_playback(playlist_uri, led_hex))
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
                "title": title if is_playing else "Paused"
            }
    except Exception as e:
        print(f"Status error: {e}")
    return {"playing": False, "title": "Spotify Closed"}

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
    return render_template('index.html', playlists=PLAYLISTS, songs=SONGS)

@app.route('/<name>', methods=['GET'])
def trigger_mood(name):
    # Check if it's a playlist or a song
    target = None
    is_song = False
    
    if name in PLAYLISTS:
        target = PLAYLISTS[name]
    elif name in SONGS:
        target = SONGS[name]
        is_song = True
        
    if target:
        print(f"Received request for /{name}")
        
        # Launch Spotify & Playback (LEDs will sync inside this function)
        led_hex = target["hex"]
        execute_playback(target["uri"], led_hex, is_song=is_song)
        
        return f"Started {name} and updated LEDs", 200
    return f"Mood '{name}' not found", 404

if __name__ == '__main__':
    # Start the persistent BLE worker in the background
    threading.Thread(target=ble_worker, daemon=True).start()
    
    print("Server starting on http://0.0.0.0:5000")
    print(f"Playlists: {list(PLAYLISTS.keys())}")
    print(f"Songs: {list(SONGS.keys())}")
    app.run(host='0.0.0.0', port=5000)
