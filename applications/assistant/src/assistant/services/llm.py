import json
import logging
from collections.abc import Callable
from typing import Any, cast

from openai import OpenAI

from assistant.core.settings import settings
from assistant.core.state import CONVERSATION_HISTORY
from assistant.models.llm import HistoryEntry, LLMResponse, ToolCall
from assistant.services.tools import (
    execute_tool,
    get_ha_entities_simple,
    get_tools_schema,
)

LOGGER = logging.getLogger(__name__)

client = OpenAI(
    api_key=settings.chat_api_key,
    base_url=settings.chat_url,
)

SYSTEM_PROMPT = """You are Jarvis, a home assistant. 
You can answer questions conversationally, and call tools when needed. 

The satellite system you are connected to will attempt to recognise users voices, but may not always work. 
If you need to know the users identity to complete a task, you can check with them.

your response must either be a message or a tool call, and follow this format:
{{
"intent": message/tool
"content": either the message to send to the user, or the tool call
"next": which action to take next, one of: "WAIT", "CONTINUE", "FINISH"
}}

CRITICAL RULES:
- You need to respond in this format at all times.
- The tool content must be JSON and be formatted exactly as: {{"method": "get/post", "endpoint": "string", "arguments": {{...}}}}
- Do NOT explain what you're doing when making tool calls

You should chain commands together unless the request is very simple. e.g. if you are asked to play a show:
* you need to check which media is available to get the show ID
* you need to check which clients are available to get the client ID
* you may need to turn on a device using Home Assistant if one is not available
* set the source for the device to plex so it becomes available as a client
* you then need to call play-media with the correct IDs
* There's no need to confirm to the user if the task completes successfully. But if there's errors, you should inform them.

If you are asked to control a HA device, you can use the list of available entities to find the correct one.

YOUR BEHAVIOUR:
* You may need to interpret transcription errors. 
* Respond as briefly as possible - you are a voice assistant. 
* If you need to list options, keep it to a maximum of 5.
* You should also try your best to action the users request, 
* If a request is ambiguous, use your best judgement to answer.
* You can use your prior knowledge to answer questions too as a fallback.

The available HA entities are:
{ha_entities_simple}

The available custom tools are:
* omnibooker - for booking things
* plex - control my Plex server

The schema for the backend API is:
{backend_schema}
"""


def make_tool_call(msg: ToolCall, history: list[HistoryEntry]) -> list[HistoryEntry]:
    """Parse and execute tool calls if message is valid JSON."""

    method = msg.method
    endpoint = msg.endpoint
    arguments = msg.arguments

    history.append(
        HistoryEntry(
            role="assistant",
            content=f"(tool execution) {method} {endpoint}, args={arguments}",
        )
    )

    try:
        result = execute_tool(method=method, endpoint=endpoint, data=arguments)
        if isinstance(result, dict) and "error" in result:
            typed_result = cast(dict[str, Any], result)
            error_value = typed_result.get("error")
            error_msg = (
                error_value if isinstance(error_value, str) else str(error_value)
            )
            raise RuntimeError(error_msg)
        history.append(
            HistoryEntry(role="assistant", content=f"(tool result) {result}")
        )
    except Exception as e:
        LOGGER.exception(f"Tool call failed: {e}")
        history.append(HistoryEntry(role="system", content=f"Tool call failed: {e}"))
        raise

    return history


