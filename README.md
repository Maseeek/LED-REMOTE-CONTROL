# Lumina (LED-REMOTE-CONTROL)

Lumina is a Python web app that controls a Bluetooth LED strip from my phone and matches the room lighting to whatever I play on Spotify.

It runs on a Windows PC. I open the dashboard on any device on the same network, pick a mood, and the PC starts the matching playlist or track in Spotify and sets the LED strip to that mood's color.

## What it does

- Starts a Spotify playlist or track and sets the LEDs to a matching color with one tap.
- Lets you pick any color with an RGB picker, or run built-in strip effects such as fades and strobes at a chosen speed.
- Shows what is playing, the current LED state and whether the strip is connected.
- Lets you add, edit and delete moods (a Spotify link paired with a color) from the dashboard.
- Has two sync modes: "instant" changes the lights right away, "smart" waits until Spotify is actually playing.

## How it's built

Python, Flask, SQLite and a single-page HTML dashboard. Bluetooth runs through `bleak` with `asyncio`, and Spotify playback is read through the Windows media controls API (`winrt`).

- Talking to the LED strip. The strip uses a cheap ELK-BLEDOM style controller. I write its 9-byte commands directly to the GATT characteristic: `7e 07 05 03 RR GG BB 10 ef` for a static color and `7e 05 03 MODE SPEED 00 00 00 ef` for an effect.
- A background Bluetooth worker. A daemon thread runs its own `asyncio` loop that finds the strip by MAC address, keeps the connection open and reads commands from a queue. If the queue fills up, for example while you drag the color picker, it skips to the newest command so the strip never lags behind. If the strip drops out, the failed command goes back on the queue and the worker reconnects every 5 seconds.
- Syncing lights with playback. In smart mode the app checks the Windows media session every 200 ms for up to 4 seconds. When Spotify reports it is playing, the color goes to the strip. If it is not playing yet, the app sends a play command.
- Pressing play when there is no API. Opening a playlist link only brings Spotify to the front, so the app screenshots the Spotify window with `mss`, looks for the green play button by pixel color and clicks it with PyAutoGUI. If it can't find the button it presses Enter.
- Saved moods. Moods live in a small SQLite table that is created and filled with a few default playlists on first run.

## Run it locally

You need Windows 10 or 11, Python 3.9+, the Spotify desktop app and a BLE LED strip that uses the `0000fff3` write characteristic.

```bash
git clone https://github.com/Maseeek/LED-REMOTE-CONTROL.git
cd LED-REMOTE-CONTROL
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set `LED_MAC_ADDR` in `.env` to your strip's Bluetooth address. Then start the server:

```bash
python music-start.py
```

Open `http://localhost:5000`, or the PC's local IP address from your phone.
