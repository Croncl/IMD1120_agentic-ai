"""Página de chat: conversas, prompts e recursos dos servidores, e o agente."""

import json
import uuid

import streamlit as st
from langchain_core.messages import BaseMessage
from langgraph.errors import GraphRecursionError

from mcp_agent import conversations
from mcp_agent.agent import build_agent, stream_turn
from mcp_agent.hub import describe
from mcp_agent.settings import WORKSPACE_DIR, load_settings
from mcp_agent.skills import load_skills
from mcp_agent.ui.state import get_services, sync_connectors

ATTACHMENT = "\n\n<recurso"


def text_of(message: BaseMessage) -> str:
    """Texto de uma mensagem, juntando os blocos quando o conteúdo é uma lista."""
    if isinstance(message.content, str):
        return message.content
    return "\n".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in message.content)


def show_call(call: dict, result: BaseMessage | None) -> None:
    """Mostra uma chamada de ferramenta, com os argumentos e o começo do resultado."""
    if call["name"] in ("load_skill", "read_skill_file"):
        st.markdown(f":material/school: skill **{call['args'].get('name')}** carregada" + (f": `{call['args']['path']}`" if "path" in call["args"] else ""))
        return
    st.markdown(f"`{call['name']}`")
    st.code(json.dumps(call["args"], ensure_ascii=False, indent=1), language="json")
    if result is not None:
        output = text_of(result)
        st.code(output[:1500] + ("\n..." if len(output) > 1500 else ""), language=None)


def show_question(question: str) -> None:
    """Mostra a pergunta, recolhendo o texto longo que um prompt de servidor costuma gerar."""
    if len(question) <= 1000:
        st.markdown(question)
        return
    st.markdown(question[:400] + "...")
    with st.expander(f"mensagem completa ({len(question)} caracteres)"):
        st.text(question)


def show_history(history: list[BaseMessage]) -> None:
    """Redesenha a conversa: cada resposta traz, acima dela, as chamadas que a produziram."""
    results = {m.tool_call_id: m for m in history if m.type == "tool"}
    calls = []
    for message in history:
        if message.type == "human":
            question, _, attached = text_of(message).partition(ATTACHMENT)
            with st.chat_message("user"):
                show_question(question)
                if attached:
                    st.caption(f":material/attach_file: recurso anexado: {attached.split(chr(34))[1]}")
        elif message.type == "ai" and message.tool_calls:
            calls += message.tool_calls
        elif message.type == "ai":
            with st.chat_message("assistant"):
                if calls:
                    with st.expander(f"{len(calls)} chamada(s) de ferramenta"):
                        for call in calls:
                            show_call(call, results.get(call["id"]))
                st.markdown(text_of(message))
            calls = []


def run_turn(request: str, thread_id: str) -> None:
    """Executa um turno mostrando cada chamada de ferramenta assim que ela acontece."""
    services, settings = get_services(), load_settings()
    question = request.partition(ATTACHMENT)[0]
    with st.chat_message("user"):
        show_question(question)
    with st.chat_message("assistant"):
        status = st.status("Pensando...", expanded=True)
        try:
            agent = build_agent(services.hub, load_skills(services.hub), settings, services.checkpointer)
            calls = {}
            for message in services.loop.iterate(stream_turn(agent, request, thread_id, settings.max_steps)):
                if message.type == "ai" and message.tool_calls:
                    calls |= {call["id"]: call for call in message.tool_calls}
                    status.update(label=f"Chamando {', '.join(c['name'] for c in message.tool_calls)}...")
                elif message.type == "tool":
                    with status:
                        show_call(calls[message.tool_call_id], message)
            status.update(label=f"{len(calls)} chamada(s) de ferramenta", state="complete", expanded=False)
        except GraphRecursionError:
            status.update(label="Interrompido", state="error")
            st.error(f"O agente passou de {settings.max_steps} passos. Aumente o limite em Configurações ou simplifique o pedido.")
            st.stop()
        except Exception as error:
            status.update(label="Erro", state="error")
            st.error(describe(error))
            st.stop()
    st.rerun()


