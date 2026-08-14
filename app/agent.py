import json
from google.adk.agents import LlmAgent
from google.adk.workflow import Workflow
from google.adk.events.event import Event
from google.adk.apps import App
from google.adk.models import Gemini
from pydantic import BaseModel, create_model
from .tools import (
    search_public_travel_tool,
    validate_preferences_tool,
    generate_vibe_diff_tool,
    UserProfile
)

orchestrator = LlmAgent(
    name="orchestrator",
    model=Gemini(model="gemini-3.1-pro"),
    instruction="""You are the Orchestrator Agent. 
Analyze the user intent, manage session contextualization, and format the output into a search request.""",
)

querying = LlmAgent(
    name="querying",
    model=Gemini(model="gemini-3.6-flash"),
    instruction="""You are the Querying Agent (Strict data retriever).
Translate the Orchestrator's requests into search queries. 
Use the search_public_travel_tool to fetch real-world flights and hotels.
Pass the resulting searchDataURI to the Auditor.""",
    tools=[search_public_travel_tool]
)

AuditorSchema = create_model("AuditorSchema", isAligned=(bool, ...), approvedDataURI=(str, ...), needsRetry=(bool, ...))

auditor = LlmAgent(
    name="auditor",
    model=Gemini(model="gemini-3.1-pro"),
    instruction="""You are the Auditor Agent.
Inspect the raw public search results in searchDataURI using validate_preferences_tool.
Ensure they align with the personal traveler's stated preferences.
If aligned, pass approvedDataURI to Reporting. If not, trigger a retry.""",
    tools=[validate_preferences_tool],
    output_schema=AuditorSchema
)

reporting = LlmAgent(
    name="reporting",
    model=Gemini(model="gemini-3.6-flash"),
    instruction="""You are the Reporting Agent (UI synthesizer).
Generate Agent-to-User Interface (A2UI) declarative output formatting using generate_vibe_diff_tool on the approvedDataURI.""",
    tools=[generate_vibe_diff_tool]
)

def auditor_router(node_input):
    if hasattr(node_input, "model_dump"):
        node_input = node_input.model_dump()
    if node_input.get("needsRetry"):
        return Event(output=node_input, route="retry")
    return Event(output=node_input.get("approvedDataURI"), route="approved")

root_agent = Workflow(
    name="travel_planner",
    edges=[
        ('START', orchestrator),
        (orchestrator, querying),
        (querying, auditor),
        (auditor, auditor_router),
        (auditor_router, {"retry": querying, "approved": reporting})
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
)
