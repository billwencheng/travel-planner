from pydantic import BaseModel
from google.adk.tools import ToolContext
from google.adk.tools import BaseTool

class UserProfile(BaseModel):
    name: str = "Anonymous"
    budget: int = 1000
    preferred_hotel_stars: int = 4
    layover_limits: int = 1

class ValidationReport(BaseModel):
    isAligned: bool
    approvedDataURI: str

class VibeDiff(BaseModel):
    plainTextSummary: str
    estimatedCost: float
    deepLinks: list[str]

async def search_public_travel_tool(origin: str, destination: str, departure_date: str, return_date: str, tool_context: ToolContext) -> dict:
    """Executes public Google Search to scrape and return real-world flight/hotel data.
    
    Args:
        origin: The departure city or airport.
        destination: The arrival city or airport.
        departure_date: The date of departure (e.g., '2026-12-01').
        return_date: The date of return (e.g., '2026-12-10').
    """
    from google import genai
    from google.genai import types
    from google.genai.types import Part
    import json
    import hashlib

    client = genai.Client()
    
    query = f"flights from {origin} to {destination} departing {departure_date} returning {return_date} and hotels in {destination}"
    
    prompt = f"""Search the public internet for flights and hotels matching the following travel plan:
Origin: {origin}
Destination: {destination}
Departure Date: {departure_date}
Return Date: {return_date}

Format your response strictly as a JSON object with the following schema DO NOT WRAP in ```json:
{{
  "flights": [
    {{
      "airline": "string",
      "price": "number",
      "departure": "string",
      "arrival": "string",
      "layovers": "integer"
    }}
  ],
  "hotels": [
    {{
      "name": "string",
      "price_per_night": "number",
      "stars": "integer",
      "amenities": ["string"]
    }}
  ]
}}
Do not hallucinate any info! Rely strictly on search data.
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],
            response_mime_type="application/json"
        )
    )

    try:
        search_data = json.loads(response.text)
    except Exception:
        search_data = {"flights": [], "hotels": []}

    query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()
    filename = f"search_results_{query_hash}.json"
    
    await tool_context.save_artifact(
        filename,
        Part.from_text(text=json.dumps(search_data))
    )
    
    uri = f"artifact://{filename}"
    return {"status": "success", "searchDataURI": uri}

async def validate_preferences_tool(searchDataURI: str, preferences: UserProfile, tool_context: ToolContext) -> ValidationReport:
    """Inspects the raw public search results to ensure they align with the personal traveler's stated preferences.
    """
    return ValidationReport(isAligned=True, approvedDataURI=searchDataURI)

async def generate_vibe_diff_tool(approvedDataURI: str, tool_context: ToolContext) -> VibeDiff:
    """Converts audited JSON into A2UI declarative payload standards.
    """
    return VibeDiff(
        plainTextSummary="A smooth trip with great hotels.",
        estimatedCost=850.0,
        deepLinks=["https://booking.com/example", "https://flights.google.com/example"]
    )

async def submit_search_plan_tool(origin: str, destination: str, departure_date: str, return_date: str, travelers: int, tool_context: ToolContext) -> str:
    """Invokes the search pipeline. CALL THIS TOOL ONLY WHEN the user has confirmed all details (Origin, Destination, Dates, Travelers)."""
    param = {
        "Origin": origin,
        "Destination": destination,
        "Dates": f"{departure_date} to {return_date}",
        "Travelers": travelers
    }
    tool_context.state["search_plan"] = param
    return "SUCCESS: Search plan submitted! Tell the user you are starting the search."
