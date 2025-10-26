import pytz
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    timezone: str

    # omnibooker
    omnibooker_url: str = "http://omnibooker:port"

    # plex
    # plex_username: str
    # plex_password: str
    # plex_server_name: str
    plex_url: str
    plex_token: str

    # home assistant
    ha_url: str
    ha_token: str
    ha_included_domains: list[str] = ["light", "media_player"]
    ha_included_entities: list[str] = []

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def tz(self):
        """Convert timezone string to pytz timezone object"""
        return pytz.timezone(self.timezone)


settings = Settings()  # type: ignore
