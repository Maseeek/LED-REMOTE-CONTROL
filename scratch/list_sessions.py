import asyncio
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager

async def list_sessions():
    sessions_manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    sessions = sessions_manager.get_sessions()
    print(f"Total sessions found: {len(sessions)}")
    for i, s in enumerate(sessions):
        props = await s.try_get_media_properties_async()
        print(f"Session {i}: {s.source_app_user_model_id} - {props.title if props else 'No Props'}")

if __name__ == "__main__":
    asyncio.run(list_sessions())
