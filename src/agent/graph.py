import psycopg2
from psycopg2 import sql
import chromadb
from chromadb.utils import embedding_functions
from typing import TypedDict, Sequence, Optional
from langchain_core.messages import BaseMessage, AIMessage
from langchain_community.llms import Ollama
from langchain_community.tools import DuckDuckGoSearchResults
from langgraph.graph import StateGraph, END

# ==========================================
# 0. DATABASE CONFIGURATION (PostgreSQL)
# ==========================================
DB_CONFIG = {
    "dbname": "neostats_hackathon",
    "user": "postgres",
    "password": "root",
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS short_term_memory (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS document_registry (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    cursor.close()
    conn.close()

init_db()

def log_short_term_memory(session_id: str, role: str, content: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Ensure the session exists in the parent table
    cursor.execute("""
        INSERT INTO chat_sessions (session_id, title) 
        VALUES (%s, %s) 
        ON CONFLICT (session_id) DO NOTHING
    """, (session_id, "New Conversation"))
    
    # 2. Now log the message
    cursor.execute(
        "INSERT INTO short_term_memory (session_id, role, content) VALUES (%s, %s, %s)",
        (session_id, role, content)
    )
    
    conn.commit()
    cursor.close()
    conn.close()

# ==========================================
# 1. VECTOR DATABASE SETUP (ChromaDB)
# ==========================================
chroma_client = chromadb.PersistentClient(path="./chroma_db")
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
doc_collection = chroma_client.get_or_create_collection(name="enterprise_docs", embedding_function=sentence_transformer_ef)

def ingest_pdf_text(text: str, filename: str, session_id: str):
    import uuid
    # Register in Postgres
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO document_registry (session_id, filename) VALUES (%s, %s)", (session_id, filename))
    conn.commit()
    cursor.close()
    conn.close()
    
    # Ingest into Vector DB
    chunks = [chunk.strip() for chunk in text.split("\n\n") if len(chunk.strip()) > 20]
    if not chunks: chunks = [text] 
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"source": filename, "session_id": session_id} for _ in chunks]
    doc_collection.add(documents=chunks, metadatas=metadatas, ids=ids)

def delete_session(session_id: str):
    """Deletes all memory and registry records for a given session."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete from memory and registry
    cursor.execute("DELETE FROM short_term_memory WHERE session_id = %s", (session_id,))
    cursor.execute("DELETE FROM document_registry WHERE session_id = %s", (session_id,))
    cursor.execute("DELETE FROM chat_sessions WHERE session_id = %s", (session_id,))
    conn.commit()
    cursor.close()
    conn.close()

# ==========================================
# 2. STATE & LLM
# ==========================================
class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    next_action: str  
    session_id: str   
    ui_mode: Optional[str]

llm = Ollama(model="deepseek-r1:1.5b", temperature=0.2)

# ==========================================
# 3. NODES LOGIC
# ==========================================
def router_node(state: AgentState):
    user_msg = state["messages"][-1].content
    session_id = state["session_id"]
    ui_mode = state.get("ui_mode", "Auto-Route (AI Decision)")
    
    log_short_term_memory(session_id, "user", user_msg)
    
    # 1. UI Overrides
    if "Mode 1" in ui_mode: return {"next_action": "general_chat"}
    if "Mode 2" in ui_mode: return {"next_action": "web_search"}
    if "Mode 3" in ui_mode: return {"next_action": "rag_search"}
        
    # 2. Smart Routing
    try:
        rag_check = doc_collection.query(query_texts=[user_msg], n_results=1, where={"session_id": session_id})
        if rag_check.get("documents") and rag_check["documents"][0]:
            return {"next_action": "rag_search"}
    except: pass 
        
    if any(k in user_msg.lower() for k in ["news", "latest", "stock"]): return {"next_action": "web_search"}
    return {"next_action": "general_chat"}

def general_chat_node(state: AgentState):
    session_id = state["session_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM short_term_memory WHERE session_id = %s ORDER BY timestamp ASC LIMIT 6", (session_id,))
    history = "\n".join([f"{r[0].capitalize()}: {r[1]}" for r in cursor.fetchall() if r[1] != state["messages"][-1].content])
    cursor.close()
    conn.close()
    
    prompt = f"History: {history}\nUser: {state['messages'][-1].content}\nAssistant:"
    response = llm.invoke(prompt)
    if "</think>" in response: response = response.split("</think>")[-1].strip()
    log_short_term_memory(session_id, "assistant", response)
    return {"messages": [AIMessage(content=response)]}

def web_search_node(state: AgentState):
    raw = DuckDuckGoSearchResults(num_results=3).run(state["messages"][-1].content)
    response = llm.invoke(f"Search Results: {raw}. Query: {state['messages'][-1].content}")
    if "</think>" in response: response = response.split("</think>")[-1].strip()
    log_short_term_memory(state["session_id"], "assistant", response)
    return {"messages": [AIMessage(content=response)]}

def rag_search_node(state: AgentState):
    results = doc_collection.query(query_texts=[state["messages"][-1].content], n_results=3, where={"session_id": state["session_id"]})
    docs = "\n".join(results["documents"][0]) if (results.get("documents") and results["documents"][0]) else "No documents found."
    response = llm.invoke(f"Use these docs: {docs}. Query: {state['messages'][-1].content}")
    if "</think>" in response: response = response.split("</think>")[-1].strip()
    log_short_term_memory(state["session_id"], "assistant", response)
    return {"messages": [AIMessage(content=response)]}

# ==========================================
# 4. GRAPH
# ==========================================
workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("general_chat", general_chat_node)
workflow.add_node("web_search", web_search_node)
workflow.add_node("rag_search", rag_search_node)
workflow.set_entry_point("router")
workflow.add_conditional_edges("router", lambda x: x["next_action"], {"general_chat": "general_chat", "web_search": "web_search", "rag_search": "rag_search"})
workflow.add_edge("general_chat", END); workflow.add_edge("web_search", END); workflow.add_edge("rag_search", END)
agent_app = workflow.compile()