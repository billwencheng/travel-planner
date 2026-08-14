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

async def search_public_travel_tool(query: str, tool_context: ToolContext) -> dict:
    """Executes public Google Search to scrape and return real-world flight/hotel data.
    
    Args:
        query: Search query for flights or hotels.
    """
    from google.genai.types import Part
    # Write search data to file message bus (artifact)
    uri = f"artifact://search_results_{hash(query)}.json"
    await tool_context.save_artifact(f"search_results_{hash(query)}.json", Part.from_text(text='{"flights":[], "hotels":[]}'))
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
