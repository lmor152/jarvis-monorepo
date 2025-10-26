import datetime
import logging

from fastapi import APIRouter

from backend.models.generic import DatetimeResponse
from backend.core.settings import settings

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/generic",
    tags=["generic"],
    responses={404: {"description": "Not found"}},
)


@router.get("/datetime")
async def get_datetime():
    return DatetimeResponse(datetime=datetime.datetime.now(settings.tz).isoformat())

