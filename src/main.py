import os
import sys
import uuid
import sqlite3
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from pypdf import PdfReader

# CRITICAL: Path correction to resolve local imports cleanly
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Import the centralized LangGraph workflow, SQLite connection, and RAG ingestion tool
from src.agent.graph import agent_app, ingest_pdf_text

def fetch_all_sessions():
    from src.agent.graph import get_db_connection
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # This groups the sessions and orders by the latest message timestamp
        cursor.execute("""
            SELECT session_id 
            FROM short_term_memory 
            GROUP BY session_id 
            ORDER BY MAX(timestamp) DESC
        """)
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"Database error: {e}")
        return []
    finally:
        conn.close()

def load_session_history(session_id):
    """Loads historical conversation data from Postgres directly into Streamlit state."""
    # 1. Import the connection function locally to prevent circular imports
    from src.agent.graph import get_db_connection
    
    # 2. Get a fresh connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT role, content FROM short_term_memory WHERE session_id = %s ORDER BY timestamp ASC", 
        (session_id,)
    )
    
    st.session_state.messages = []
    for role, content in cursor.fetchall():
        if role == "user":
            st.session_state.messages.append(HumanMessage(content=content))
        else:
            st.session_state.messages.append(AIMessage(content=content))
    
    # 3. Clean up
    cursor.close()
    conn.close()

def main():
    st.set_page_config(page_title="AetherFlow", page_icon="🤖", layout="wide")
    
    # --- SIDEBAR: ONLY CHAT SESSIONS ---
    with st.sidebar:
        st.title("💬 Chat Sessions")
        
        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()

        st.divider()
        st.caption("Past Conversations")
        
        past_sessions = fetch_all_sessions()
        for s_id in past_sessions:
            col1, col2 = st.columns([4, 1]) # 4 parts for button, 1 part for delete
            with col1:
                if st.button(f"Chat: {s_id[:8]}...", key=s_id, use_container_width=True):
                    st.session_state.session_id = s_id
                    load_session_history(s_id)
                    st.rerun()
            with col2:
                # Mini delete button
                if st.button("🗑️", key=f"del_{s_id}"):
                    from src.agent.graph import delete_session
                    delete_session(s_id)
                    if st.session_state.session_id == s_id:
                        st.session_state.session_id = str(uuid.uuid4())
                        st.session_state.messages = []
                    st.rerun()

    # --- STATE SYNCHRONIZATION ---
    if "session_id" not in st.session_state:
        past_sessions = fetch_all_sessions()
        if past_sessions:
            st.session_state.session_id = past_sessions[0]
            load_session_history(past_sessions[0])
        else:
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []

    # --- MAIN CONSOLE ---
    st.title("AetherFlow")
    st.caption(f"Active Session: `{st.session_state.session_id}`")
    
    selected_mode = st.radio(
        "Select Operation Mode:",
        ["Auto-Route (AI Decision)", "Mode 1: General Chat", "Mode 2: Web Search", "Mode 3: Document RAG"],
        horizontal=True
    )

    # --- CONDITIONAL PDF UPLOAD (ONLY FOR RAG MODE) ---
    if selected_mode == "Mode 3: Document RAG":
        st.info("💡 You are in RAG Mode. Upload a PDF below to analyze it.")
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], key=f"uploader_{st.session_state.session_id}")
        
        if uploaded_file is not None:
            cache_key = f"loaded_{uploaded_file.name}_{st.session_state.session_id}"
            if cache_key not in st.session_state:
                with st.spinner("Extracting text and chunking into vector store..."):
                    try:
                        reader = PdfReader(uploaded_file)
                        full_text = "\n\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
                        if full_text.strip():
                            ingest_pdf_text(full_text, uploaded_file.name, st.session_state.session_id)
                            st.session_state[cache_key] = True
                            st.success(f"Attached: {uploaded_file.name}")
                        else:
                            st.error("Document unreadable.")
                    except Exception as e:
                        st.error(f"Ingestion failed: {str(e)}")

    # --- UI Chat Render Pipeline ---
    for message in st.session_state.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.markdown(message.content)

    # Runtime Execution
    if user_input := st.chat_input("Input command..."):
        with st.chat_message("user"):
            st.markdown(user_input)
            
        st.session_state.messages.append(HumanMessage(content=user_input))

        with st.chat_message("assistant"):
            with st.spinner("Processing..."):
                try:
                    inputs = {
                        "messages": st.session_state.messages,
                        "session_id": st.session_state.session_id,
                        "ui_mode": selected_mode  
                    }
                    output = agent_app.invoke(inputs)
                    final_reply = output["messages"][-1]
                    st.markdown(final_reply.content)
                    st.session_state.messages.append(final_reply)
                except Exception as e:
                    st.error(f"Node Error: {str(e)}")

if __name__ == "__main__":
    main()