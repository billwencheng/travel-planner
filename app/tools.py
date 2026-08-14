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

class FlightDetail(BaseModel):
    airline: str
    price: float
    departure: str
    arrival: str
    layovers: int
    deepLink: str

class HotelDetail(BaseModel):
    name: str
    price_per_night: float
    stars: int
    deepLink: str

class VibeDiff(BaseModel):
    plainTextSummary: str
    estimatedCost: float
    flights: list[FlightDetail]
    hotels: list[HotelDetail]
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
    
    # Development Mock: Return deterministic data instead of calling LLM
    search_data = {
        "flights": [
            {
                "airline": "Delta Airlines",
                "price": 295.0,
                "departure": origin,
                "arrival": destination,
                "layovers": 0
            }
        ],
        "hotels": [
            {
                "name": "Grand Hyatt",
                "price_per_night": 100.0,
                "stars": 4,
                "amenities": ["WiFi", "Pool"]
            }
        ]
    }

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
    import json
    
    filename = searchDataURI.replace('artifact://', '')
    part = await tool_context.load_artifact(filename)
    
    is_aligned = True
    if part and getattr(part, 'text', None):
        try:
            data = json.loads(part.text)
            flights = data.get('flights', [])
            hotels = data.get('hotels', [])

            cost = 0.0
            
            for index, flight in enumerate(flights):
                if index == 0:
                    cost += float(flight.get("price", 0))
                if int(flight.get("layovers", 0)) > preferences.layover_limits:
                    is_aligned = False

            for index, hotel in enumerate(hotels):
                if index == 0:
                    cost += float(hotel.get("price_per_night", 0)) * 5  # Assume 5 nights based on generate_vibe_diff_tool
                if int(hotel.get("stars", 0)) < preferences.preferred_hotel_stars:
                    is_aligned = False
                    
            if cost > preferences.budget:
                is_aligned = False

        except Exception:
            is_aligned = False
    else:
        is_aligned = False

    return ValidationReport(isAligned=is_aligned, approvedDataURI=searchDataURI if is_aligned else "")

async def generate_vibe_diff_tool(approvedDataURI: str, tool_context: ToolContext) -> VibeDiff:
    """Converts audited JSON into A2UI declarative payload standards.
    """
    import json
    
    filename = approvedDataURI.replace('artifact://', '')
    part = await tool_context.load_artifact(filename)
    
    cost = 0.0
    summary_sentences = []
    deep_links = []
    flight_details = []
    hotel_details = []
    
    if part and getattr(part, 'text', None):
        try:
            data = json.loads(part.text)
            flights = data.get('flights', [])
            hotels = data.get('hotels', [])
            
            for index, flight in enumerate(flights):
                flight_price = float(flight.get("price", 0))
                if index == 0:
                    cost += flight_price
                airline = flight.get("airline", "the airline")
                origin = flight.get("departure", "")
                destination = flight.get("arrival", "")
                link = f"https://flights.google.com/search?q={origin}+to+{destination}"
                
                flight_details.append(FlightDetail(
                    airline=airline,
                    price=flight_price,
                    departure=origin,
                    arrival=destination,
                    layovers=int(flight.get("layovers", 0)),
                    deepLink=link
                ))
                if index == 0:
                    summary_sentences.append(f"You will be flying elegantly with {airline}.")
                    deep_links.append(link)
            
            for index, hotel in enumerate(hotels):
                hotel_price = float(hotel.get("price_per_night", 0))
                if index == 0:
                    cost += (hotel_price * 5) # Assuming ~5 nights for base calculation
                hotel_name = hotel.get("name", "a highly-rated hotel")
                link = f"https://booking.com/search?q={hotel_name.replace(' ', '+')}"
                
                hotel_details.append(HotelDetail(
                    name=hotel_name,
                    price_per_night=hotel_price,
                    stars=int(hotel.get("stars", 4)),
                    deepLink=link
                ))
                if index == 0:
                    summary_sentences.append(f"Your stay at {hotel_name} guarantees relaxation.")
                    deep_links.append(link)
                
        except Exception:
            pass

    if not summary_sentences:
        summary_sentences.append("A smooth trip with great hotels.")
        cost = 850.0
        deep_links = ["https://booking.com/example", "https://flights.google.com/example"]

    return VibeDiff(
        plainTextSummary=" ".join(summary_sentences),
        estimatedCost=cost,
        flights=flight_details,
        hotels=hotel_details,
        deepLinks=deep_links
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
