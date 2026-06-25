import streamlit as st
import requests

API_URL = "http://localhost:8000/query"

st.set_page_config(page_title="AI Data Analysis Agent", layout="wide")

# -----------------------
# Session state init (IMPORTANT)
# -----------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi! Please ask me any question related to the selected data source."
        }
    ]

if "data_source" not in st.session_state:
    st.session_state.data_source = "Chinook Database"

# -----------------------
# CSS Styling
# -----------------------
st.markdown("""
<style>

html, body, [data-testid="stAppViewContainer"] {
    height: 100%;
}

/* full height layout */
[data-testid="stAppViewContainer"] > div {
    height: 100vh;
}

/* Chat column layout */
[data-testid="column"] > div {
    display: flex;
    flex-direction: column;
    height: 100%;
}
            
div[data-testid="stAlert"] {
    background-color: #ffa500;
    border-radius: 8px;
}
            
div[data-testid="stAlert"] p {
    color: black;
}

</style>
""", unsafe_allow_html=True)

# -----------------------
# Layout
# -----------------------
chat_col, control_col = st.columns([3, 1])

# -----------------------
# Right Column (Controls)
# -----------------------
with control_col:
    st.subheader("Data Source")

    data_source = st.radio(
        "Choose data source",
        ["Chinook Database", "Example Excel", "Upload Excel"]
    )

    st.session_state.data_source = data_source

    uploaded_file = None

    if data_source == "Upload Excel":
        uploaded_file = st.file_uploader(
            "Upload Excel file",
            type=["xlsx"]
        )


# -----------------------
# Left Column (Chat)
# -----------------------
with chat_col:
    st.title("AI Data Analysis Agent")
    st.caption(f"Using: {st.session_state.data_source}")

    # Only warn, never block UI
    if data_source == "Upload Excel" and uploaded_file is None:
        st.warning("Upload an Excel file to use this mode.")

    chat_container = st.container(height=500)

    with chat_container:
        st.markdown('<div class="chat-window">', unsafe_allow_html=True)

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        st.markdown('</div>', unsafe_allow_html=True)

    user_input = st.chat_input("Ask a question about your data...")

# -----------------------
# Handle user input
# -----------------------
if user_input:
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    payload = {
        "input": user_input,
        "session_id": "default-session",
        "data_source": st.session_state.data_source
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        response.raise_for_status()

        answer = response.json().get("response", "No response from server.")

    except Exception as e:
        answer = f"Error: {str(e)}"

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

    st.rerun()