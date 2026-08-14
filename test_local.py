import asyncio
from app.agent import app
from google.adk.events.event import Event
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.runners import Runner

async def main():
    runner = Runner(
        app=app,
        session_service=InMemorySessionService(),
    )
    session = await runner.session_service.create_session(user_id="test_user")
    
    events = await runner.run_agent(
        "app",
        session,
        Event(output="Hi!", route="START")
    )
    print("FINAL EVENT:", events[-1])

asyncio.run(main())
