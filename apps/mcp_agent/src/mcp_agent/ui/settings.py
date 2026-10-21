"""Página de configurações: modelo, limite de passos e mensagem de sistema."""

from dataclasses import replace

import streamlit as st

from mcp_agent.agent import agent_tools, system_prompt as full_system_prompt
from mcp_agent.settings import DEFAULT_SYSTEM_PROMPT, MODELS, load_settings, save_settings
from mcp_agent.skills import load_skills
from mcp_agent.ui.state import get_services, sync_connectors


def render() -> None:
    sync_connectors()
    settings = load_settings()
    st.title("Configurações")

    with st.form("settings"):
        model = st.selectbox(
            "Modelo", MODELS if settings.model in MODELS else [settings.model, *MODELS], index=0 if settings.model not in MODELS else MODELS.index(settings.model),
            accept_new_options=True, help="Qualquer identificador aceito pelo init_chat_model, como openai:gpt-5.4-mini.",
        )
        left, right = st.columns(2)
        temperature = left.slider("Temperatura", 0.0, 1.0, settings.temperature, 0.1)
        max_steps = right.number_input("Limite de passos por turno", 5, 100, settings.max_steps, help="O recursion_limit do LangGraph: cada chamada ao modelo e cada execução de ferramenta conta um passo.")
        system_prompt = st.text_area("Mensagem de sistema", settings.system_prompt, height=320, help="{workspace} vira o caminho da pasta de trabalho e {today}, a data de hoje.")
        if st.form_submit_button("Salvar", type="primary", icon=":material/save:"):
            save_settings(replace(settings, model=model, temperature=temperature, max_steps=int(max_steps), system_prompt=system_prompt))
            st.toast("Configurações salvas. Elas valem a partir da próxima mensagem.")
            st.rerun()

    if settings.system_prompt != DEFAULT_SYSTEM_PROMPT and st.button("Restaurar a mensagem de sistema padrão", icon=":material/restart_alt:"):
        save_settings(replace(settings, system_prompt=DEFAULT_SYSTEM_PROMPT))
        st.rerun()

    hub = get_services().hub
    skills = load_skills(hub)
    with st.expander("Mensagem de sistema como o modelo recebe, com o catálogo de skills"):
        st.code(full_system_prompt(settings, skills), language=None)
        st.caption(f"Ferramentas enviadas junto: {', '.join(t.name for t in agent_tools(hub, skills))}")

    checkpointer = get_services().checkpointer
    st.subheader("Memória das conversas")
    st.caption(
        "As conversas ficam em um InMemorySaver, que guarda um checkpoint do estado do agente a cada passo, por thread. "
        "Elas sobrevivem à troca de conectores e de configurações, mas somem quando o processo do Streamlit termina."
    )
    threads = {saved.config["configurable"]["thread_id"] for saved in checkpointer.list(None)}
    checkpoints = sum(1 for _ in checkpointer.list(None))
    st.metric("Conversas", len(threads))
    st.caption(f"{checkpoints} checkpoints guardados.")
    if threads and st.button("Apagar todas as conversas", icon=":material/delete_sweep:"):
        for thread_id in threads:
            checkpointer.delete_thread(thread_id)
        st.rerun()
