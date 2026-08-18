import datetime
import json

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.models import Gemini
from google.adk.workflow import Workflow
from pydantic import create_model

from .tools import (
    generate_vibe_diff_tool,
    search_public_travel_tool,
    submit_search_plan_tool,
    validate_preferences_tool,
)

current_date = datetime.datetime.now().strftime("%Y-%m-%d")

orchestrator = LlmAgent(
    name="orchestrator",
    model=Gemini(model="gemini-2.5-pro"),
    instruction=f"""You are the Orchestrator Travel Concierge Agent.
Your role: Act as the primary interface for the user's travel planning needs.

CRITICAL DATE CONTEXT: Today's date is {current_date}.
If a user provides a partial date like "08/21", resolve it to the correct year based on today's date {current_date}. All final travel dates MUST be strictly in the future.

Task Breakdown:
1. Analyze the ENTIRE conversation history to extract: Origin, Destination, Dates, and Traveler count.
2. If ANY critical info is missing, explicitly ask the user ONLY for the missing pieces. Do not hallucinate counts (e.g. if the user says "2", it means 2, not 22). Do not ask for details they have already provided.
3. Once all details are confirmed by the user, you MUST call the `submit_search_plan_tool` to finalize the plan.
4. Provide a conversational summary explicitly listing the formulated Search Plan parameters to the user.
5. GUARDRAILS: If the user asks for anything other than travel planning (e.g. coding, math, general chatting not related to travel, or policy-violating requests), politely refuse and explicitly halt the conversation. Do not use tools for off-topic requests.""",
    tools=[submit_search_plan_tool],
    include_contents="default",
)

querying = LlmAgent(
    name="querying",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Querying Data Retrieval Agent.
Your role: Fetch real-world flight itineraries and hotel inventories based on the Orchestrator's plan.
Task Breakdown:
1. Parse the travel plan parameters provided by the Orchestrator (Origin, Destination, Departure Date, Return Date).
2. Execute the `search_public_travel_tool` using these highly structured search schema parameters.
3. Do not hallucinate prices or schedules. Only rely on the data returned by the tool.
4. Upon successful data retrieval, wrap the search results into a `searchDataURI` artifact.
5. Stop generating and implicitly pass the data URI to the Auditor Agent.

Format: Produce a plain text summary showing the queried locations and the searchDataURI. Do NOT output Python code, do NOT use `print()` or code blocks. Speak natively in English.""",
    tools=[search_public_travel_tool],
)

AuditorSchema = create_model(
    "AuditorSchema",
    isAligned=(bool, ...),
    approvedDataURI=(str, ...),
    needsRetry=(bool, ...),
)

auditor = LlmAgent(
    name="auditor",
    model=Gemini(model="gemini-2.5-pro"),
    instruction="""You are the Travel Auditor Agent (Quality Assurance).
Your role: Inspect the raw inventory data (flights/hotels) retrieved by the Querying agent and ensure it fully aligns with the traveler's stated constraints.
Task Breakdown:
1. Read the `searchDataURI` provided by the Querying Agent.
2. Use the `validate_preferences_tool` to check the data against user profile constraints (Implicitly assume: Max Budget=$1000, preferred_hotel_stars=4, layover_limits=1).
3. If the data exceeds the budget or violates layover constraints, set `needsRetry=True` and `isAligned=False`.
4. If the data perfectly matches the traveler's criteria, set `needsRetry=False`, `isAligned=True`, and output the `approvedDataURI`.

Format: Your output must strictly adhere to the predefined AuditorSchema JSON format for routing.""",
    tools=[validate_preferences_tool],
    output_schema=AuditorSchema,
)

reporting = LlmAgent(
    name="reporting",
    model=Gemini(model="gemini-2.5-flash"),
    instruction="""You are the Travel Reporting & UI Synthesizer Agent.
Your role: Transform the final, audited travel inventory into a beautiful, user-facing itinerary presentation.
Task Breakdown:
1. Ingest the `approvedDataURI` from the user message.
2. YOU MUST IMMEDIATELY use the `generate_vibe_diff_tool` with the provided `approvedDataURI` to convert the raw JSON inventory into declarative A2UI schemas.
3. Formulate a compelling narrative about the "vibe" of the trip based on the returned summary.
4. Output a detailed section for "Flights" listing the exact airline, departure, arrival, and price, with its direct Google Flights booking link.
5. Output a detailed section for "Hotels" listing the exact hotel name, price per night, and stars, with its direct Booking.com link.
6. Emphasize total estimated costs and layover clarity.

Format: Your output MUST be strict A2UI declarative JSON array format. DO NOT generate simple text or generic JSON. You MUST use exactly these structures with a `type` field:
Example A2UI JSON Format:
[
  {
    "type": "text_item",
    "text": "Here is your itinerary plan!"
  },
  {
    "type": "card",
    "title": "Flight to MIA",
    "content": "Delta Airlines - Direct flight",
    "price": 295,
    "deepLink": "https://flights.google.com"
  },
  {
    "type": "list",
    "title": "Available Hotels",
    "components": [
       {
         "type": "text_item",
         "text": "Grand Hyatt - 4 Stars"
       }
    ]
  }
]
Produce valid A2UI JSON arrays consisting ONLY of the standard types: `card`, `list`, `text_item`, `divider`, `list_item`. EVERY component object in your JSON array MUST explicitly possess a `"type"` string key! DO NOT invent other types.""",
    tools=[generate_vibe_diff_tool],
)


def orchestrator_router(ctx: Context, node_input):
    """Routes execution based on whether the Orchestrator gathered all info."""
    if "search_plan" in ctx.state:
        plan = ctx.state["search_plan"]
        ctx.actions.state_delta["search_plan"] = None
        return Event(output=json.dumps(plan), route="ready")

    # If not ready, we route to '__DEFAULT__' which won't match any edge,
    # pausing execution naturally and returning control to human!
    return Event(output=node_input, route="human_input_required")


def auditor_router(node_input):
    if not node_input:
        # Failsafe if auditor returns nothing
        return Event(output=None, route="approved")
    if hasattr(node_input, "model_dump"):
        node_input = node_input.model_dump()
    elif isinstance(node_input, str):
        try:
            node_input = json.loads(node_input)
        except Exception:
            node_input = {}

    if isinstance(node_input, dict) and node_input.get("needsRetry"):
        return Event(output=json.dumps(node_input), route="retry")
    uri = node_input.get("approvedDataURI") if isinstance(node_input, dict) else None
    return Event(
        output=f"The auditor has approved the travel data. Here is the approvedDataURI: {uri}",
        route="approved",
    )


root_agent = Workflow(
    name="travel_planner",
    edges=[
        ("START", orchestrator),
        (orchestrator, orchestrator_router),
        (orchestrator_router, {"ready": querying}),
        (querying, auditor),
        (auditor, auditor_router),
        (auditor_router, {"retry": querying, "approved": reporting}),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
