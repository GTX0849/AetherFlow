import os
import sys
import hashlib
from pypdf import PdfReader

# --- PATH CORRECTION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# --- CORRECTED IMPORTS ---
from src.agent.graph import ingest_pdf_text, get_db_connection

DATA_DIR = os.path.join(root_dir, "data")

def sync_folder():
    """Scans the data folder and syncs new PDFs to PostgreSQL and ChromaDB."""
    if not os.path.exists(DATA_DIR):
        print(f"Directory {DATA_DIR} not found. Please create it.")
        return

    # Open connection
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. BOOTSTRAP: Ensure the 'system_global' session exists to satisfy FK constraint
    try:
        cursor.execute("""
            INSERT INTO chat_sessions (session_id, title) 
            VALUES (%s, %s) 
            ON CONFLICT (session_id) DO NOTHING
        """, ("system_global", "Global Knowledge Base"))
        conn.commit()
    except Exception as e:
        print(f"Error bootstrapping global session: {e}")
        conn.rollback()

    # 2. SYNC FILES
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".pdf"):
            filepath = os.path.join(DATA_DIR, filename)
            
            # Check Postgres: Has this file been ingested?
            cursor.execute("SELECT id FROM document_registry WHERE filename = %s", (filename,))
            if cursor.fetchone():
                print(f"Skipping: {filename} (Already ingested)")
                continue
            
            print(f"Syncing new file: {filename}...")
            
            try:
                # Ingest text
                reader = PdfReader(filepath)
                text = "\n\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
                
                # Ingest to ChromaDB
                ingest_pdf_text(text, filename, "system_global")
                
                # Register in Postgres
                cursor.execute("INSERT INTO document_registry (session_id, filename) VALUES (%s, %s)", 
                               ("system_global", filename))
                conn.commit()
            except Exception as e:
                print(f"Failed to sync {filename}: {e}")
                conn.rollback()

    cursor.close()
    conn.close()
    print("Sync complete.")

if __name__ == "__main__":
    sync_folder()