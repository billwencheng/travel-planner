from pydantic import BaseModel, Field
from typing import List, Optional, Any

class A2UIClick(BaseModel):
    type: str = "link"
    uri: str

class A2UIAccessory(BaseModel):
    text: str

class A2UIListImage(BaseModel):
    image_uri: str = ""

class A2UIListItem(BaseModel):
    type: str = "list_item"
    headline: str = ""
    details: str = ""
    trailing_details: str = ""
    accessories: List[A2UIAccessory] = []
    on_click: Optional[A2UIClick] = None

class A2UIText(BaseModel):
    type: str = "text"
    text: str
    fontStyle: str = "body_large"

class A2UIListCard(BaseModel):
    type: str = "list_card_component"
    title: str = ""
    components: List[Any] = []

class A2UIPayload(BaseModel):
    type: str = "layout_card"
    components: List[Any] = []

