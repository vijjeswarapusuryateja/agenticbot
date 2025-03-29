import streamlit as st
import requests
import json
import os
import uuid  # Unique session IDs
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# FastAPI Backend URL
API_URL = "http://127.0.0.1:8000/query"
TICKET_API_URL = "http://127.0.0.1:8000/create_ticket"
TICKET_SUMMARY_URL = "http://127.0.0.1:8000/generate_ticket_summary"

# File to store chat sessions
CHAT_HISTORY_FILE = "chat_sessions.json"

# Function to load chat sessions from JSON file
def load_chat_sessions():
    """Load chat sessions safely, handling potential file errors."""
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r") as file:
                history = json.load(file)
                return history if isinstance(history, list) else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

# Function to save chat sessions to JSON file
def save_chat_sessions(history):
    """Safely save chat sessions."""
    with open(CHAT_HISTORY_FILE, "w") as file:
        json.dump(history, file, indent=4)

# Streamlit UI Setup
st.set_page_config(page_title="Evabot AI", layout="wide")

# Sidebar: Chat History
with st.sidebar:
    st.title("⚙️ Settings")

    if st.button("🆕 New Chat"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.session_title = ""  # ✅ Reset session title
        st.session_state.issue_resolved = None
        st.session_state.raise_ticket = False
        st.session_state.ticket_summary = ""
        st.session_state.ticket_submitted = False
        chat_sessions = load_chat_sessions()
        save_chat_sessions(chat_sessions)
        st.rerun()

    st.subheader("📜 Chat History")
    chat_sessions = load_chat_sessions()

    for i, session in enumerate(reversed(chat_sessions)):
        session_title = session.get("title") or (session["messages"][0]["content"][:30] if session.get("messages") else "Untitled Chat")
        if st.button(f"🗨️ {session_title}...", key=f"session_{i}"):
            st.session_state.session_id = session["id"]
            st.session_state.messages = session["messages"]
            st.session_state.session_title = session_title
            st.rerun()

# Initialize session state variables
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_title" not in st.session_state:
    st.session_state.session_title = ""
if "issue_resolved" not in st.session_state:
    st.session_state.issue_resolved = None
if "raise_ticket" not in st.session_state:
    st.session_state.raise_ticket = False
if "ticket_summary" not in st.session_state:
    st.session_state.ticket_summary = ""
if "ticket_submitted" not in st.session_state:
    st.session_state.ticket_submitted = False

# Main Chat UI
st.title("🗨️ Evabot AI")

# Display chat messages
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Chat input box (Fixed at bottom)
user_input = st.chat_input("Ask Eva...")

if user_input:
    # Append user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Set session title if first question
    if not st.session_state.session_title:
        st.session_state.session_title = user_input[:30]  # Use first message as title

    with st.chat_message("user"):
        st.markdown(user_input)

    # Send request to FastAPI bot
    response = requests.post(API_URL, json={"query": user_input, "session_id": st.session_state.session_id})

    if response.status_code == 200:
        response_json = response.json()
        bot_reply = response_json.get("response", "Error: No response received.")
        st.session_state.raise_ticket = response_json.get("prompt_ticket", False)
        st.session_state.ticket_summary = bot_reply if st.session_state.raise_ticket else ""

        logger.info(f"Bot Response: {bot_reply}")
    else:
        bot_reply = "Error: Failed to reach API."
        st.session_state.raise_ticket = False
        st.session_state.ticket_summary = ""

    # Append bot response to chat
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    with st.chat_message("assistant"):
        st.markdown(bot_reply)

    # Save chat history
    chat_sessions = load_chat_sessions()
    existing_session = next((s for s in chat_sessions if s["id"] == st.session_state.session_id), None)

    if existing_session:
        existing_session["messages"] = st.session_state.messages
        existing_session["title"] = st.session_state.session_title  # Ensure title is stored
    else:
        chat_sessions.append({
            "id": st.session_state.session_id,
            "title": st.session_state.session_title or st.session_state.messages[0]["content"][:30],  # Set title
            "messages": st.session_state.messages
        })

    save_chat_sessions(chat_sessions)

# IT Issue Handling with UI Elements
if st.session_state.raise_ticket and not st.session_state.ticket_submitted:
    st.markdown("❓ *Does this solve your issue?*")

    selected_option = st.radio(
        "Select an option:", 
        ["Yes, resolved", "No, I need IT support"], 
        index=None
    )

    if selected_option:
        st.session_state.issue_resolved = selected_option

    # Only trigger Ticket Agent when user selects "No, I need IT support"
    if st.session_state.issue_resolved == "No, I need IT support":
        st.markdown("🚨 **Your issue might require IT support.** Please create a ticket.")

        # **Trigger Ticket Agent Only When Needed**
        ticket_response = requests.post(TICKET_SUMMARY_URL, json={
            "query": st.session_state.messages[-1]["content"],  # Send last user message
            "session_id": st.session_state.session_id
        })

        if ticket_response.status_code == 200:
            response_json = ticket_response.json()
            st.session_state.ticket_summary = response_json.get("ticket_summary", " Error: Ticket summary not generated.")
        else:
            st.session_state.ticket_summary = "Error: Failed to fetch ticket summary."

        st.markdown(f"**Issue Summary:** {st.session_state.ticket_summary}")

        # Select issue category
        issue_category = st.selectbox(
            "Select Issue Category:", 
            ["Network Issue", "Password Reset", "Software Installation", "Hardware Problem"],
            key="issue_category"
        )

        if st.button("📝 Submit Ticket"):
            logger.info(f"Submitting ticket with summary: {st.session_state.ticket_summary} and category: {issue_category}")

            ticket_submit_response = requests.post(TICKET_API_URL, json={
                "issue_summary": st.session_state.ticket_summary,
                "issue_category": issue_category
            })

            if ticket_submit_response.status_code == 200:
                ticket_reply = ticket_submit_response.json().get("response", "Error: Ticket creation failed.")
            else:
                ticket_reply = "Error: Ticket creation failed."

            logger.info(f"Ticket creation response: {ticket_reply}")

            st.session_state.messages.append({"role": "assistant", "content": ticket_reply})
            with st.chat_message("assistant"):
                st.markdown(ticket_reply)

            st.session_state.ticket_submitted = True  
            save_chat_sessions(chat_sessions)
            st.rerun()

# Auto-scroll to latest message
st.markdown(
    """<script>
        var chatDiv = window.parent.document.querySelector('.stChat');
        if (chatDiv) {
            chatDiv.scrollTop = chatDiv.scrollHeight;
        }
    </script>""",
    unsafe_allow_html=True
)

