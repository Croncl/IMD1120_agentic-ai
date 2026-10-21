"""Caminhos do projeto e configurações do agente, gravadas em data/settings.json."""

import json
from dataclasses import asdict, dataclass, fields
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_DIR / "config"
SERVERS_DIR = PROJECT_DIR / "servers"
DATA_DIR = PROJECT_DIR / "data"
WORKSPACE_DIR = PROJECT_DIR / "workspace"
SETTINGS_FILE = DATA_DIR / "settings.json"

MODELS = ["openai:gpt-5.4-mini", "openai:gpt-5.4", "openai:gpt-4.1-mini", "openai:gpt-4.1"]

DEFAULT_SYSTEM_PROMPT = """Você é um assistente que cumpre os pedidos do usuário com as ferramentas dos conectores MCP ativos.
O nome de cada ferramenta começa pelo conector de origem, como fetch_fetch ou filesystem_write_file.

- Use as ferramentas sempre que o pedido depender de dados externos, e nunca invente o que uma ferramenta poderia consultar.
- Quando um passo depender do resultado de outro, chame as ferramentas uma de cada vez.
- Arquivos são lidos e gravados na pasta {workspace}.
- Cite a fonte de cada informação: o link, o identificador do artigo ou o arquivo.
- Responda em português, de forma direta.

A data de hoje é {today}."""


@dataclass
class Settings:
    """Configurações do agente editáveis na página Configurações."""

    model: str = MODELS[0]
    temperature: float = 0.0
    max_steps: int = 30
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


def load_settings() -> Settings:
    """Lê as configurações gravadas, com o padrão para o que faltar."""
    if not SETTINGS_FILE.exists():
        return Settings()
    saved = json.loads(SETTINGS_FILE.read_text())
    return Settings(**{f.name: saved[f.name] for f in fields(Settings) if f.name in saved})


def save_settings(settings: Settings) -> None:
    """Grava as configurações em data/settings.json."""
    DATA_DIR.mkdir(exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2))


def prepare_dirs() -> None:
    """Cria as pastas de dados e de trabalho, que o filesystem e o memory exigem que existam."""
    for directory in (DATA_DIR, WORKSPACE_DIR):
        directory.mkdir(exist_ok=True)


def render_system_prompt(template: str) -> str:
    """Substitui {workspace} e {today} na mensagem de sistema."""
    return template.replace("{workspace}", str(WORKSPACE_DIR)).replace("{today}", date.today().isoformat())
