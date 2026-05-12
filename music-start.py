from flask import Flask
import os
import time
import pyautogui
import threading
import asyncio
from bleak import BleakClient
from mss import mss

app = Flask(__name__)

# --- CONFIGURATION ---
MAC_ADDR = "BE:37:FC:00:3C:49" 
CHAR_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"  

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
# ---------------------

# --- BLUETOOTH LOGIC ---
async def set_led_color(hex_val):
    try:
        async with BleakClient(MAC_ADDR) as client:
            await client.write_gatt_char(CHAR_UUID, bytes.fromhex(hex_val))
            print(f"LEDs updated with hex: {hex_val}")
    except Exception as e:
        print(f"BLE Error: {e}")

def run_ble_thread(hex_val):
    # Running the async BLE call in a separate thread to prevent Flask blocking
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(set_led_color(hex_val))
    finally:
        loop.close()

def execute_playback(playlist_uri):
    print(f"Opening playlist: {playlist_uri}")
    result = os.system(f"start {playlist_uri}")
    
    if result != 0:
        print(f"Failed to execute start command. Error code: {result}")
        return False

    def find_and_click_play():
        try:
            with mss() as sct:
                monitor = sct.monitors[0]
                screenshot = sct.grab(monitor)
                width, height = screenshot.width, screenshot.height
                
                for x in range(50, width - 50, 15): # Slightly finer scan
                    for y in range(50, height - 50, 15):
                        b, g, r = screenshot.pixel(x, y)
                        
                        # Is it Spotify Green?
                        if g > 180 and r < 100 and b < 150 and g > r + 80:
                            # 1. VERIFY SIZE: Check a wider area (15px away)
                            b2, g2, r2 = screenshot.pixel(x + 15, y + 15)
                            if g2 > 180 and r2 < 100 and b2 < 150:
                                
                                # 2. TRIANGLE CHECK: Look for black inside (the play icon)
                                # The heart icon is solid green, the Play button has a black center
                                found_black = False
                                for dx in range(-20, 20, 5):
                                    for dy in range(-20, 20, 5):
                                        bx, gx, rx = screenshot.pixel(x + dx, y + dy)
                                        if rx < 40 and gx < 40 and bx < 40: # Black/Dark Gray
                                            found_black = True
                                            break
                                    if found_black: break
                                
                                if found_black:
                                    screen_x = monitor["left"] + x
                                    screen_y = monitor["top"] + y
                                    print(f"Confirmed Play button (with triangle) at {screen_x}, {screen_y}")
                                    pyautogui.click(screen_x, screen_y)
                                    return True
                return False
        except Exception as e:
            print(f"Error during search: {e}")
            return False

    # Optimized Playback logic: Poll frequently for the play button
    print("Scanning for Spotify Play button (polling for 8s)...")
    
    # Try immediately, then loop
    for attempt in range(16): # 16 attempts * 0.5s = 8 seconds total
        if find_and_click_play():
            print(f"Play button clicked on attempt {attempt + 1}")
            return True
        time.sleep(0.5) # Check every 500ms for responsiveness
        
    print("Play button not found, falling back to Alt+Shift+P...")
    pyautogui.hotkey('alt', 'shift', 'p')
    return True

@app.route('/<mood>', methods=['GET'])
def trigger_playlist(mood):
    if mood in PLAYLISTS:
        print(f"Received request for /{mood}")
        
        # 1. Update LEDs immediately in background
        led_hex = PLAYLISTS[mood]["hex"]
        threading.Thread(target=run_ble_thread, args=(led_hex,)).start()
        
        # 2. Launch Spotify & Playback
        execute_playback(PLAYLISTS[mood]["uri"])
        
        return f"Started {mood} music and updated LEDs", 200
    return "Playlist not found", 404

if __name__ == '__main__':
    print("Server starting on http://0.0.0.0:5000")
    print(f"Available endpoints: {list(PLAYLISTS.keys())}")
    app.run(host='0.0.0.0', port=5000)
