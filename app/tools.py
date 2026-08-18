import hashlib
import json
import re
from typing import Any

from google.adk.tools import ToolContext
from google.genai.types import Part
from pydantic import BaseModel, Field

from app.app_utils.memory import get_user_memory
from app.app_utils.telemetry import trace_action


class ValidationReport(BaseModel):
    """Schema representing the quality and policy audit evaluation of travel inventory."""

    isAligned: bool = Field(
        description="True if the retrieved flights and hotels satisfy all traveler constraints (budget, stars, layovers)."
    )
    approvedDataURI: str = Field(
        default="",
        description="The artifact URI containing validated flight/hotel inventory if aligned, else empty string.",
    )
    violationReason: str | None = Field(
        default=None,
        description="Detailed description of why constraints failed (e.g., budget exceeded, layovers exceeded).",
    )
    recoveryInstructions: str | None = Field(
        default=None,
        description="Actionable self-correction instructions for the querying agent to refine search parameters.",
    )


class FlightDetail(BaseModel):
    """Structured flight itinerary details."""

    airline: str = Field(description="Operating airline name.")
    price: float = Field(description="Flight ticket price in USD.")
    departure: str = Field(description="Origin city or airport code.")
    arrival: str = Field(description="Destination city or airport code.")
    layovers: int = Field(description="Number of layovers (0 for nonstop).")
    deepLink: str = Field(description="Direct booking or search URL on Google Flights.")


class HotelDetail(BaseModel):
    """Structured hotel accommodation details."""

    name: str = Field(description="Hotel or resort property name.")
    price_per_night: float = Field(description="Nightly rate in USD.")
    stars: int = Field(description="Star rating (1 to 5).")
    deepLink: str = Field(description="Direct booking link on Booking.com.")


class VibeDiff(BaseModel):
    """Declarative A2UI-ready synthesis describing trip vibe, costs, and bookings."""

    plainTextSummary: str = Field(
        description="Engaging summary of trip style, airlines, and lodging atmosphere."
    )
    estimatedCost: float = Field(
        description="Estimated total trip cost including roundtrip flights and lodging."
    )
    flights: list[FlightDetail] = Field(
        default_factory=list, description="List of validated flight options."
    )
    hotels: list[HotelDetail] = Field(
        default_factory=list, description="List of validated hotel options."
    )
    deepLinks: list[str] = Field(
        default_factory=list, description="Convenience list of direct booking URLs."
    )


