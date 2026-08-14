import asyncio
from google.adk.runners import Runner
from app.app_utils.services import get_session_service, get_artifact_service
from google.genai import types
from google.adk.agents.run_config import RunConfig
import os
from dotenv import load_dotenv

load_dotenv(".env")
os.environ["SESSION_SERVICE_URI"] = "memory://"

from app.agent import root_agent

async def main():
    runner = Runner(
        agent=root_agent, 
        session_service=get_session_service(), 
        artifact_service=get_artifact_service(), 
        app_name="app"
    )
    
    msg = types.Content(role="user", parts=[types.Part.from_text(text="I want to travel from NYC to MIA from 2026-10-10 to 2026-10-15. 2 travelers.")])
    
    session = get_session_service().create_session_sync(user_id="test_user", app_name="app")

    events = runner.run_async(
        new_message=msg,
        user_id="test_user",
        session_id=session.id,
        run_config=RunConfig()
    )
    
    async for event in events:
         print(f"[{event.author}] {event.content.parts[0].text if event.content and event.content.parts else ''}")
         if event.actions and getattr(event.actions, 'tool_calls', None):
             print(f"Tool calls: {event.actions.tool_calls}")

if __name__ == "__main__":
    asyncio.run(main())
