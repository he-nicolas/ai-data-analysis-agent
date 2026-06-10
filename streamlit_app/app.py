import streamlit as st
import requests

API_URL = "http://localhost:8000/query"

st.set_page_config(page_title="AI Data Analysis Agent", layout="wide")

st.title("AI Data Analysis Agent")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Input
user_input = st.chat_input("Ask the agent something...")

if user_input:
    # Store & show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Call backend
    try:
        response = requests.post(
            API_URL,
            json={"input": user_input},
            timeout=30
        )

        response.raise_for_status()
        assistant_msg = response.json()["response"]

    except Exception as e:
        assistant_msg = f"Error: {str(e)}"

    # Store & show assistant message
    st.session_state.messages.append({"role": "assistant", "content": assistant_msg})
    with st.chat_message("assistant"):
        st.write(assistant_msg)