import logging
from typing import Dict, List

from fastapi import APIRouter, WebSocket
from fastapi.responses import JSONResponse

from assistant.core.state import CONVERSATION_HISTORY
from assistant.models.conversation import ConversationRequest
from assistant.services.llm import chat_with_llm

router = APIRouter()
LOGGER = logging.getLogger(__name__)


active_connections: Dict[str, WebSocket] = {}


def send_file_message(message: str, next_action: str | None = None):
    """Send a message to a specific client session."""

    # for now, write to a file
    with open("user_messages.txt", "a") as f:
        f.write(f"{message}\n")


@router.post("/conversation")
async def converse(request: ConversationRequest) -> JSONResponse:
    """Process one conversational turn."""
    LOGGER.info(f"Speaker {request.speaker}: {request.text}")
    history = CONVERSATION_HISTORY.get(request.conversation_id, [])
    responses: List[dict[str, str]] = []

    if request.speaker:
        LOGGER.info(
            "Conversation %s tagged with speaker=%s",
            request.conversation_id,
            request.speaker,
        )

    def collect(message: str, next_action: str | None = None) -> None:
        action = (next_action or "finish").lower()
        responses.append({"text": message, "next": action})
        send_file_message(message, next_action)

    updated_history = chat_with_llm(
        session_id=request.conversation_id,
        user_input=request.text or None,
        speaker=request.speaker,
        history=history,
        send_func=collect,
    )
    CONVERSATION_HISTORY[request.conversation_id] = updated_history
    last_action = responses[-1]["next"] if responses else "finish"
    return JSONResponse(
        status_code=200,
        content={
            "conversation_id": request.conversation_id,
            "messages": responses,
            "next": last_action,
        },
    )


@router.get("/conversation/{conversation_id}")
async def get_conversation_history(conversation_id: str) -> JSONResponse:
    """Retrieve the conversation history for a given conversation_id."""
    history = CONVERSATION_HISTORY.get(conversation_id, [])
    history_data = [{"role": entry.role, "content": entry.content} for entry in history]
    return JSONResponse(
        status_code=200,
        content={"conversation_id": conversation_id, "history": history_data},
    )
