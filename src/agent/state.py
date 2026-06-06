from typing import TypedDict, Sequence
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    next_action: str  # 'general_chat', 'web_search', or 'rag_search'
    session_id: str   # To pass to your Postgres db layer