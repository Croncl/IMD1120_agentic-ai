"""Agente com conectores MCP.

    pip install -e apps/mcp_agent
    streamlit run apps/mcp_agent/app.py

A chave da OpenAI vem da OPENAI_API_KEY, no ambiente ou em um .env nesta pasta
ou na raiz do repositório.
"""

import streamlit as st
from dotenv import load_dotenv

from mcp_agent.settings import PROJECT_DIR, prepare_dirs
from mcp_agent.ui import chat, connectors, settings, skills

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(PROJECT_DIR.parents[1] / ".env")
prepare_dirs()

st.set_page_config(page_title="Agente MCP", page_icon=":material/hub:", layout="wide")

# st.navigation monta o menu lateral e devolve a página escolhida. Cada página é
# uma função render, e o script inteiro, inclusive esta parte, roda de novo a
# cada interação.
page = st.navigation([
    st.Page(chat.render, title="Chat", icon=":material/chat:", url_path="chat", default=True),
    st.Page(connectors.render, title="Conectores", icon=":material/extension:", url_path="conectores"),
    st.Page(skills.render, title="Skills", icon=":material/school:", url_path="skills"),
    st.Page(settings.render, title="Configurações", icon=":material/tune:", url_path="configuracoes"),
])
page.run()
