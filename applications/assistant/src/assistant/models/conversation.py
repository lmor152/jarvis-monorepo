from pydantic import BaseModel


class ConversationRequest(BaseModel):
    text: str | None = None
    conversation_id: str
    language: str | None = "en"
    speaker: str | None = None
