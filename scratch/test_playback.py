import os
import time
import pyautogui
import pygetwindow as gw

def test_spotify():
    print("Testing Spotify Playback...")
    # Open a track
    os.system("start spotify:track:39shmbIHICJ2Wxnk1fPSdz")
    time.sleep(2)
    
    windows = [w for w in gw.getWindowsWithTitle('Spotify') if w.width > 200]
    if windows:
        windows[0].activate()
        time.sleep(0.5)
        
    print("Pressing Enter...")
    pyautogui.press('enter')
    
if __name__ == "__main__":
    test_spotify()
