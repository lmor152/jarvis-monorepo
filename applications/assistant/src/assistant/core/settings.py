from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # llm settings
    chat_model: str
    chat_api_key: str
    chat_url: str
    chat_temperature: float = 1.0

    # backend integrations
    backend_url: str

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()  # type: ignore
