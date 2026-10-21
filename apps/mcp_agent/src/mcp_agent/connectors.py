"""Catálogo de conectores MCP.

Um conector é uma entrada no formato mcpServers, o mesmo do Claude Desktop, do
Cursor e do Claude Code: {"url": ...} para servidores remotos e
{"command": ..., "args": [...], "env": {...}} para servidores locais. Os conectores
prontos vêm de config/catalog.json, e os adicionados pela interface, junto com a
lista dos ativos, ficam em data/connectors.json.
"""

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from mcp_agent.settings import CONFIG_DIR, DATA_DIR, PROJECT_DIR, SERVERS_DIR, WORKSPACE_DIR

CATALOG_FILE = CONFIG_DIR / "catalog.json"
STATE_FILE = DATA_DIR / "connectors.json"
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")

PLACEHOLDERS = {
    "{workspace}": str(WORKSPACE_DIR),
    "{data}": str(DATA_DIR),
    "{servers}": str(SERVERS_DIR),
    "{repository}": str(PROJECT_DIR.parents[1]),
    "{python}": sys.executable,
}


@dataclass
class Connector:
    """Um servidor MCP que o agente pode usar."""

    name: str
    config: dict
    description: str = ""
    category: str = "Adicionados"
    example: str = ""
    requires: list[str] = field(default_factory=list)
    enabled: bool = False
    custom: bool = False

    @property
    def transport(self) -> str:
        return "http" if "url" in self.config else "stdio"

    def problems(self) -> list[str]:
        """Motivos que impedem a conexão antes mesmo de tentar."""
        missing = [f"variável {name} não definida" for name in self.requires if not os.environ.get(name)]
        command = self.resolved_config().get("command")
        if command and not shutil.which(command):
            missing.append(f"comando {command} não encontrado no PATH")
        return missing

    def resolved_config(self) -> dict:
        """Configuração com os caminhos do projeto e as variáveis de ambiente no lugar."""
        return expand(self.config)

    def to_json(self) -> dict:
        return {"config": self.config, "description": self.description, "category": self.category, "example": self.example, "requires": self.requires}


def expand(value):
    """Troca os marcadores {workspace}, {data}, ... e as variáveis ${NOME} em toda a estrutura."""
    if isinstance(value, dict):
        return {key: expand(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand(item) for item in value]
    if isinstance(value, str):
        for marker, path in PLACEHOLDERS.items():
            value = value.replace(marker, path)
        return os.path.expandvars(value)
    return value


def read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_connectors() -> dict[str, Connector]:
    """Junta o catálogo e os conectores adicionados, marcando os ativos."""
    state = read_json(STATE_FILE)
    connectors = {name: Connector(name, **entry) for name, entry in read_json(CATALOG_FILE).items()}
    connectors |= {name: Connector(name, **entry, custom=True) for name, entry in state.get("custom", {}).items()}
    if "enabled" in state:
        for connector in connectors.values():
            connector.enabled = connector.name in state["enabled"]
    return connectors


def save_connectors(connectors: dict[str, Connector]) -> None:
    """Grava os conectores adicionados e a lista dos ativos em data/connectors.json."""
    DATA_DIR.mkdir(exist_ok=True)
    state = {
        "enabled": [c.name for c in connectors.values() if c.enabled],
        "custom": {c.name: c.to_json() for c in connectors.values() if c.custom},
    }
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def validate(name: str, config: dict, connectors: dict[str, Connector]) -> str | None:
    """Devolve a mensagem de erro de um conector novo, ou None se ele for válido."""
    if not NAME_PATTERN.match(name):
        return f"nome inválido: {name!r}; use letras minúsculas, números e hífen"
    if name in connectors:
        return f"já existe um conector chamado {name}"
    if "url" in config:
        return None if re.match(r"^https?://", config["url"]) else "a URL precisa começar com http:// ou https://"
    if not config.get("command"):
        return "informe uma URL ou um comando"
    return None


def parse_mcp_servers(text: str) -> dict[str, dict]:
    """Lê um JSON colado de um README, com ou sem a chave mcpServers externa."""
    data = json.loads(text)
    servers = data.get("mcpServers", data)
    if not isinstance(servers, dict) or not all(isinstance(entry, dict) for entry in servers.values()):
        raise ValueError("o JSON precisa mapear nomes de servidores para configurações")
    # Alguns clientes usam "type" e "serverUrl"; o formato do FastMCP só precisa da url.
    return {name: {key: value for key, value in entry.items() if key != "type"} | ({"url": entry["serverUrl"]} if "serverUrl" in entry else {}) for name, entry in servers.items()}
