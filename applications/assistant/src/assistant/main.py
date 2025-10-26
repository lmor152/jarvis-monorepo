import logging

from fastapi import FastAPI

from assistant.api import conversation

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

app = FastAPI(
    title="Jarvis Voice Assistant",
    description="Voice and chat-based home assistant.",
)

app.include_router(conversation.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Jarvis is running."}
