import asyncio
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager

async def get_media_info():
    sessions = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    current_session = sessions.get_current_session()
    if current_session:
        playback_info = current_session.get_playback_info()
        print(f"Status: {playback_info.playback_status.name}")
        
        # 4 is 'playing', 5 is 'paused' in the enum usually, 
        # but playback_status.name should be 'PLAYING' or 'PAUSED'
        
        info = await current_session.try_get_media_properties_async()
        if info:
            print(f"Title: {info.title}")
            print(f"Artist: {info.artist}")
    else:
        print("No active media session.")

if __name__ == "__main__":
    try:
        asyncio.run(get_media_info())
    except ImportError:
        print("Required winrt package missing. Try: pip install winrt-Windows.Media.Control")
    except Exception as e:
        print(f"Error: {e}")
