from typing import Any

from pydantic import BaseModel


class Entity(BaseModel):
    entity_id: str


class LightEntity(Entity):
    brightness_255: int = 255
    color_name: str = "yellow"


class MediaEntity(Entity):
    source: str = "Infuse"
    volume_frac: float = 0.1


class ListEntitiesResponse(BaseModel):
    entities: dict[str, dict[str, Any]]


class ListEntitiesSimpleResponse(BaseModel):
    entities: dict[str, str]


class ListResponse(BaseModel):
    items: list[str]


class PlayMediaRequest(BaseModel):
    library: str
    media_id: str
    client_id: str


class ControlMediaRequest(BaseModel):
    client_id: str
