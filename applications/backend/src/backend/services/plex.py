# type: ignore

from functools import lru_cache

from plexapi.server import PlexServer

from backend.core.settings import settings


@lru_cache()
def setup_plex() -> PlexServer:
    """
    Get Plex server instance with caching.
    """
    try:
        return PlexServer(settings.plex_url, settings.plex_token)
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Plex server: {e}")


def update_libraries(plex: PlexServer) -> None:
    libraries = [s.title for s in plex.library.sections()]
    for lib in libraries:
        plex.library.section(lib).update()


def list_media(plex: PlexServer) -> dict[str, list[str]]:
    libraries = [s.title for s in plex.library.sections()]
    media: dict[str, list[str]] = {}
    for lib in libraries:
        media[lib] = [item.title for item in plex.library.section(lib).all()]

    return media


def list_clients(plex: PlexServer) -> list[str]:
    return [client.title for client in plex.clients()]


def play_media(plex: PlexServer, library: str, media_id: str, client_id: str) -> None:
    client = plex.client(client_id)
    media = plex.library.section(library).get(media_id)
    client.playMedia(media)


def pause_media(plex: PlexServer, client_id: str) -> None:
    client = plex.client(client_id)
    client.pause()


def resume_media(plex: PlexServer, client_id: str) -> None:
    client = plex.client(client_id)
    client.play()
