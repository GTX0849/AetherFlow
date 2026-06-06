import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from src.agent.graph import agent_app

def render_chat_interface():
    """Renders the chat interface and streams responses from the LangGraph agent."""
    st.title("🤖 Intelligent Multi-Mode Agent")
    st.caption("Backend: LangGraph | Local LLM: DeepSeek-R1 1.5B | Persistent Layer: PostgreSQL")

    # Render history
    for message in st.session_state.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.markdown(message.content)

    # Capture User Input
    if user_input := st.chat_input("Ask a question, analyze web data, or query documents..."):
        # Display user message instantly
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Format for LangGraph state history
        human_message = HumanMessage(content=user_input)
        st.session_state.messages.append(human_message)

        # Process through the LangGraph Orchestrator
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Prepare the inputs matching the AgentState TypedDict
                    inputs = {
                        "messages": st.session_state.messages,
                        "session_id": st.session_state.session_id
                    }
                    
                    # Run the graph synchronously for reliable local orchestration
                    output = agent_app.invoke(inputs)
                    
                    # Extract the final message added by the active execution node
                    final_reply = output["messages"][-1]
                    
                    st.markdown(final_reply.content)
                    st.session_state.messages.append(final_reply)
                    
                except Exception as e:
                    error_msg = f"An execution error occurred inside the agent engine: {str(e)}"
                    st.error(error_msg)