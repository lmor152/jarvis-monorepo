from dataclasses import dataclass
from typing import Any, Dict, Literal

from pydantic import BaseModel, field_validator


class ToolCall(BaseModel):
    method: Literal["get", "post"]
    endpoint: str
    arguments: dict[str, Any] = {}

    @field_validator("method", mode="before")
    @classmethod
    def lowercase_method(cls, v: str) -> str:
        return v.lower()


class LLMResponse(BaseModel):
    intent: Literal["message", "tool"]
    content: str | ToolCall
    next: Literal["wait", "continue", "finish"]

    @field_validator("intent", mode="before")
    @classmethod
    def lowercase_intent(cls, v: str) -> str:
        return v.lower()

    @field_validator("next", mode="before")
    @classmethod
    def lowercase_next(cls, v: str) -> str:
        return v.lower()


@dataclass
class HistoryEntry:
    role: str
    content: str

    def format(self) -> Dict[str, Any]:
        return {"role": self.role, "content": self.content}
