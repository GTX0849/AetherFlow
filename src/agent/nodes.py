from langchain_community.llms import Ollama
from src.agent.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage

# Connect to your local lightweight model
llm = Ollama(model="deepseek-r1:1.5b", temperature=0.2)

def router_node(state: AgentState):
    """
    Analyzes the user's intent to route to the correct tool.
    Using string matching on a smaller model is safer than forcing strict JSON on an i3.
    """
    last_message = state["messages"][-1].content.lower()
    
    # Heuristic routing (extremely fast, zero RAM cost)
    if any(keyword in last_message for keyword in ["news", "latest", "current", "today", "stock"]):
        action = "web_search"
    elif any(keyword in last_message for keyword in ["policy", "company", "handbook", "proposal", "document"]):
        action = "rag_search"
    else:
        # Let the LLM decide if heuristics miss
        prompt = f"Analyze this query: '{last_message}'. Reply ONLY with 'web' for internet searches, 'rag' for enterprise docs, or 'general' for standard questions."
        decision = llm.invoke(prompt).strip().lower()
        
        if "web" in decision:
            action = "web_search"
        elif "rag" in decision:
            action = "rag_search"
        else:
            action = "general_chat"
            
    return {"next_action": action}

def general_chat_node(state: AgentState):
    """Handles standard interactions using only the LLM."""
    query = state["messages"][-1].content
    
    # Invoke the local model
    response_text = llm.invoke(query)
    
    return {"messages": [AIMessage(content=response_text)]}

def web_search_node(state: AgentState):
    """Placeholder for Mode 2: Web Search"""
    return {"messages": [AIMessage(content="[Web Search Executed - Pending Tool Hookup]")]}

def rag_search_node(state: AgentState):
    """Placeholder for Mode 3: Enterprise RAG"""
    return {"messages": [AIMessage(content="[RAG Search Executed - Pending Tool Hookup]")]}