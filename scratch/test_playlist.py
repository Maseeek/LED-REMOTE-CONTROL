import os
import time
import pyautogui
import pygetwindow as gw

def test_playlist():
    print("Opening playlist...")
    os.system("start spotify:playlist:3TKkZAP3k6FVMfnFqUMvpL")
    time.sleep(2)
    
    spotify_windows = [w for w in gw.getWindowsWithTitle('Spotify') if w.width > 200]
    if spotify_windows:
        spotify_windows[0].activate()
        time.sleep(0.5)
        
    print("Pressing Tab x3 then Enter...")
    for _ in range(3):
        pyautogui.press('tab')
        time.sleep(0.1)
    pyautogui.press('enter')
    
if __name__ == "__main__":
    test_playlist()
