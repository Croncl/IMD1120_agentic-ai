"""Conexões abertas com os servidores MCP ativos.

Cada conector tem a própria conexão, em vez de um único mcpServers com todos.
Assim um servidor que falha ao iniciar não derruba os outros, e ligar ou desligar
um conector abre ou fecha só aquela conexão.
"""

import asyncio
import json
from dataclasses import dataclass, field

from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool
from mcp.types import Prompt, Resource

from mcp_agent.connectors import Connector

try:
    from builtins import BaseExceptionGroup
except ImportError:  # Python 3.10
    from exceptiongroup import BaseExceptionGroup
from mcp_agent.runtime import BackgroundLoop

CONNECT_TIMEOUT = 120


@dataclass
class Connection:
    """Estado de um conector: as primitivas descobertas, ou o erro da conexão."""

    name: str
    key: str
    adapter: MCPAdapter | None = None
    tools: list[BaseTool] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    prompts: list[Prompt] = field(default_factory=list)
    error: str | None = None


def describe(error: BaseException) -> str:
    """Mensagem curta de um erro, abrindo os ExceptionGroup do anyio."""
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    return f"{type(error).__name__}: {error}"[:500]


async def connect(connector: Connector) -> Connection:
    """Abre a conexão com um servidor e descobre ferramentas, recursos e prompts."""
    connection = Connection(connector.name, json.dumps(connector.config, sort_keys=True))
    adapter = MCPAdapter({"mcpServers": {connector.name: connector.resolved_config()}})
    try:
        await asyncio.wait_for(adapter.__aenter__(), CONNECT_TIMEOUT)
        connection.adapter = adapter
        connection.tools = await adapter.list_tools()
        capabilities = adapter.client.server_capabilities
        if capabilities is None or capabilities.resources:
            connection.resources = await adapter.client.list_resources()
        if capabilities is None or capabilities.prompts:
            connection.prompts = await adapter.client.list_prompts()
    except Exception as error:
        connection.error = describe(error)
        await disconnect(connection)
        return connection
    # Com uma conexão por servidor, os nomes chegam sem prefixo. O prefixo evita que
    # duas ferramentas de servidores diferentes com o mesmo nome colidam no agente.
    for tool in connection.tools:
        tool.name = f"{connector.name}_{tool.name}"[:64]
    return connection


async def disconnect(connection: Connection) -> None:
    """Fecha a conexão, ignorando erros de um servidor que já caiu."""
    if connection.adapter is not None:
        try:
            await connection.adapter.__aexit__(None, None, None)
        except Exception:
            pass
        connection.adapter = None


class MCPHub:
    """Mantém uma conexão aberta para cada conector ativo."""

    def __init__(self, loop: BackgroundLoop) -> None:
        self.loop = loop
        self.connections: dict[str, Connection] = {}

    def sync(self, connectors: dict[str, Connector]) -> None:
        """Fecha as conexões dos conectores desligados ou alterados e abre as dos novos."""
        wanted = {c.name: c for c in connectors.values() if c.enabled and not c.problems()}
        stale = [c for name, c in self.connections.items() if name not in wanted or c.key != json.dumps(wanted[name].config, sort_keys=True)]
        fresh = [c for name, c in wanted.items() if name not in self.connections or self.connections[name] in stale]
        if not stale and not fresh:
            return

        async def update():
            await asyncio.gather(*(disconnect(c) for c in stale))
            return await asyncio.gather(*(connect(c) for c in fresh))

        for connection in stale:
            del self.connections[connection.name]
        for connection in self.loop.run(update()):
            self.connections[connection.name] = connection

    def test(self, connector: Connector) -> Connection:
        """Conecta, descobre as primitivas e desconecta, para validar um conector novo."""
        connection = self.loop.run(connect(connector))
        self.loop.run(disconnect(connection))
        return connection

    def tools(self) -> list[BaseTool]:
        return [tool for connection in self.connections.values() for tool in connection.tools]

    def get_prompt(self, server: str, name: str, arguments: dict[str, str]) -> str:
        """Renderiza um prompt do servidor e junta o texto das mensagens."""
        result = self.loop.run(self.connections[server].adapter.client.get_prompt(name, arguments))
        return "\n\n".join(m.content.text for m in result.messages if hasattr(m.content, "text"))

    def read_resource(self, server: str, uri: str) -> str:
        """Lê um recurso do servidor e devolve o texto."""
        contents = self.loop.run(self.connections[server].adapter.client.read_resource(uri))
        return "\n\n".join(c.text for c in contents if hasattr(c, "text"))