def chat_with_llm(
    session_id: str,
    send_func: Callable[[str, str], None],
    history: list[HistoryEntry],
    user_input: str | None = None,
    speaker: str | None = None,
    max_iterations: int = 10,
    iteration: int = 0,
) -> list[HistoryEntry]:
    """Recursive conversation loop with tool calls and intermediate messages."""

    if iteration >= max_iterations:
        final_msg = "I've reached the maximum number of iterations for this request. Try simplifying your request."
        history.append(HistoryEntry(role="assistant", content=final_msg))
        if session_id:
            send_func(final_msg, "finish")
        return history

    # First iteration: initialise system prompt
    if iteration == 0 and not history:
        schema = get_tools_schema()
        ha_entities_simple = get_ha_entities_simple()
        system_prompt = SYSTEM_PROMPT.format(
            ha_entities_simple=ha_entities_simple,
            backend_schema=schema,
        )
        history = [HistoryEntry(role="system", content=system_prompt)]

    # Add user message
    if user_input:
        if speaker:
            history.append(
                HistoryEntry(
                    role="system",
                    content=f"speaker={speaker}",
                )
            )
        else:
            history.append(
                HistoryEntry(
                    role="system",
                    content="speaker=unrecognised",
                )
            )
        history.append(HistoryEntry(role="user", content=user_input))

    # Send to LLM
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=[h.format() for h in history],  # type: ignore
        temperature=settings.chat_temperature,
    )

    msg = response.choices[0].message.content
    LOGGER.info(f"LLM response: {msg}")
    history.append(HistoryEntry(role="assistant", content=str(msg)))

    try:
        parsed = LLMResponse.model_validate_json(str(msg))
    except Exception:
        history.append(
            HistoryEntry(role="system", content="Failed to parse LLM response.")
        )
        return chat_with_llm(
            session_id=session_id,
            send_func=send_func,
            user_input=None,
            history=history,
            max_iterations=max_iterations,
            iteration=iteration + 1,
        )

    next_action = (parsed.next or "finish").lower()

    if parsed.intent == "tool":
        try:
            tool_payload = parsed.content
            if isinstance(tool_payload, str):
                try:
                    tool_payload = json.loads(tool_payload)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Tool payload JSON decode error: {exc}") from exc

            tool_call = ToolCall.model_validate(tool_payload)
        except Exception:
            history.append(
                HistoryEntry(role="system", content="Failed to parse ToolCall.")
            )
            return chat_with_llm(
                session_id=session_id,
                user_input=None,
                send_func=send_func,
                history=history,
                max_iterations=max_iterations,
                iteration=iteration + 1,
            )

        try:
            history = make_tool_call(tool_call, history)
        except Exception as exc:
            LOGGER.exception(f"Tool invocation failure: {exc}")
            failure_msg = "Sorry, I hit an error while finishing that request."
            history.append(HistoryEntry(role="assistant", content=failure_msg))
            send_func(failure_msg, "finish")
            return history

        if next_action != "continue":
            return history
        return chat_with_llm(
            session_id=session_id,
            user_input=None,
            send_func=send_func,
            history=history,
            max_iterations=max_iterations,
            iteration=iteration + 1,
        )

    elif parsed.intent == "message":
        effective_next = next_action
        message_text = str(parsed.content)
        if message_text.strip() == "":
            effective_next = "finish"
        elif user_input is None and next_action == "continue":
            previous_message: str | None = None
            for entry in reversed(history[:-1]):
                if entry.role != "assistant":
                    continue
                try:
                    previous = LLMResponse.model_validate_json(entry.content)
                except Exception:
                    continue
                if previous.intent == "message":
                    previous_message = str(previous.content)
                    break

            if (
                previous_message is not None
                and previous_message.strip() == message_text.strip()
            ):
                effective_next = "finish"

        send_func(message_text, effective_next)
        if effective_next in ("finish", "wait", "continue"):
            return history
        return chat_with_llm(
            session_id=session_id,
            user_input=None,
            send_func=send_func,
            history=history,
            max_iterations=max_iterations,
            iteration=iteration + 1,
        )
    else:
        return chat_with_llm(
            session_id=session_id,
            user_input=None,
            send_func=send_func,
            history=history,
            max_iterations=max_iterations,
            iteration=iteration + 1,
        )

    return history


async def handle_user_message(
    session_id: str, user_text: str, send_func: Callable[[str, str], None]
):
    history = CONVERSATION_HISTORY.get(session_id, [])
    history = chat_with_llm(
        session_id=session_id,
        user_input=user_text,
        send_func=send_func,
        history=history,
        max_iterations=10,
        iteration=0,
    )
