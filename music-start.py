from flask import Flask
import os
import time
import pyautogui
import threading
import asyncio
from bleak import BleakClient
import mss
import pygetwindow as gw
import queue

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

def execute_playback(playlist_uri, led_hex, is_song=False):
    print(f"Opening: {playlist_uri}")
    result = os.system(f"start {playlist_uri}")
    
    if result != 0:
        print(f"Failed to execute start command. Error code: {result}")
        return False

    if is_song:
        print("Song detected, waiting 1.5s for page load...")
        time.sleep(1.5) # Increased delay to ensure page is ready
        try:
            spotify_windows = [w for w in gw.getWindowsWithTitle('Spotify') if w.width > 200]
            if spotify_windows:
                spotify_windows[0].activate()
                time.sleep(0.3)
        except: pass
        
        print("Pressing Enter...")
        pyautogui.press('enter')
        
        # Sync LEDs with track start
        color_queue.put(led_hex)
        return True

    def find_and_click_play():
        try:
            # 1. Try to find the Spotify window to narrow down the search area
            spotify_windows = [w for w in gw.getWindowsWithTitle('Spotify') if w.visible and w.width > 200]
            search_region = None
            
            with mss.mss() as sct:
                if spotify_windows:
                    win = spotify_windows[0]
                    search_region = {"top": win.top, "left": win.left, "width": win.width, "height": win.height}
                else:
                    search_region = sct.monitors[0] # Fallback to all monitors
                
                screenshot = sct.grab(search_region)
                width, height = screenshot.width, screenshot.height
                
                # OPTIMIZATION: Only scan the top 60% of the window
                max_y = int(height * 0.6)
                
                # Scan with a 10px step for maximum precision
                for x in range(0, width, 10):
                    for y in range(0, max_y, 10):
                        b, g, r = screenshot.pixel(x, y)
                        
                        # Robust Spotify Green Check
                        if g > 185 and r < 100 and b < 150 and g > r + 80:
                            screen_x = search_region["left"] + x
                            screen_y = search_region["top"] + y
                            print(f"Fast Match! Play Button at {screen_x}, {screen_y}")
                            
                            # Force focus before clicking
                            try:
                                if spotify_windows:
                                    spotify_windows[0].activate()
                                    time.sleep(0.5) # Increased for stability
                            except: pass
                            
                            # Slower click duration helps Spotify register the input
                            pyautogui.click(screen_x, screen_y, duration=0.1)
                            
                            # Sync LEDs with playlist start
                            color_queue.put(led_hex)
                            return True
                return False
        except Exception as e:
            print(f"Scan error: {e}")
            return False

    # Wait a moment for the window to actually open before scanning
    time.sleep(1.0)
    
    # Extreme Polling: 0.1s interval for maximum speed
    print("Fast Scanning for Play button...")
    for attempt in range(60): # 60 attempts * 0.1s = 6 seconds total
        if find_and_click_play():
            return True
        time.sleep(0.1) 
        
    print("Falling back to Alt+Shift+P...")
    try:
        spotify_windows = [w for w in gw.getWindowsWithTitle('Spotify') if w.width > 200]
        if spotify_windows:
            spotify_windows[0].activate()
            time.sleep(0.3)
    except: pass
    pyautogui.hotkey('alt', 'shift', 'p')
    
    # Sync LEDs with fallback play
    color_queue.put(led_hex)
    return True

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
