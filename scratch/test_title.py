import pygetwindow as gw

def check_spotify():
    windows = gw.getWindowsWithTitle('Spotify')
    # Filter for the main window (it usually has a width/height)
    spotify_windows = [w for w in windows if w.width > 200]
    
    if not spotify_windows:
        print("Spotify is not open.")
        return

    for w in spotify_windows:
        title = w.title
        print(f"Window found: '{title}'")
        
        # Heuristic check
        is_playing = " - " in title
        if is_playing:
            print(f"Status: Playing ({title})")
        elif title in ["Spotify", "Spotify Free", "Spotify Premium"]:
            print("Status: Paused/Idle")
        else:
            print(f"Status: Unknown/Other ('{title}')")

if __name__ == "__main__":
    check_spotify()
