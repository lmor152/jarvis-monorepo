import logging
from typing import Literal

import requests

from applications.assistant.src.assistant.core.settings import settings

LOGGER = logging.getLogger(__name__)


def get_tools_schema():
    """Fetches the available tools and schema from homelab-api."""
    resp = requests.get(f"{settings.backend_url}/schema")
    resp.raise_for_status()
    return resp.json()


def get_ha_entities_simple():
    """Fetches a simplified list of Home Assistant entities."""
    return _execute_tool(method="get", endpoint="ha/list-entities-simple", data={})


def _execute_tool(method: Literal["get", "post"], endpoint: str, data: dict[str, str]):
    """Posts arguments to the homelab-api."""

    if method == "get":
        resp = requests.get(f"{settings.backend_url}/{endpoint}", params=data)
        if resp.status_code >= 400:
            return {"error": resp.text}
        return resp.json()

    if method == "post":
        resp = requests.post(f"{settings.backend_url}/{endpoint}", json=data)
        if resp.status_code >= 400:
            return {"error": resp.text}
        return resp.json()


def execute_tool(method: Literal["get", "post"], endpoint: str, data: dict[str, str]):
    LOGGER.info(f"Executing tool: {method} {endpoint} with args {data}")
    try:
        resp = _execute_tool(method, endpoint, data)
        LOGGER.info(f"Tool response: {resp}")
        return resp
    except Exception as e:
        LOGGER.error(f"Error executing tool: {e}")
        return {"error": str(e)}
