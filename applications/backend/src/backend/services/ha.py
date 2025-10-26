from functools import lru_cache
from typing import Any

from backend.core.ha_client import SimpleHAClient
from backend.core.settings import settings


@lru_cache()
def get_ha_client() -> SimpleHAClient:
    return SimpleHAClient(base_url=settings.ha_url, token=settings.ha_token)


def list_entities(
    client: SimpleHAClient,
) -> dict[str, dict[str, Any]]:
    entities = client.get_entities()

    filtered_entities = {}
    for key, value in list(entities.items()):
        if any(key.startswith(d) for d in settings.ha_included_domains):
            filtered_entities[key] = value
            continue

        if any(key == e for e in settings.ha_included_entities):
            filtered_entities[key] = value
            continue

    return filtered_entities
