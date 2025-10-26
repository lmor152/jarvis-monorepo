from pydantic import BaseModel


class ListMediaResponse(BaseModel):
    media: dict[str, list[str]]


class PlayMediaRequest(BaseModel):
    library: str
    media_id: str
    client_id: str


class ControlMediaRequest(BaseModel):
    client_id: str
