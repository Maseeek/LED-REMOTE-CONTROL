import asyncio
import os
import time
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager, GlobalSystemMediaTransportControlsSessionPlaybackStatus

async def force_play_uri(uri):
    # 1. Open URI
    print(f"Opening URI: {uri}")
    os.system(f"start {uri}")
    
    # Give Spotify a moment to process the URI
    await asyncio.sleep(1.5)
    
    sessions_manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    
    for attempt in range(10):
        session = sessions_manager.get_current_session()
        if not session:
            print("No media session found. Waiting...")
            await asyncio.sleep(0.5)
            continue
            
        playback_info = session.get_playback_info()
        status = playback_info.playback_status
        
        if status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
            print("Successfully playing!")
            return True
            
        print("Not playing. Sending play command...")
        await session.try_play_async()
        await asyncio.sleep(0.5)
        
    print("Failed to play.")
    return False

if __name__ == "__main__":
    asyncio.run(force_play_uri("spotify:track:39shmbIHICJ2Wxnk1fPSdz"))
