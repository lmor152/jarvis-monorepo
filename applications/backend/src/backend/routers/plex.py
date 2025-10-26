import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from plexapi.server import PlexServer

from backend.models.generic import ListResponse
from backend.models.plex import (
    ControlMediaRequest,
    ListMediaResponse,
    PlayMediaRequest,
)
from backend.services.plex import (
    list_clients,
    list_media,
    pause_media,
    play_media,
    resume_media,
    setup_plex,
    update_libraries,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/plex",
    tags=["plex"],
    responses={404: {"description": "Not found"}},
)


@router.get("/update-libraries")
async def get_update_libraries(plex: PlexServer = Depends(setup_plex)) -> JSONResponse:
    update_libraries(plex)
    return JSONResponse(content={"message": "Libraries updated successfully"})


@router.get("/list-media", response_model=ListMediaResponse)
async def get_media(plex: PlexServer = Depends(setup_plex)) -> ListMediaResponse:
    return ListMediaResponse(media=list_media(plex))


@router.get("/list-clients", response_model=ListResponse)
async def get_clients(plex: PlexServer = Depends(setup_plex)) -> ListResponse:
    return ListResponse(items=list_clients(plex))


@router.post("/play-media")
async def post_play_media(
    play: PlayMediaRequest, plex: PlexServer = Depends(setup_plex)
) -> JSONResponse:
    try:
        play_media(plex, play.library, play.media_id, play.client_id)
        return JSONResponse(content={"message": "Media is playing"}, status_code=200)
    except Exception as e:
        LOGGER.error(f"Error playing media: {e}")
        return JSONResponse(content={"message": "Error playing media"}, status_code=500)


@router.post("/pause-media")
async def post_pause_media(
    media: ControlMediaRequest, plex: PlexServer = Depends(setup_plex)
) -> JSONResponse:
    try:
        pause_media(plex, media.client_id)
        return JSONResponse(content={"message": "Media is paused"}, status_code=200)
    except Exception as e:
        LOGGER.error(f"Error pausing media: {e}")
        return JSONResponse(content={"message": "Error pausing media"}, status_code=500)


@router.post("/resume-media")
async def post_resume_media(
    media: ControlMediaRequest, plex: PlexServer = Depends(setup_plex)
) -> JSONResponse:
    try:
        resume_media(plex, media.client_id)
        return JSONResponse(content={"message": "Media is resumed"}, status_code=200)
    except Exception as e:
        LOGGER.error(f"Error resuming media: {e}")
        return JSONResponse(
            content={"message": "Error resuming media"}, status_code=500
        )
