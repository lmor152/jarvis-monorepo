import json
import uuid

import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Jarvis Assistant", page_icon="🤖")
st.title("💬 Jarvis Assistant")

if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# Poll every 2 seconds
st_autorefresh(interval=1000, key="chat_autorefresh")


# Fetch new messages from backend (replace with your API/WebSocket logic)
def fetch_new_messages():
    response = requests.get(
        f"http://localhost:8001/api/conversation/{st.session_state['conversation_id']}"
    )
    history = response.json()["history"]
    messages = []
    for m in history:
        if m.get("role") == "user":
            messages.append({"role": "user", "content": m["content"]})
        elif m.get("role") == "assistant":
            content_str = m["content"]
            # Only parse/display if it looks like a JSON message
            if content_str.strip().startswith("{"):
                try:
                    content = json.loads(content_str)
                    # Only show if intent is "message"
                    if content.get("intent") == "message":
                        messages.append(
                            {"role": "assistant", "content": content["content"]}
                        )
                except Exception as e:
                    print(f"Error parsing assistant message: {e}")
                    continue
            # Otherwise, skip tool/system logs
    already_have = len(st.session_state.messages)
    return messages[already_have:]


# Update chat history
for msg in fetch_new_messages():
    st.session_state.messages.append(msg)

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Type your message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Send to backend (HTTP POST to /api/conversation)
    requests.post(
        "http://localhost:8001/api/conversation",
        json={
            "conversation_id": st.session_state["conversation_id"],
            "text": prompt,
            "language": "en",
        },
    )
    st.rerun()
