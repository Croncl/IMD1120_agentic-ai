"""Agente com as ferramentas dos conectores ativos e as skills ligadas."""

from collections.abc import AsyncIterator

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver

from mcp_agent.hub import MCPHub
from mcp_agent.settings import Settings, render_system_prompt
from mcp_agent.skills import Skill, catalog_text, skill_tools


def system_prompt(settings: Settings, skills: dict[str, Skill]) -> str:
    """Mensagem de sistema do usuário, seguida do catálogo de skills ativas, se houver."""
    active = [s for s in skills.values() if s.enabled]
    prompt = render_system_prompt(settings.system_prompt)
    return f"{prompt}\n\n{catalog_text(active)}" if active else prompt


def agent_tools(hub: MCPHub, skills: dict[str, Skill]) -> list[BaseTool]:
    """Ferramentas dos conectores, mais load_skill e read_skill_file quando há skill ativa."""
    has_skills = any(s.enabled for s in skills.values())
    return hub.tools() + (skill_tools(skills, hub) if has_skills else [])


def build_agent(hub: MCPHub, skills: dict[str, Skill], settings: Settings, checkpointer: BaseCheckpointSaver):
    """Monta o agente. É barato, então ele é recriado a cada turno com os conectores, as skills e as configurações do momento.

    O histórico não se perde nessa troca, porque ele vive no checkpointer, e não no agente.
    """
    model = init_chat_model(settings.model, temperature=settings.temperature)
    return create_agent(model, tools=agent_tools(hub, skills), system_prompt=system_prompt(settings, skills), checkpointer=checkpointer)


async def stream_turn(agent, text: str, thread_id: str, max_steps: int) -> AsyncIterator[BaseMessage]:
    """Executa um turno e devolve cada mensagem nova, pedido de ferramenta, resultado ou resposta, assim que ela é produzida."""
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": max_steps}
    async for update in agent.astream({"messages": [HumanMessage(text)]}, config, stream_mode="updates"):
        for node in update.values():
            for message in (node or {}).get("messages", []):
                yield message
