import streamlit as st

def show_homepage():
    st.set_page_config(page_title="NeoStats AI", layout="wide")
    
    # Custom CSS for high-responsiveness
    st.markdown("""
        <style>
            .main-title { font-size: 3rem; text-align: center; color: #ffffff; }
            .hero-container { padding: 4rem 1rem; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); border-radius: 1rem; }
            .feature-card { padding: 1.5rem; border: 1px solid #ddd; border-radius: 0.5rem; margin-bottom: 1rem; }
        </style>
    """, unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="hero-container"><h1 class="main-title">NeoStats Multi-Mode AI</h1></div>', unsafe_allow_html=True)
        st.write("---")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("### 🔒 Private RAG")
            st.write("Your documents are processed locally and securely.")
        with col2:
            st.markdown("### 🧠 Local LLM")
            st.write("Powered by DeepSeek-R1, running 100% offline.")
        with col3:
            st.markdown("### ⚡ Fast Sync")
            st.write("Automatic folder syncing for new documentation.")
            
        if st.button("🚀 Access Secure Chat", use_container_width=True):
            st.switch_page("main.py")

if __name__ == "__main__":
    show_homepage()