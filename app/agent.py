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
    model=Gemini(model="gemini-2.5-pro"),
    instruction="""You are the Orchestrator Travel Concierge Agent.
Your role: Act as the primary interface for the user's travel planning needs.
Task Breakdown:
1. Analyze the user's intent, desired destinations, dates, and overarching trip goals (e.g., family vacation, honeymoon, solo adventure).
2. Ask clarifying questions if critical info (destination, dates) is missing.
3. Once intent is clear, format a structured travel search request detailing Origin, Destination, Departure Date, Return Date, and basic traveler headcount.
4. Pass this formatted search request to the Querying Agent.

Format: Provide a conversational summary explicitly listing the formulated Search Plan parameters before handoff.""",
)

querying = LlmAgent(
    name="querying",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Querying Data Retrieval Agent.
Your role: Fetch real-world flight itineraries and hotel inventories based on the Orchestrator's plan.
Task Breakdown:
1. Parse the travel plan parameters provided by the Orchestrator.
2. Execute the `search_public_travel_tool` using strict query parameters (Origin, Destination, Dates).
3. Do not hallucinate prices or schedules. Only rely on the data returned by the tool.
4. Upon successful data retrieval, wrap the search results into a `searchDataURI` artifact.
5. Stop generating and implicitly pass the data URI to the Auditor Agent.

Format: Output a concise execution log of the queries run and the resulting data artifact pointer.""",
    tools=[search_public_travel_tool]
)

AuditorSchema = create_model("AuditorSchema", isAligned=(bool, ...), approvedDataURI=(str, ...), needsRetry=(bool, ...))

auditor = LlmAgent(
    name="auditor",
    model=Gemini(model="gemini-2.5-pro"),
    instruction="""You are the Travel Auditor Agent (Quality Assurance).
Your role: Inspect the raw inventory data (flights/hotels) retrieved by the Querying agent and ensure it fully aligns with the traveler's stated constraints.
Task Breakdown:
1. Read the `searchDataURI` provided by the Querying Agent.
2. Use the `validate_preferences_tool` to check the data against user profile constraints (Max Budget, Hotel Star Ratings, Max Layovers).
3. If the data exceeds the budget or violates layover constraints, set `needsRetry=True` and `isAligned=False`.
4. If the data perfectly matches the traveler's criteria, set `needsRetry=False`, `isAligned=True`, and output the `approvedDataURI`.

Format: Your output must strictly adhere to the predefined AuditorSchema JSON format for routing.""",
    tools=[validate_preferences_tool],
    output_schema=AuditorSchema
)

reporting = LlmAgent(
    name="reporting",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Travel Reporting & UI Synthesizer Agent.
Your role: Transform the final, audited travel inventory into a beautiful, user-facing itinerary presentation.
Task Breakdown:
1. Ingest the `approvedDataURI` from the Auditor Agent.
2. Formulate a compelling narrative about the "vibe" of the trip based on the selected hotels and flights.
3. Use the `generate_vibe_diff_tool` to convert the raw JSON inventory into declarative Agent-to-User Interface (A2UI) schemas (Cards, Lists, Deep Links).
4. Emphasize total estimated costs, layover clarity, and direct booking links.

Format: Output the final UI rendering payload. Do not expose internal IDs or raw JSON arrays directly to the user.""",
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
