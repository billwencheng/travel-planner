# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import os
from collections.abc import AsyncIterator
from typing import Any

import google.auth
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.cloud import logging as google_cloud_logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.memory import consolidate_user_memory_async, get_user_memory
from app.app_utils.telemetry import redact_pii, setup_telemetry
from app.app_utils.typing import Feedback

load_dotenv()
setup_telemetry()
_, project_id = google.auth.default()
logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    for path in [
        f"/a2a/{adk_app.name}",
        f"/a2a/{adk_app.name}/",
        f"/api/a2a/{adk_app.name}",
        f"/api/a2a/{adk_app.name}/",
    ]:
        await attach_a2a_routes(
            app,
            agent=root_agent,
            runner=runner,
            task_store=InMemoryTaskStore(),
            rpc_path=path,
        )
    # Ensure static mount is at the end of routes so API routes match first
    static_mounts = [r for r in app.routes if getattr(r, "name", None) == "frontend"]
    for sm in static_mounts:
        app.routes.remove(sm)
        app.routes.append(sm)
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=False,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "travel-planner"
app.description = "API for interacting with the Agent travel-planner"


class NoBufferMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Accel-Buffering"] = "no"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        return response


app.add_middleware(NoBufferMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback with automated PII redaction.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    redacted_feedback = redact_pii(feedback.model_dump())
    logger.log_struct(redacted_feedback, severity="INFO")
    return {"status": "success"}


@app.get("/api/user/{user_id}/memory")
def fetch_user_memory(user_id: str) -> dict[str, Any]:
    """Retrieve long-term traveler preferences from Memory Bank."""
    return get_user_memory(user_id)


@app.post("/api/user/{user_id}/memory/consolidate")
async def trigger_memory_consolidation(
    user_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Trigger asynchronous background memory consolidation for a user session."""
    session_text = payload.get("text", "")
    updated_profile = await consolidate_user_memory_async(user_id, session_text)
    return {"status": "success", "profile": updated_profile}


frontend_dir = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "frontend", "out"
)
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
