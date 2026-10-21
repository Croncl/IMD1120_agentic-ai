"""Objetos que vivem enquanto o processo do Streamlit estiver de pé."""

from dataclasses import dataclass

import streamlit as st
from langgraph.checkpoint.memory import InMemorySaver

from mcp_agent.connectors import Connector, load_connectors
from mcp_agent.hub import MCPHub
from mcp_agent.runtime import BackgroundLoop


@dataclass
class Services:
    loop: BackgroundLoop
    hub: MCPHub
    checkpointer: InMemorySaver


# st.cache_resource guarda o objeto entre as reexecuções do script, e ele é
# compartilhado por todas as abas do navegador. Sem o cache, cada clique abriria
# de novo as conexões MCP e o checkpointer nasceria vazio, sem as conversas.
@st.cache_resource
def get_services() -> Services:
    loop = BackgroundLoop()
    return Services(loop, MCPHub(loop), InMemorySaver())


def sync_connectors() -> dict[str, Connector]:
    """Lê os conectores gravados e ajusta as conexões abertas a eles."""
    connectors = load_connectors()
    with st.spinner("Conectando aos servidores MCP..."):
        get_services().hub.sync(connectors)
    return connectors
