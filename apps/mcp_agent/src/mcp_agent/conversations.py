"""Conversas guardadas no checkpointer.

O InMemorySaver grava um checkpoint do estado do agente a cada passo, separado
por thread_id. Cada conversa da interface é uma thread: a lista de conversas, o
histórico mostrado na tela e a exclusão saem todos do próprio checkpointer, sem
uma segunda cópia das mensagens. Como o nome diz, tudo some quando o processo
termina; um SqliteSaver ou PostgresSaver no lugar dele manteria as conversas.
"""

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver


def thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def messages(checkpointer: BaseCheckpointSaver, thread_id: str) -> list[BaseMessage]:
    """Mensagens do último checkpoint da conversa."""
    saved = checkpointer.get_tuple(thread_config(thread_id))
    return saved.checkpoint["channel_values"].get("messages", []) if saved else []


def list_conversations(checkpointer: BaseCheckpointSaver) -> list[dict]:
    """Uma entrada por thread, da mais recente para a mais antiga, com a primeira pergunta como título."""
    latest = {}
    for saved in checkpointer.list(None):
        thread_id = saved.config["configurable"]["thread_id"]
        if thread_id not in latest or saved.checkpoint["ts"] > latest[thread_id]["updated"]:
            latest[thread_id] = {"id": thread_id, "updated": saved.checkpoint["ts"]}
    for conversation in latest.values():
        first = next((m for m in messages(checkpointer, conversation["id"]) if m.type == "human"), None)
        conversation["title"] = " ".join(str(first.content).split())[:40] if first else "(vazia)"
    return sorted(latest.values(), key=lambda c: c["updated"], reverse=True)


def delete(checkpointer: BaseCheckpointSaver, thread_id: str) -> None:
    checkpointer.delete_thread(thread_id)
