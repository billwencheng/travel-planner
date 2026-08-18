import re

with open("app/tools.py") as f:
    code = f.read()

code = code.replace("class VibeDiff(BaseModel):\n    plainTextSummary: str\n    estimatedCost: float\n    flights: list[FlightDetail]\n    hotels: list[HotelDetail]\n    deepLinks: list[str]", "")

code = code.replace("async def generate_vibe_diff_tool(approvedDataURI: str, tool_context: ToolContext) -> VibeDiff:", "async def generate_vibe_diff_tool(approvedDataURI: str, tool_context: ToolContext) -> list[dict]:")

code = re.sub(r'    cost = 0\.0\n    summary_sentences = \[\][\s\S]*?return VibeDiff\([^)]+\)\n', r"""    components = []
    
    if part and getattr(part, 'text', None):
        try:
            data = json.loads(part.text)
            flights = data.get('flights', [])
            hotels = data.get('hotels', [])
            
            flight_list_items = []
            for flight in flights:
                flight_list_items.append({
                    "type": "list_item",
                    "headline": flight.get("airline", "Airline"),
                    "details": f'{flight.get("departure", "")} to {flight.get("arrival", "")}',
                    "trailing_details": f'${float(flight.get("price", 0)):.2f}',
                })
            
            if flight_list_items:
                components.append({
                    "type": "list_card_component",
                    "title": "Flights",
                    "components": flight_list_items
                })
                
            hotel_list_items = []
            for hotel in hotels:
                hotel_list_items.append({
                    "type": "list_item",
                    "headline": hotel.get("name", "Hotel"),
                    "details": f'{hotel.get("stars", 4)} stars',
                    "trailing_details": f'${float(hotel.get("price_per_night", 0)):.2f} / nt',
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
            "fontStyle": "body_large"
        })

    return components
""", code)

with open("app/tools.py", "w") as f:
    f.write(code)
