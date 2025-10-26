from fastapi import APIRouter, Depends

from backend.core.ha_client import SimpleHAClient
from backend.models.ha import (
    Entity,
    LightEntity,
    ListEntitiesResponse,
    ListEntitiesSimpleResponse,
    MediaEntity,
)
from backend.services.ha import get_ha_client, list_entities

router = APIRouter(
    prefix="/ha",
    tags=["ha"],
    responses={404: {"description": "Not found"}},
)


@router.get("/list-entities-simple")
async def get_list_entities_simple(
    client: SimpleHAClient = Depends(get_ha_client),
) -> ListEntitiesSimpleResponse:
    filtered_entities = list_entities(client)
    return ListEntitiesSimpleResponse(
        entities={
            k: v["attributes"]["friendly_name"] for k, v in filtered_entities.items()
        }
    )


@router.get("/list-entities-full")
async def get_list_entities(
    client: SimpleHAClient = Depends(get_ha_client),
) -> ListEntitiesResponse:
    filtered_entities = list_entities(client)
    return ListEntitiesResponse(entities=filtered_entities)


@router.post("/turn-on")
async def turn_on_entity(
    entity: Entity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> str:
    client.turn_on(entity.entity_id)
    return f"turned on {entity.entity_id}"


@router.post("/turn-off")
async def turn_off_entity(
    entity: Entity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> str:
    client.turn_off(entity.entity_id)
    return f"turned off {entity.entity_id}"


@router.post("/turn-on-light-custom")
async def turn_on_light_custom(
    entity: LightEntity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> str:
    client.light_turn_on(
        entity_id=entity.entity_id,
        brightness=entity.brightness_255,
        color_name=entity.color_name,
    )
    return f"turned on {entity.entity_id}"


@router.post("/pause-media")
async def pause_media(
    entity: Entity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> str:
    client.media_player_pause(entity.entity_id)
    return f"paused media on {entity.entity_id}"


@router.post("/play-media")
async def play_media(
    entity: Entity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> str:
    client.media_player_play(entity.entity_id)
    return f"played media on {entity.entity_id}"


@router.post("/media-get-sources")
async def media_get_sources(
    entity: Entity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> list[str]:
    return client.media_player_get_sources(entity.entity_id)


@router.post("/media-select-source")
async def media_select_source(
    entity: MediaEntity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> str:
    client.media_player_select_source(entity.entity_id, entity.source)
    return f"selected source {entity.source} on {entity.entity_id}"


@router.post("/media-set-volume")
async def media_set_volume(
    entity: MediaEntity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> str:
    client.media_player_set_volume(entity.entity_id, entity.volume_frac)
    return f"set volume to {entity.volume_frac} on {entity.entity_id}"


@router.post("/media-volume-up")
async def media_volume_up(
    entity: Entity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> str:
    client.media_player_volume_up(entity.entity_id)
    return f"volume up on {entity.entity_id}"


@router.post("/media-volume-down")
async def media_volume_down(
    entity: Entity,
    client: SimpleHAClient = Depends(get_ha_client),
) -> str:
    client.media_player_volume_down(entity.entity_id)
    return f"volume down on {entity.entity_id}"