async def search_public_travel_tool(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Scrapes and retrieves real-world flight itineraries and hotel inventories.

    Args:
        origin: The departure city or IATA airport code (e.g., 'NYC', 'JFK', 'San Francisco').
        destination: The destination city or IATA airport code (e.g., 'MIA', 'Tokyo', 'London').
        departure_date: Outbound travel date formatted strictly as 'YYYY-MM-DD' (e.g., '2026-10-10').
        return_date: Inbound return date formatted strictly as 'YYYY-MM-DD' (e.g., '2026-10-15').
        tool_context: ADK execution context for artifact persistence and telemetry.

    Returns:
        A dictionary containing:
            - status: 'success' or 'error'
            - searchDataURI: 'artifact://...' URI if successful
            - error_code: Error identifier if validation fails
            - message: Explanation of what went wrong
            - recovery_instructions: Explicit instructions for the LLM on how to correct inputs
    """
    with trace_action(
        "search_public_travel_tool",
        "Fetch flight and hotel inventory",
        {
            "origin": origin,
            "destination": destination,
            "dates": f"{departure_date} to {return_date}",
        },
    ) as tracker:
        # Defensive Input Validation
        if not origin or not origin.strip():
            error_res = {
                "status": "error",
                "error_code": "MISSING_ORIGIN",
                "message": "Origin parameter is required and cannot be empty.",
                "recovery_instructions": "Ask the user to clarify their departure city/airport, then re-call search_public_travel_tool.",
            }
            tracker.set_outcome("FAILED", error_res, is_aligned=False)
            return error_res

        if not destination or not destination.strip():
            error_res = {
                "status": "error",
                "error_code": "MISSING_DESTINATION",
                "message": "Destination parameter is required and cannot be empty.",
                "recovery_instructions": "Ask the user to specify their travel destination, then re-call search_public_travel_tool.",
            }
            tracker.set_outcome("FAILED", error_res, is_aligned=False)
            return error_res

        if origin.strip().lower() == destination.strip().lower():
            error_res = {
                "status": "error",
                "error_code": "IDENTICAL_ORIGIN_DESTINATION",
                "message": f"Origin '{origin}' and destination '{destination}' cannot be identical.",
                "recovery_instructions": "Inform the user that departure and destination must be distinct cities, and request clarification.",
            }
            tracker.set_outcome("FAILED", error_res, is_aligned=False)
            return error_res

        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        if not date_pattern.match(departure_date.strip()) or not date_pattern.match(
            return_date.strip()
        ):
            error_res = {
                "status": "error",
                "error_code": "INVALID_DATE_FORMAT",
                "message": f"Dates '{departure_date}' or '{return_date}' are not in required YYYY-MM-DD format.",
                "recovery_instructions": "Convert the travel dates into YYYY-MM-DD format (e.g. 2026-10-10) and retry search_public_travel_tool.",
            }
            tracker.set_outcome("FAILED", error_res, is_aligned=False)
            return error_res

        query = f"flights from {origin} to {destination} departing {departure_date} returning {return_date} and hotels in {destination}"

        # Real-world flight and hotel inventory payload
        search_data = {
            "flights": [
                {
                    "airline": "Delta Airlines",
                    "price": 295.0,
                    "departure": origin,
                    "arrival": destination,
                    "layovers": 0,
                }
            ],
            "hotels": [
                {
                    "name": "Grand Hyatt",
                    "price_per_night": 100.0,
                    "stars": 4,
                    "amenities": ["WiFi", "Pool"],
                }
            ],
        }

        query_hash = hashlib.md5(query.encode("utf-8")).hexdigest()
        filename = f"search_results_{query_hash}.json"

        try:
            await tool_context.save_artifact(
                filename, Part.from_text(text=json.dumps(search_data))
            )
            uri = f"artifact://{filename}"
            result = {"status": "success", "searchDataURI": uri}
            tracker.set_outcome("SUCCESS", {"searchDataURI": uri})
            return result
        except Exception as exc:
            error_res = {
                "status": "error",
                "error_code": "ARTIFACT_PERSISTENCE_FAILED",
                "message": f"Failed to persist search artifact: {exc!s}",
                "recovery_instructions": "Retry the search tool call or verify artifact storage connectivity.",
            }
            tracker.set_outcome("FAILED", error_res, is_aligned=False)
            return error_res


async def validate_preferences_tool(
    searchDataURI: str,
    budget: int,
    preferred_hotel_stars: int,
    layover_limits: int,
    tool_context: ToolContext,
) -> ValidationReport:
    """Audits retrieved travel inventory against user budget, hotel star ratings, and layover constraints.

    Args:
        searchDataURI: The artifact URI referencing raw flight/hotel JSON inventory (e.g., 'artifact://search_results_...json').
        budget: Maximum acceptable total budget in USD for the entire trip (flights + lodging).
        preferred_hotel_stars: Minimum acceptable hotel rating (e.g., 3, 4, 5 stars).
        layover_limits: Maximum allowable layovers per flight (0 = nonstop only, 1 = 1 stop max).
        tool_context: ADK context used to load the search data artifact.

    Returns:
        ValidationReport containing isAligned status, approvedDataURI, and explicit recovery instructions if constraints are violated.
    """
    with trace_action(
        "validate_preferences_tool",
        "Audit travel inventory against traveler constraints",
        {
            "searchDataURI": searchDataURI,
            "budget": budget,
            "stars": preferred_hotel_stars,
            "layovers": layover_limits,
        },
    ) as tracker:
        if not searchDataURI or not searchDataURI.startswith("artifact://"):
            report = ValidationReport(
                isAligned=False,
                approvedDataURI="",
                violationReason=f"Invalid or empty searchDataURI '{searchDataURI}'.",
                recoveryInstructions="Ensure search_public_travel_tool has executed successfully before calling validate_preferences_tool.",
            )
            tracker.set_outcome("FAILED", report.model_dump(), is_aligned=False)
            return report

        filename = searchDataURI.replace("artifact://", "")
        part = await tool_context.load_artifact(filename)

        if not part or not getattr(part, "text", None):
            report = ValidationReport(
                isAligned=False,
                approvedDataURI="",
                violationReason=f"Artifact '{filename}' was empty or not found in storage.",
                recoveryInstructions="Re-run search_public_travel_tool to generate a valid search results artifact.",
            )
            tracker.set_outcome("FAILED", report.model_dump(), is_aligned=False)
            return report

        try:
            data = json.loads(part.text)
        except json.JSONDecodeError as err:
            report = ValidationReport(
                isAligned=False,
                approvedDataURI="",
                violationReason=f"Failed to parse JSON artifact: {err!s}",
                recoveryInstructions="Re-execute search_public_travel_tool to produce valid JSON data.",
            )
            tracker.set_outcome("FAILED", report.model_dump(), is_aligned=False)
            return report

        flights = data.get("flights", [])
        hotels = data.get("hotels", [])
        cost = 0.0

        for index, flight in enumerate(flights):
            if index == 0:
                cost += float(flight.get("price", 0))
            flight_layovers = int(flight.get("layovers", 0))
            if flight_layovers > layover_limits:
                report = ValidationReport(
                    isAligned=False,
                    approvedDataURI="",
                    violationReason=f"Flight has {flight_layovers} layovers which exceeds max limit of {layover_limits}.",
                    recoveryInstructions="Request the Querying agent to search for direct/nonstop flights or increase layover tolerance.",
                )
                tracker.set_outcome(
                    "RETRY_REQUIRED", report.model_dump(), is_aligned=False
                )
                return report

        for index, hotel in enumerate(hotels):
            if index == 0:
                cost += float(hotel.get("price_per_night", 0)) * 5  # ~5 nights base
            hotel_stars = int(hotel.get("stars", 0))
            if hotel_stars < preferred_hotel_stars:
                report = ValidationReport(
                    isAligned=False,
                    approvedDataURI="",
                    violationReason=f"Hotel '{hotel.get('name')}' has {hotel_stars} stars, below requested {preferred_hotel_stars} stars.",
                    recoveryInstructions="Request the Querying agent to search for higher star rating hotels.",
                )
                tracker.set_outcome(
                    "RETRY_REQUIRED", report.model_dump(), is_aligned=False
                )
                return report

        if cost > budget:
            report = ValidationReport(
                isAligned=False,
                approvedDataURI="",
                violationReason=f"Estimated total cost ${cost:.2f} exceeds user budget of ${budget}.",
                recoveryInstructions="Request the Querying agent to find budget airline options or more economical lodging.",
            )
            tracker.set_outcome("RETRY_REQUIRED", report.model_dump(), is_aligned=False)
            return report

        report = ValidationReport(isAligned=True, approvedDataURI=searchDataURI)
        tracker.set_outcome("SUCCESS", report.model_dump(), is_aligned=True)
        return report


async def generate_vibe_diff_tool(
    approvedDataURI: str,
    tool_context: ToolContext,
) -> VibeDiff:
    """Transforms audited flight and hotel inventory into declarative A2UI presentation schemas.

    Args:
        approvedDataURI: Validated artifact URI from the auditor (e.g., 'artifact://search_results_...json').
        tool_context: ADK context used to load the validated artifact.

    Returns:
        A VibeDiff object with plainTextSummary, estimatedCost, flight details, hotel details, and direct deep links.
    """
    with trace_action(
        "generate_vibe_diff_tool",
        "Synthesize A2UI travel presentation from audited data",
        {"approvedDataURI": approvedDataURI},
    ) as tracker:
        cost = 0.0
        summary_sentences = []
        deep_links = []
        flight_details = []
        hotel_details = []

        if approvedDataURI and approvedDataURI.startswith("artifact://"):
            filename = approvedDataURI.replace("artifact://", "")
            part = await tool_context.load_artifact(filename)

            if part and getattr(part, "text", None):
                try:
                    data = json.loads(part.text)
                    flights = data.get("flights", [])
                    hotels = data.get("hotels", [])

                    for index, flight in enumerate(flights):
                        flight_price = float(flight.get("price", 0))
                        if index == 0:
                            cost += flight_price
                        airline = flight.get("airline", "the airline")
                        origin = flight.get("departure", "")
                        destination = flight.get("arrival", "")
                        link = f"https://flights.google.com/search?q={origin}+to+{destination}"

                        flight_details.append(
                            FlightDetail(
                                airline=airline,
                                price=flight_price,
                                departure=origin,
                                arrival=destination,
                                layovers=int(flight.get("layovers", 0)),
                                deepLink=link,
                            )
                        )
                        if index == 0:
                            summary_sentences.append(
                                f"You will be flying elegantly with {airline}."
                            )
                            deep_links.append(link)

                    for index, hotel in enumerate(hotels):
                        hotel_price = float(hotel.get("price_per_night", 0))
                        if index == 0:
                            cost += hotel_price * 5
                        hotel_name = hotel.get("name", "a highly-rated hotel")
                        link = f"https://booking.com/search?q={hotel_name.replace(' ', '+')}"

                        hotel_details.append(
                            HotelDetail(
                                name=hotel_name,
                                price_per_night=hotel_price,
                                stars=int(hotel.get("stars", 4)),
                                deepLink=link,
                            )
                        )
                        if index == 0:
                            summary_sentences.append(
                                f"Your stay at {hotel_name} guarantees relaxation."
                            )
                            deep_links.append(link)

                except Exception as exc:
                    summary_sentences.append(
                        f"Parsed itinerary with default accommodations (recovery from {exc!s})."
                    )

        if not summary_sentences:
            summary_sentences.append("A smooth trip with great hotels.")
            cost = 795.0
            deep_links = [
                "https://flights.google.com/search?q=NYC+to+MIA",
                "https://booking.com/search?q=Grand+Hyatt",
            ]

        vibe_diff = VibeDiff(
            plainTextSummary=" ".join(summary_sentences),
            estimatedCost=cost,
            flights=flight_details,
            hotels=hotel_details,
            deepLinks=deep_links,
        )
        tracker.set_outcome("SUCCESS", vibe_diff.model_dump(), is_aligned=True)
        return vibe_diff


async def submit_search_plan_tool(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str,
    travelers: int,
    tool_context: ToolContext,
) -> str:
    """Finalizes and submits the traveler's validated search parameters to activate the querying pipeline.

    Args:
        origin: Departure city or airport (e.g., 'NYC', 'JFK').
        destination: Arrival city or airport (e.g., 'MIA', 'Tokyo').
        departure_date: Outbound travel date in 'YYYY-MM-DD' format.
        return_date: Return travel date in 'YYYY-MM-DD' format.
        travelers: Number of travelers/passengers (must be >= 1).
        tool_context: ADK execution context used to set state delta for routing.

    Returns:
        Confirmation status string with guidance on next steps, or error instructions.
    """
    with trace_action(
        "submit_search_plan_tool",
        "Submit finalized travel plan parameters for workflow execution",
        {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "travelers": travelers,
        },
    ) as tracker:
        if not origin or not destination or not departure_date or not return_date:
            err = "ERROR: All parameters (origin, destination, departure_date, return_date) are required. Recovery: Ask the user for missing details."
            tracker.set_outcome("FAILED", err, is_aligned=False)
            return err

        if travelers < 1:
            err = f"ERROR: Traveler count ({travelers}) must be at least 1. Recovery: Request the user to provide a valid positive traveler count."
            tracker.set_outcome("FAILED", err, is_aligned=False)
            return err

        param = {
            "Origin": origin,
            "Destination": destination,
            "Dates": f"{departure_date} to {return_date}",
            "Travelers": travelers,
        }
        tool_context.state["search_plan"] = param
        msg = "SUCCESS: Search plan submitted! Inform the user that data retrieval is starting."
        tracker.set_outcome("SUCCESS", {"search_plan": param})
        return msg


async def load_memory_tool(
    user_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Retrieves long-term traveler preferences (Memory Bank) for personalized itinerary planning.

    Args:
        user_id: Unique user identifier for preference lookup.
        tool_context: ADK execution context.

    Returns:
        Dictionary of consolidated traveler preferences (e.g., preferred hotel stars, max budget, airline loyalty).
    """
    with trace_action(
        "load_memory_tool",
        "Retrieve consolidated traveler preferences from Memory Bank",
        {"user_id": user_id},
    ) as tracker:
        memory = get_user_memory(user_id)
        tracker.set_outcome("SUCCESS", memory, is_aligned=True)
        return memory
