import re

content = open("app/tools.py").read()

def repl(m):
    return """async def generate_vibe_diff_tool(approvedDataURI: str, tool_context: ToolContext) -> list[dict]:
    import json
    filename = approvedDataURI.replace('artifact://', '')
    part = await tool_context.load_artifact(filename)
    components = []
    
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
                    "trailing_details": f'${flight.get("price", 0):.2f}',
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
                    "trailing_details": f'${hotel.get("price_per_night", 0):.2f} / nt',
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
"""

new_content = re.sub(r'async def generate_vibe_diff_tool.*?return \w+', repl, content, flags=re.DOTALL)
open("app/tools.py", "w").write(new_content)
