from flask import Flask
import os
import time
import pyautogui

app = Flask(__name__)

# --- CONFIGURATION ---
PLAYLISTS = {
    "hype": "spotify:playlist:0hBSTE8N0qNbBrXyVH5BUm",
    "chill": "spotify:playlist:3TKkZAP3k6FVMfnFqUMvpL", 
    "party": "spotify:playlist:37i9dQZF1EIcsHAaTPt2VN",
    "italy": "spotify:playlist:2QWl1UykngbHZoeoJsSP90"
}
# ---------------------

def execute_playback(playlist_uri):
    print(f"Opening playlist: {playlist_uri}")
    result = os.system(f"start {playlist_uri}")
    
    if result != 0:
        print(f"Failed to execute start command. Error code: {result}")
        return False

    def find_and_click_play():
        try:
            import pyautogui
            from mss import mss
            with mss() as sct:
                monitor = sct.monitors[0]
                screenshot = sct.grab(monitor)
                width, height = screenshot.width, screenshot.height
                
                for x in range(50, width - 50, 20): # Faster scan
                    for y in range(50, height - 50, 20):
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

    # Attempt playback logic
    print("Checking if Spotify is already open (Attempt 1)...")
    time.sleep(2)
    if not find_and_click_play():
        print("Waiting for load (Attempt 2)...")
        time.sleep(4)
        if not find_and_click_play():
            print("Falling back to Alt+Shift+P...")
            pyautogui.hotkey('alt', 'shift', 'p')
    return True

@app.route('/<mood>', methods=['GET'])
def trigger_playlist(mood):
    if mood in PLAYLISTS:
        print(f"Received request for /{mood}")
        execute_playback(PLAYLISTS[mood])
        return f"Started {mood} music", 200
    return "Playlist not found", 404

if __name__ == '__main__':
    print("Server starting on http://0.0.0.0:5000")
    print(f"Available endpoints: {list(PLAYLISTS.keys())}")
    app.run(host='0.0.0.0', port=5000)
