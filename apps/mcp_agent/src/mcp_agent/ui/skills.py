"""Página de skills: ver, ligar e desligar, criar, editar e colar skills."""

import streamlit as st

from mcp_agent.skills import Skill, delete_local, load_skills, save_local, save_state, split_frontmatter
from mcp_agent.ui.state import get_services, sync_connectors

TEMPLATE = """Siga estes passos:

1. ...
2. ...

Formato da resposta: ...
"""


def toggle(skills: dict[str, Skill], key: str) -> None:
    skills[key].enabled = st.session_state[f"skill_{key}"]
    save_state(skills)


def content(skill: Skill) -> str:
    """Texto do SKILL.md, do disco ou do conector que publica a skill."""
    if skill.source == "local":
        return (skill.path / "SKILL.md").read_text()
    return get_services().hub.read_resource(skill.source, skill.uri)


def card(key: str, skill: Skill, skills: dict[str, Skill]) -> None:
    with st.container(border=True):
        st.toggle(f"**{key}**", value=skill.enabled, key=f"skill_{key}", on_change=toggle, args=(skills, key))
        st.badge("local" if skill.source == "local" else f"conector {skill.source}", color="green" if skill.source == "local" else "violet")
        st.caption(skill.description)
        with st.expander("SKILL.md"):
            _, body = split_frontmatter(content(skill))
            st.markdown(body)
            if skill.files:
                st.caption("Arquivos de apoio: " + ", ".join(f"`{f}`" for f in skill.files))
        if skill.source == "local":
            edit, remove = st.columns(2)
            if edit.button("Editar", key=f"edit_{key}", icon=":material/edit:"):
                st.session_state.editing = key
                st.toast(f"{key} aberta na aba Criar ou editar.")
                st.rerun()
            if remove.button("Apagar", key=f"delete_{key}", icon=":material/delete:"):
                delete_local(skill)
                st.rerun()


def editor(skills: dict[str, Skill]) -> None:
    """Formulário de criação, ou de edição quando um card pediu para editar."""
    key = st.session_state.get("editing")
    skill = skills.get(key) if key else None
    meta, body = split_frontmatter(content(skill)) if skill else ({}, TEMPLATE)
    st.subheader(f"Editando {key}" if skill else "Nova skill")
    with st.form("skill_form"):
        name = st.text_input("Nome", meta.get("name", ""), disabled=skill is not None, placeholder="minha-skill")
        description = st.text_area(
            "Descrição", meta.get("description", ""), height=80,
            help="É a única parte que o modelo vê antes de carregar a skill: diga o que ela faz e quando usá-la.",
        )
        body = st.text_area("Instruções (Markdown)", body, height=320)
        if st.form_submit_button("Salvar", type="primary", icon=":material/save:"):
            try:
                save_local(skill.name if skill else name.strip(), description, body)
            except ValueError as error:
                st.error(str(error))
                return
            st.session_state.pop("editing", None)
            st.toast("Skill salva. Ela vale a partir da próxima mensagem.")
            st.rerun()
    if skill and st.button("Cancelar edição"):
        st.session_state.pop("editing", None)
        st.rerun()


def paste(skills: dict[str, Skill]) -> None:
    """Importa um SKILL.md colado, com o frontmatter name e description."""
    st.caption("Cole o conteúdo de um SKILL.md, por exemplo de um repositório de skills. Os arquivos de apoio podem ser criados depois na pasta skills/.")
    with st.form("paste_form"):
        text = st.text_area("SKILL.md", height=320, placeholder="---\nname: minha-skill\ndescription: ...\n---\n\nInstruções...")
        if st.form_submit_button("Importar", icon=":material/upload:"):
            meta, body = split_frontmatter(text)
            try:
                if str(meta.get("name", "")) in skills:
                    raise ValueError(f"já existe uma skill chamada {meta['name']}")
                save_local(str(meta.get("name", "")), str(meta.get("description", "")), body)
            except ValueError as error:
                st.error(str(error))
                return
            st.toast(f"Skill {meta['name']} importada.")
            st.rerun()


def render() -> None:
    sync_connectors()
    skills = load_skills(get_services().hub)
    st.title("Skills")
    st.caption(
        "Uma skill ensina o agente a fazer um tipo de tarefa. O modelo vê só o nome e a descrição de cada skill ligada, "
        "e carrega as instruções com load_skill quando o pedido corresponde a ela. As locais ficam na pasta skills/; "
        "as de conectores vêm de servidores MCP que publicam recursos skill://."
    )
    list_tab, edit_tab, paste_tab = st.tabs(["Skills", "Criar ou editar", "Colar SKILL.md"])
    with list_tab:
        if not skills:
            st.info("Nenhuma skill. Crie uma na aba ao lado ou ligue um conector que publique skills.")
        for source in dict.fromkeys(s.source for s in skills.values()):
            group = {key: s for key, s in skills.items() if s.source == source}
            active = sum(s.enabled for s in group.values())
            st.subheader("Locais" if source == "local" else f"Conector {source}")
            # As skills de conectores ficam recolhidas: um servidor pode publicar dezenas delas.
            if source != "local" and not st.toggle(f"Mostrar as {len(group)} skills ({active} ligada(s))", key=f"show_{source}"):
                continue
            columns = st.columns(3)
            for index, (key, skill) in enumerate(group.items()):
                with columns[index % 3]:
                    card(key, skill, skills)
    with edit_tab:
        editor(skills)
    with paste_tab:
        paste(skills)
