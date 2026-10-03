# Lumina — Asynchronous BLE LED Controller & Real-Time Spotify Synchronizer

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Bleak](https://img.shields.io/badge/BLE_GATT-Bleak_%2B_Asyncio-0082FC?logo=bluetooth&logoColor=white)](https://github.com/hbldh/bleak)
[![Flask](https://img.shields.io/badge/Backend-Flask_REST_API-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/Persistence-SQLite3-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Windows Media Control](https://img.shields.io/badge/OS_Integration-WinRT_SMTC-0078D6?logo=windows&logoColor=white)](https://learn.microsoft.com/en-us/uwp/api/windows.media.control)

**Lumina (`LED-REMOTE-CONTROL`)** is an asynchronous IoT hardware controller and media synchronization engine written in Python. It bridges a responsive web control plane (**Flask**) with Bluetooth Low Energy (BLE) LED strip hardware over the **GATT protocol** (`bleak` + `asyncio`), synchronizing room lighting with real-time **Spotify** playback state via Windows System Media Transport Controls (`winrt`) and computer-vision UI automation (`mss` + `PyAutoGUI`).

---

## System Architecture

```mermaid
flowchart TB
    subgraph Client["Web Control Plane (Lumina UI)"]
        UI[Responsive Dashboard<br/>Mood Triggers, RGB Picker & Dynamic Effects]
    end

    subgraph Server["Flask Application & Sync Engine (music-start.py)"]
        API[Flask REST Controller<br/>/api/moods, /api/led/*, /status]
        DB[(SQLite Persistence<br/>database.py)]
        SYNC[Playback Sync Engine<br/>Spotify URI Launcher + WinRT SMTC Polling]
        CV[Computer Vision Fallback<br/>mss Screen Capture + PyAutoGUI]
        Q[[Thread-Safe Command Queue<br/>Flood-Draining FIFO]]
    end

    subgraph BLE["Asynchronous BLE Worker Thread (asyncio + bleak)"]
        SCAN[BleakScanner Discovery<br/>Self-Healing Reconnection Loop]
        GATT[BleakClient GATT Writer<br/>UUID 0000fff3-0000-1000-8000-00805f9b34fb]
    end

    subgraph External["Hardware & Media Targets"]
        LED[ELK-BLEDOM / BLE LED Strip<br/>9-Byte Hex Frame Protocol]
        SPOT[Spotify Desktop Client &<br/>Windows Media Session Manager]
    end

    UI -->|REST JSON / Status Polling| API
    API <-->|CRUD Mood Mappings| DB
    API -->|Enqueue 9-Byte Hex Frame| Q
    API -->|Spawn Daemon Playback Thread| SYNC
    SYNC <-->|Query Session & Force Play| SPOT
    SYNC -->|Pixel Scan Play Button| CV
    CV -->|Click / Keypress| SPOT
    SYNC -->|Playback Confirmed -> Enqueue Color| Q
    Q -->|run_in_executor Non-Blocking Read| GATT
    SCAN -->|Maintain Persistent Session| GATT
    GATT -->|write_gatt_char Raw Bytes| LED
```

---

## Core Engineering Highlights

### 1. Asynchronous BLE GATT Protocol Controller (`bleak` + `asyncio`)
- **Binary Frame Encoding (`LEDCommand`)**: Implements the 9-byte ELK-BLEDOM GATT wire protocol directly in hex frames:
  - **Static RGB Frame**: `7e 07 05 03 [RR] [GG] [BB] 10 ef`
  - **Hardware Effect / Strobe Frame**: `7e 05 03 [MODE_ID] [SPEED] 00 00 00 ef`
- **Flood-Draining Command Queue**: High-frequency UI events (such as dragging the RGB color picker or effect speed slider) push frames into a thread-safe `queue.Queue`. The async BLE worker drains intermediate stale frames when flooded, writing only the latest state to the GATT characteristic (`0000fff3-0000-1000-8000-00805f9b34fb`) to eliminate BLE packet backlog and latency.

### 2. Self-Healing Background Reconnection Worker
- A dedicated daemon thread hosts a persistent `asyncio` event loop (`ble_async_worker`).
- Performs active device discovery via `BleakScanner.find_device_by_address`, maintains an open `BleakClient` context, and monitors link health with idle heartbeats.
- If the LED controller powers down or drops out of RF range, failed writes are automatically re-queued while the worker enters a non-blocking exponential/interval retry loop until the GATT link is restored.

### 3. Real-Time Spotify Playback Synchronization & OS Media Integration
- **Smart Sync vs. Instant Sync**:
  - **Smart Sync Mode**: Prevents premature lighting transitions while Spotify loads. Queries the Windows Runtime `GlobalSystemMediaTransportControlsSessionManager` (`winrt.windows.media.control`) at 200 ms intervals to verify `GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING` and invokes `try_play_async()` before dispatching the target mood color to the BLE queue.
  - **Instant Sync Mode**: Immediately dispatches the GATT color frame upon mood selection while background threads initiate media playback.
- **Live Telemetry**: Exposes `/status` polling for active track artist/title metadata, playback state, current LED frame state, and live BLE connection health.

### 4. Computer Vision UI Automation & Audio-Reactive Modes
- When launching playlist URIs (`spotify:playlist:...`), `music-start.py` uses **mss** for high-speed screen region capture and **PyGetWindow** to locate the active Spotify window.
- Scans window pixels in a strided grid for Spotify's signature green accent (`#1DB954` / `#1ED760`, $G \ge 180, R < 110, B < 160, G > R + 70$) and dispatches **PyAutoGUI** cursor/keyboard automation to start playback reliably.
- Supports hardware-accelerated dynamic lighting modes (Seven Color Fade, RGB Strobe, Color Jump) with real-time speed modulation.

### 5. SQLite State Persistence (`database.py`)
- Stores user-defined **Moods** (mappings between Spotify Track/Playlist URIs and 9-byte BLE hex payloads) in a local SQLite database (`moods` table).
- Automatically initializes schema and seeds default playlists and solo tracks on first boot while supporting full REST CRUD (`/api/moods`) from the web dashboard.

---

## API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/` | `GET` | Renders the Lumina web controller (`templates/index.html`) hydrated with persisted moods |
| `/<name>` | `GET` | Activates a named mood: updates LED state and spawns asynchronous Spotify playback sync |
| `/status` | `GET` | Returns real-time WinRT media playback telemetry, active track title, and BLE link status |
| `/api/led/color` | `POST` | Encodes `{ r, g, b }` into a `7e070503...` frame and enqueues an immediate GATT write |
| `/api/led/mode` | `POST` | Triggers or toggles off hardware effect modes (`7e0503...`) with configurable speed |
| `/api/settings` | `GET` / `POST` | Reads or updates the synchronization engine mode (`smart` vs. `instant`) |
| `/api/moods` | `POST` | Persists a new playlist or track mood mapping in SQLite |
| `/api/moods/<id>` | `PUT` / `DELETE` | Updates or deletes an existing mood mapping by ID |

---

## Getting Started

### Prerequisites

- **OS**: Windows 10 / 11 (required for `winrt-Windows.Media.Control` and `winrt-Windows.Devices.Bluetooth`)
- **Python**: 3.9+
- **Hardware**: Bluetooth Low Energy LED controller (ELK-BLEDOM / `0000fff3` GATT characteristic compatible)
- **Spotify**: Spotify Desktop client installed and authenticated

### 1. Installation

```bash
git clone https://github.com/Maseeek/LED-REMOTE-CONTROL.git
cd LED-REMOTE-CONTROL

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure your BLE controller's MAC address and GATT write characteristic UUID:

```bash
cp .env.example .env
```

```ini
LED_MAC_ADDR=BE:37:FC:00:3C:49
LED_CHAR_UUID=0000fff3-0000-1000-8000-00805f9b34fb
FLASK_PORT=5000
FLASK_HOST=0.0.0.0
```

### 3. Running the Controller

```bash
python music-start.py
```

Open `http://localhost:5000` (or your host's LAN IP from any mobile device on the same network) to access the Lumina dashboard.

---

## License

MIT License
