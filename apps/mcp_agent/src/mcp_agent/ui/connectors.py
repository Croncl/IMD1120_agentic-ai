"""Página de conectores: ligar e desligar servidores e adicionar novos."""

import json

import streamlit as st

from mcp_agent.connectors import Connector, parse_mcp_servers, save_connectors, validate
from mcp_agent.hub import Connection
from mcp_agent.ui.state import get_services, sync_connectors

EXAMPLE_JSON = """{
  "mcpServers": {
    "pokemon": {"url": "https://exemplo.com/mcp"}
  }
}"""


def toggle(connectors: dict[str, Connector], name: str) -> None:
    """Callback do st.toggle: roda antes da reexecução, então a página já nasce com a conexão ajustada."""
    connectors[name].enabled = st.session_state[f"on_{name}"]
    save_connectors(connectors)


def summary(connection: Connection) -> str:
    return f"{len(connection.tools)} ferramentas · {len(connection.resources)} recursos · {len(connection.prompts)} prompts"


def card(connector: Connector, connectors: dict[str, Connector]) -> None:
    """Um conector: chave liga e desliga, estado da conexão e detalhes."""
    hub = get_services().hub
    connection = hub.connections.get(connector.name)
    problems = connector.problems()
    with st.container(border=True):
        st.toggle(f"**{connector.name}**", value=connector.enabled, key=f"on_{connector.name}", on_change=toggle, args=(connectors, connector.name), disabled=bool(problems) and not connector.enabled)
        st.badge(connector.transport, color="blue" if connector.transport == "http" else "gray")
        st.caption(connector.description)
        if problems:
            st.warning("; ".join(problems), icon=":material/key:")
        elif connection and connection.error:
            st.error(connection.error, icon=":material/error:")
        elif connection:
            st.success(summary(connection), icon=":material/check_circle:")
        with st.expander("Detalhes"):
            st.json(connector.config)
            for tool in connection.tools if connection else []:
                st.markdown(f"`{tool.name}` {(tool.description or '').splitlines()[0][:150] if tool.description else ''}")
            for resource in connection.resources if connection else []:
                st.markdown(f":material/attach_file: `{resource.uri}` {resource.description or ''}")
            for prompt in connection.prompts if connection else []:
                st.markdown(f":material/description: `{prompt.name}` {prompt.description or ''}")
        buttons = st.columns(2)
        if connection and connection.error and buttons[0].button("Reconectar", key=f"retry_{connector.name}", icon=":material/refresh:"):
            # Sem a conexão registrada, a próxima sincronização tenta de novo.
            del hub.connections[connector.name]
            st.rerun()
        if connector.custom and buttons[1].button("Remover", key=f"remove_{connector.name}", icon=":material/delete:"):
            del connectors[connector.name]
            save_connectors(connectors)
            st.rerun()


def catalog(connectors: dict[str, Connector]) -> None:
    categories = dict.fromkeys(c.category for c in connectors.values())
    for category in categories:
        st.subheader(category)
        columns = st.columns(3)
        for index, connector in enumerate(c for c in connectors.values() if c.category == category):
            with columns[index % 3]:
                card(connector, connectors)


def lines_to_dict(text: str, separator: str) -> dict[str, str]:
    """Converte linhas CHAVE=valor (ou Nome: valor) em dicionário."""
    pairs = [line.split(separator, 1) for line in text.splitlines() if separator in line]
    return {key.strip(): value.strip() for key, value in pairs}


def new_connectors_from_form() -> dict[str, dict] | None:
    """Monta as configurações a partir do formulário escolhido; None enquanto nada for enviado."""
    kind = st.radio("Tipo", ["Servidor remoto (URL)", "Servidor local (comando)", "Colar JSON mcpServers"], horizontal=True)
    with st.form("new_connector"):
        if kind == "Colar JSON mcpServers":
            st.caption("O formato que os READMEs dos servidores trazem para o Claude Desktop, o Cursor ou o Claude Code.")
            text = st.text_area("JSON", EXAMPLE_JSON, height=200)
        else:
            name = st.text_input("Nome", placeholder="meu-servidor")
            description = st.text_input("Descrição")
            if kind == "Servidor remoto (URL)":
                url = st.text_input("URL", placeholder="https://exemplo.com/mcp")
                headers = st.text_area("Cabeçalhos, um por linha", placeholder="Authorization: Bearer ${MEU_TOKEN}")
            else:
                command = st.text_input("Comando", placeholder="npx, uvx, python...")
                args = st.text_area("Argumentos, um por linha", placeholder="-y\n@modelcontextprotocol/server-everything")
                env = st.text_area("Variáveis de ambiente, uma por linha", placeholder="MINHA_CHAVE=${MINHA_CHAVE}")
        st.caption("Valores como ${MINHA_CHAVE} são lidos do ambiente na hora de conectar, e o segredo não fica gravado no arquivo.")
        if not st.form_submit_button("Testar e adicionar", icon=":material/add:"):
            return None
    try:
        if kind == "Colar JSON mcpServers":
            return {name: {"config": config} for name, config in parse_mcp_servers(text).items()}
    except ValueError as error:
        st.error(f"JSON inválido: {error}")
        return None
    if kind == "Servidor remoto (URL)":
        config = {"url": url.strip()} | ({"headers": lines_to_dict(headers, ":")} if headers.strip() else {})
    else:
        config = {"command": command.strip(), "args": [a.strip() for a in args.splitlines() if a.strip()]} | ({"env": lines_to_dict(env, "=")} if env.strip() else {})
    return {name.strip(): {"config": config, "description": description}}


def add_form(connectors: dict[str, Connector]) -> None:
    """Adiciona conectores depois de testar a conexão com cada um."""
    entries = new_connectors_from_form()
    for name, entry in (entries or {}).items():
        if error := validate(name, entry["config"], connectors):
            st.error(error)
            continue
        connector = Connector(name, **entry, enabled=True, custom=True)
        with st.spinner(f"Conectando a {name}..."):
            connection = get_services().hub.test(connector)
        if connection.error:
            st.error(f"{name}: {connection.error}")
            continue
        connectors[name] = connector
        save_connectors(connectors)
        st.success(f"{name} adicionado e ativo: {summary(connection)}.")
        st.code("\n".join(tool.name for tool in connection.tools), language=None)


def render() -> None:
    connectors = sync_connectors()
    st.title("Conectores")
    st.caption(
        "Cada conector é um servidor MCP. Os locais (stdio) rodam como processos nesta máquina; os remotos (http) "
        "são acessados pela URL. As ferramentas dos conectores ligados entram no agente com o nome do conector como prefixo."
    )
    catalog_tab, add_tab = st.tabs(["Catálogo", "Adicionar conector"])
    with catalog_tab:
        catalog(connectors)
    with add_tab:
        add_form(connectors)
