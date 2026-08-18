import sys

content = open("app/tools.py").read()
# Replace VibeDiff return type
new_content = content.replace("async def generate_vibe_diff_tool(approvedDataURI: str, tool_context: ToolContext) -> VibeDiff:", "async def generate_vibe_diff_tool(approvedDataURI: str, tool_context: ToolContext) -> list[dict]:")

replacement = """
    components = []
    
    if part and getattr(part, 'text', None):
        try:
            data = json.loads(part.text)
            flights = data.get('flights', [])
            hotels = data.get('hotels', [])
            
            # Add summary text
            components.append({
                "type": "text",
                "text": f"Found these great options for your trip (est. ${cost:.2f}):",
                "font_style": {"tag": "title_medium"}
            })
            
            flight_list_items = []
            for index, flight in enumerate(flights):
                airline = flight.get("airline", "the airline")
                flight_price = float(flight.get("price", 0))
                origin = flight.get("departure", "")
                destination = flight.get("arrival", "")
                link = f"https://flights.google.com/search?q={origin}+to+{destination}"
                
                flight_list_items.append({
                    "type": "list_item",
                    "headline": airline,
                    "details": f"{origin} to {destination} ({flight.get('layovers', 0)} layovers)",
                    "trailing_details": f"${flight_price:.2f}",
                    "on_click": {"type": "link", "uri": link}
                })
            
            if flight_list_items:
                components.append({
                    "type": "list_card_component",
                    "title": "Flights",
                    "components": flight_list_items
                })
                
            hotel_list_items = []
            for index, hotel in enumerate(hotels):
                hotel_price = float(hotel.get("price_per_night", 0))
                hotel_name = hotel.get("name", "a hotel")
                link = f"https://booking.com/search?q={hotel_name.replace(' ', '+')}"
                hotel_list_items.append({
                    "type": "list_item",
                    "headline": hotel_name,
                    "details": f"{hotel.get('stars', 4)} stars",
                    "trailing_details": f"${hotel_price:.2f} / nt",
                    "accessories": [{"text": "WiFi included"}],
                    "on_click": {"type": "link", "uri": link}
                })
                
            if hotel_list_items:
                components.append({
                    "type": "list_card_component",
                    "title": "Hotels",
                    "components": hotel_list_items
                })
                
        except Exception:
            pass

    if not components:
        components.append({
            "type": "text",
            "text": "A smooth trip with great hotels.",
            "font_style": {"tag": "body_large"}
        })

    return components
"""
import re
new_content = re.sub(r"    cost = 0\.0\n    summary_sentences = \[\][\s\S]*return VibeDiff\([^)]*\)", replacement.strip() + "\n", new_content)
with open("app/tools.py", "w") as f:
    f.write(new_content)