def sidebar_conversations(thread_id: str) -> None:
    """Lista as conversas guardadas no checkpointer, com botões para abrir e apagar."""
    checkpointer = get_services().checkpointer
    if st.sidebar.button("Nova conversa", icon=":material/add:", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()
    for conversation in conversations.list_conversations(checkpointer):
        open_column, delete_column = st.sidebar.columns([5, 1])
        current = conversation["id"] == thread_id
        if open_column.button(conversation["title"], key=f"open_{conversation['id']}", type="primary" if current else "secondary", use_container_width=True):
            st.session_state.thread_id = conversation["id"]
            st.rerun()
        if delete_column.button("", icon=":material/delete:", key=f"delete_{conversation['id']}"):
            conversations.delete(checkpointer, conversation["id"])
            st.rerun()


def sidebar_prompts() -> None:
    """Prompts dos servidores: o usuário escolhe um, preenche os argumentos e o texto vira a próxima mensagem."""
    hub = get_services().hub
    options = {f"{server}: {p.name}": (server, p) for server, c in hub.connections.items() for p in c.prompts}
    with st.sidebar.expander(f"Prompts ({len(options)})", icon=":material/description:"):
        if not options:
            st.caption("Nenhum conector ativo oferece prompts.")
            return
        server, prompt = options[st.selectbox("Prompt", options)]
        st.caption(prompt.description or "")
        with st.form("prompt_form", border=False):
            arguments = {a.name: st.text_input(a.name + ("" if a.required else " (opcional)"), help=a.description) for a in prompt.arguments or []}
            if st.form_submit_button("Usar prompt", use_container_width=True):
                st.session_state.pending = hub.get_prompt(server, prompt.name, {k: v for k, v in arguments.items() if v})


def sidebar_resources() -> None:
    """Recursos dos servidores: a aplicação, e não o modelo, decide anexar o conteúdo à próxima mensagem."""
    hub = get_services().hub
    # Os recursos skill:// aparecem na página Skills, e quem os lê é o modelo.
    options = {str(r.uri): server for server, c in hub.connections.items() for r in c.resources if not str(r.uri).startswith("skill://")}
    with st.sidebar.expander(f"Recursos ({len(options)})", icon=":material/attach_file:"):
        if not options:
            st.caption("Nenhum conector ativo oferece recursos.")
            return
        uri = st.selectbox("Recurso", options)
        if st.button("Anexar à próxima mensagem", use_container_width=True):
            st.session_state.attachment = (uri, hub.read_resource(options[uri], uri))


def sidebar_workspace() -> None:
    """Arquivos gravados pelo agente na pasta workspace, para baixar."""
    files = sorted(path for path in WORKSPACE_DIR.rglob("*") if path.is_file())
    with st.sidebar.expander(f"Workspace ({len(files)})", icon=":material/folder:"):
        for path in files[:30]:
            name = str(path.relative_to(WORKSPACE_DIR))
            st.download_button(name, path.read_bytes(), file_name=path.name, key=f"file_{name}", icon=":material/download:", use_container_width=True)
        if not files:
            st.caption("Os arquivos que o agente gravar aparecem aqui.")


def render() -> None:
    connectors = sync_connectors()
    hub = get_services().hub
    st.session_state.setdefault("thread_id", str(uuid.uuid4()))
    thread_id = st.session_state.thread_id

    sidebar_conversations(thread_id)
    st.sidebar.divider()
    sidebar_prompts()
    sidebar_resources()
    sidebar_workspace()

    st.title("Agente MCP")
    active = [c for c in hub.connections.values() if not c.error]
    failed = [c for c in hub.connections.values() if c.error]
    skills = [key for key, s in load_skills(hub).items() if s.enabled]
    st.caption(f"{len(active)} conector(es) ativo(s), {len(hub.tools())} ferramentas: " + ", ".join(c.name for c in active) + f". {len(skills)} skill(s): " + (", ".join(skills) or "nenhuma"))
    if failed:
        st.warning("Falharam: " + ", ".join(c.name for c in failed) + ". Veja os detalhes em Conectores.", icon=":material/error:")

    history = conversations.messages(get_services().checkpointer, thread_id)
    if not history:
        examples = [connectors[c.name].example for c in active if connectors[c.name].example]
        if examples:
            st.caption("Exemplos dos conectores ativos")
        for example in examples:
            if st.button(example, icon=":material/lightbulb:"):
                st.session_state.pending = example
    show_history(history)

    if attachment := st.session_state.get("attachment"):
        left, right = st.columns([6, 1])
        left.info(f"Recurso {attachment[0]} anexado à próxima mensagem ({len(attachment[1])} caracteres).", icon=":material/attach_file:")
        if right.button("Remover"):
            del st.session_state.attachment
            st.rerun()

    request = st.chat_input("Peça algo ao agente") or st.session_state.pop("pending", None)
    if request:
        if attachment := st.session_state.pop("attachment", None):
            request += f'{ATTACHMENT} uri="{attachment[0]}">\n{attachment[1]}\n</recurso>'
        run_turn(request, thread_id)
