"""Laço de eventos em uma thread própria.

O Streamlit executa o script de forma síncrona e o reexecuta a cada interação,
enquanto as conexões MCP são assíncronas e precisam continuar abertas entre uma
execução e outra. Um laço único, rodando em segundo plano durante toda a vida do
processo, guarda essas conexões, e o script envia corrotinas para ele.
"""

import asyncio
import threading
from collections.abc import AsyncIterator, Coroutine, Iterator
from typing import Any


class BackgroundLoop:
    """Executa corrotinas em um laço de eventos que vive em outra thread."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True, name="mcp-loop").start()

    def run(self, coroutine: Coroutine[Any, Any, Any], timeout: float | None = None) -> Any:
        """Executa a corrotina no laço e espera o resultado."""
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout)

    def iterate(self, generator: AsyncIterator[Any]) -> Iterator[Any]:
        """Consome um gerador assíncrono item a item, para a interface mostrar cada passo assim que ele chega."""
        while True:
            try:
                yield self.run(generator.__anext__())
            except StopAsyncIteration:
                return
