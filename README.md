# LED Remote Control & Spotify Sync

A full-stack application that provides a responsive web interface to control Bluetooth Low Energy (BLE) LED light strips and synchronizes their colors with your Spotify playback.

## Features
- **Web Dashboard:** A modern, mobile-friendly interface to control your LEDs remotely.
- **Spotify Integration:** Automatically changes LED colors based on the Spotify playlist or song you start.
- **Smart Playback Sync:** Uses Windows Media Transport Controls (`winrt`) to ensure LEDs perfectly sync with actual playback state, preventing premature light changes before the song starts.
- **BLE Communication:** Uses `bleak` to connect to Bluetooth Low Energy LED controllers asynchronously, maintaining a persistent, self-healing background connection.
- **Computer Vision Fallback:** Uses `mss` and `pyautogui` for screen reading and automated UI interaction to start playback in the Spotify desktop app if needed.
- **Database Backend:** Uses SQLite to store custom "Moods" (a mapping between a Spotify URI and a specific LED hex color).

## Prerequisites
- **OS:** Windows 10/11 (due to `winrt` and `pygetwindow` dependencies).
- **Python:** Python 3.9+ 
- **Hardware:** A compatible Bluetooth LE LED strip (commonly using the `0000fff3` characteristic for writing commands).
- **Spotify:** The Spotify desktop application must be installed and logged in.

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd LED-REMOTE-CONTROL
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   - Copy `.env.example` to a new file named `.env`:
     ```bash
     cp .env.example .env
     ```
   - Open `.env` and enter your LED strip's MAC address:
     ```env
     LED_MAC_ADDR=BE:37:FC:00:3C:49
     ```


4. **Initialize Playlists/Songs:**
   - In `music-start.py`, you can modify the `PLAYLISTS` and `SONGS` dictionaries with your own Spotify URIs and desired hex colors. The database will be seeded with these upon first run.

## Running the Application

1. Ensure your computer's Bluetooth is turned on.
2. Run the main server:
   ```bash
   python music-start.py
   ```
3. Open a web browser and navigate to the IP address printed in your terminal (e.g., `http://localhost:5000` or your local network IP).

## Architecture & Technical Details

- **Flask Backend:** Serves the REST API and the frontend application.
- **Asynchronous BLE Worker:** A dedicated `asyncio` loop runs in a background thread to maintain the BLE connection. It reads from a thread-safe `queue` and sends commands to the LEDs instantly.
- **Playback Detection:** The app attempts to use Windows Media Controls for exact status. When triggering a new mood, it can also use screen region scanning to find and click the Spotify "Play" button dynamically.
- **SQLite Database:** Handles CRUD operations for adding, editing, and deleting "Moods" from the web interface.

## License
MIT License
