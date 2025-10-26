from typing import Any, Dict, Optional

import requests


class SimpleHAClient:
    """Simple and reliable Home Assistant API client"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make a request to the Home Assistant API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(
                    url, headers=self.headers, json=data, timeout=10
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")

    def get_states(self) -> list[Dict[str, Any]]:
        """Get all entity states"""
        return self._request("GET", "states")

    def get_state(self, entity_id: str) -> Dict[str, Any]:
        """Get state of a specific entity"""
        return self._request("GET", f"states/{entity_id}")

    def get_entities(self, domain: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get all entities, optionally filtered by domain"""
        states = self.get_states()
        entities = {}
        for entity in states:
            if "entity_id" in entity:
                entity_id = str(entity["entity_id"])
                if domain is None or entity_id.startswith(f"{domain}."):
                    entities[entity_id] = entity
        return entities

    def list_entities(self, domain: Optional[str] = None) -> list[str]:
        """Get a list of entity IDs, optionally filtered by domain"""
        entities = self.get_entities(domain)
        return list(entities.keys())

    def set_state(
        self, entity_id: str, state: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Set state of an entity"""
        data: Dict[str, Any] = {"state": state}
        if attributes:
            data["attributes"] = attributes
        return self._request("POST", f"states/{entity_id}", data)

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        service_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call a Home Assistant service"""
        data: Dict[str, Any] = {}
        if entity_id:
            data["entity_id"] = entity_id
        if service_data:
            data.update(service_data)

        return self._request("POST", f"services/{domain}/{service}", data)

    def turn_on(
        self, entity_id: str, domain: str = "homeassistant", **kwargs: Any
    ) -> Dict[str, Any]:
        """Turn on an entity (default domain: homeassistant)"""
        return self.call_service(domain, "turn_on", entity_id, kwargs)

    def turn_off(
        self, entity_id: str, domain: str = "homeassistant", **kwargs: Any
    ) -> Dict[str, Any]:
        """Turn off an entity (default domain: homeassistant)"""
        return self.call_service(domain, "turn_off", entity_id, kwargs)

    def toggle(
        self, entity_id: str, domain: str = "homeassistant", **kwargs: Any
    ) -> Dict[str, Any]:
        """Toggle an entity (default domain: homeassistant)"""
        return self.call_service(domain, "toggle", entity_id, kwargs)

    def light_turn_on(
        self,
        entity_id: str,
        brightness: Optional[int] = None,
        color_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Turn on a light with optional parameters"""
        service_data = kwargs.copy()
        if brightness is not None:
            service_data["brightness"] = brightness
        if color_name:
            service_data["color_name"] = color_name

        return self.call_service("light", "turn_on", entity_id, service_data)

    def light_turn_off(self, entity_id: str) -> Dict[str, Any]:
        """Turn off a light"""
        return self.call_service("light", "turn_off", entity_id)

    def media_player_play(self, entity_id: str) -> Dict[str, Any]:
        """Play media on a media player entity"""
        return self.call_service("media_player", "media_play", entity_id)

    def media_player_pause(self, entity_id: str) -> Dict[str, Any]:
        """Pause media on a media player entity"""
        return self.call_service("media_player", "media_pause", entity_id)

    def media_player_play_pause(self, entity_id: str) -> Dict[str, Any]:
        """Toggle play/pause on a media player entity"""
        return self.call_service("media_player", "media_play_pause", entity_id)

    def media_player_stop(self, entity_id: str) -> Dict[str, Any]:
        """Stop media on a media player entity"""
        return self.call_service("media_player", "media_stop", entity_id)

    def media_player_next(self, entity_id: str) -> Dict[str, Any]:
        """Skip to next track on a media player entity"""
        return self.call_service("media_player", "media_next_track", entity_id)

    def media_player_previous(self, entity_id: str) -> Dict[str, Any]:
        """Skip to previous track on a media player entity"""
        return self.call_service("media_player", "media_previous_track", entity_id)

    def media_player_volume_up(self, entity_id: str) -> Dict[str, Any]:
        """Increase volume on a media player entity"""
        return self.call_service("media_player", "volume_up", entity_id)

    def media_player_volume_down(self, entity_id: str) -> Dict[str, Any]:
        """Decrease volume on a media player entity"""
        return self.call_service("media_player", "volume_down", entity_id)

    def media_player_set_volume(
        self, entity_id: str, volume_level: float
    ) -> Dict[str, Any]:
        """Set volume level on a media player entity (0.0 to 1.0)"""
        return self.call_service(
            "media_player", "volume_set", entity_id, {"volume_level": volume_level}
        )

    def media_player_select_source(self, entity_id: str, source: str) -> Dict[str, Any]:
        """Select a source/app on a media player entity"""
        return self.call_service(
            "media_player", "select_source", entity_id, {"source": source}
        )

    def media_player_get_sources(self, entity_id: str) -> list[str]:
        """Get list of available sources/apps on a media player entity"""
        state = self.get_state(entity_id)
        return state.get("attributes", {}).get("source_list", [])
