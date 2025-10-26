from pydantic import BaseModel


class DatetimeResponse(BaseModel):
    datetime: str


class ListResponse(BaseModel):
    items: list[str]
