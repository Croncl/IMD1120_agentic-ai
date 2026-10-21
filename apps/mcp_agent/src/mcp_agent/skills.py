"""Skills: instruções que o modelo carrega quando a tarefa pede.

Uma skill é uma pasta com um SKILL.md, cujo frontmatter traz name e description,
e arquivos de apoio opcionais. O agente vê só o nome e a descrição de cada skill
na mensagem de sistema; o corpo entra no contexto quando ele chama load_skill, e
os arquivos de apoio, quando o corpo os cita e ele chama read_skill_file. Essa
revelação progressiva mantém o contexto pequeno mesmo com muitas skills.

As skills vêm de dois lugares: a pasta skills/ do projeto e os conectores ativos
que publicam recursos skill://{nome}/SKILL.md, como faz o SkillsDirectoryProvider
do FastMCP. As locais começam ligadas; as de conectores começam desligadas, porque
são instruções de terceiros que entram na mensagem de sistema e merecem uma
leitura antes.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from fastmcp.utilities.skills import get_skill_manifest
from langchain_core.tools import BaseTool, StructuredTool

from mcp_agent.hub import MCPHub
from mcp_agent.settings import DATA_DIR, PROJECT_DIR

SKILLS_DIR = PROJECT_DIR / "skills"
STATE_FILE = DATA_DIR / "skills.json"
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass
class Skill:
    """Uma skill disponível, local ou publicada por um conector."""

    name: str
    description: str
    source: str = "local"
    path: Path | None = None
    files: list[str] = field(default_factory=list)
    enabled: bool = True

    @property
    def uri(self) -> str:
        return f"skill://{self.name}/SKILL.md"


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Separa o frontmatter YAML do corpo de um SKILL.md."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def compose(name: str, description: str, body: str) -> str:
    """Monta o texto de um SKILL.md a partir das três partes."""
    header = yaml.safe_dump({"name": name, "description": description}, allow_unicode=True, sort_keys=False, width=1000)
    return f"---\n{header}---\n\n{body.strip()}\n"


def local_skills() -> list[Skill]:
    skills = []
    for main in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        meta, _ = split_frontmatter(main.read_text())
        files = sorted(str(p.relative_to(main.parent)) for p in main.parent.rglob("*") if p.is_file() and p != main)
        skills.append(Skill(meta.get("name", main.parent.name), meta.get("description", ""), path=main.parent, files=files))
    return skills


def remote_skills(hub: MCPHub) -> list[Skill]:
    """Skills publicadas pelos conectores ativos, achadas pela forma do URI do recurso."""
    return [
        Skill(str(r.uri)[len("skill://"):-len("/SKILL.md")], r.description or "", source=server)
        for server, connection in hub.connections.items()
        for r in connection.resources
        if str(r.uri).startswith("skill://") and str(r.uri).endswith("/SKILL.md")
    ]


def load_skills(hub: MCPHub) -> dict[str, Skill]:
    """Junta as skills locais e as dos conectores, com as escolhas gravadas pelo usuário."""
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    enabled, disabled = set(state.get("enabled", [])), set(state.get("disabled", []))
    skills = {}
    for skill in local_skills() + remote_skills(hub):
        # Uma skill remota com o nome de outra já existente ganha o conector como prefixo.
        key = skill.name if skill.name not in skills else f"{skill.source}-{skill.name}"
        skill.enabled = key in enabled or (skill.source == "local" and key not in disabled)
        skills[key] = skill
    return skills


def save_state(skills: dict[str, Skill]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    state = {"enabled": [k for k, s in skills.items() if s.enabled], "disabled": [k for k, s in skills.items() if not s.enabled]}
    STATE_FILE.write_text(json.dumps(state, indent=2))


def save_local(name: str, description: str, body: str) -> Path:
    """Cria ou reescreve uma skill local."""
    if not NAME_PATTERN.match(name):
        raise ValueError(f"nome inválido: {name!r}; use letras minúsculas, números e hífen")
    if not description.strip():
        raise ValueError("a descrição é obrigatória: é por ela que o modelo decide carregar a skill")
    folder = SKILLS_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(compose(name, description.strip(), body))
    return folder


def delete_local(skill: Skill) -> None:
    for path in sorted(skill.path.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    skill.path.rmdir()


def catalog_text(skills: list[Skill]) -> str:
    """Trecho da mensagem de sistema com o nome e a descrição de cada skill ativa."""
    lines = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    return f"""## Skills

Uma skill traz instruções para um tipo de tarefa. Quando o pedido corresponder à descrição de uma skill, chame load_skill com o nome dela antes de qualquer outra ferramenta e siga as instruções. Se elas citarem um arquivo, leia-o com read_skill_file.

{lines}"""


async def read_text(hub: MCPHub, skill: Skill, path: str) -> str:
    """Lê um arquivo da skill, do disco ou do servidor que a publica."""
    if skill.source == "local":
        target = (skill.path / path).resolve()
        if not target.is_relative_to(skill.path.resolve()) or not target.is_file():
            return f"erro: a skill {skill.name} não tem o arquivo {path}"
        return target.read_text()
    contents = await hub.connections[skill.source].adapter.client.read_resource(f"skill://{skill.name}/{path}")
    return "\n".join(c.text for c in contents if hasattr(c, "text"))


async def list_files(hub: MCPHub, skill: Skill) -> list[str]:
    if skill.source == "local":
        return skill.files
    manifest = await get_skill_manifest(hub.connections[skill.source].adapter.client, skill.name)
    return [f.path for f in manifest.files if f.path != "SKILL.md"]


def skill_tools(skills: dict[str, Skill], hub: MCPHub) -> list[BaseTool]:
    """As duas ferramentas que dão ao agente acesso às skills ativas."""
    active = {key: s for key, s in skills.items() if s.enabled}

    async def load_skill(name: str) -> str:
        """Carrega as instruções completas de uma skill pelo nome."""
        if name not in active:
            return f"erro: skill desconhecida; as disponíveis são {', '.join(active)}"
        _, body = split_frontmatter(await read_text(hub, active[name], "SKILL.md"))
        files = await list_files(hub, active[name])
        return body + (f"\n\nArquivos de apoio: {', '.join(files)}" if files else "")

    async def read_skill_file(name: str, path: str) -> str:
        """Lê um arquivo de apoio citado nas instruções de uma skill."""
        if name not in active:
            return f"erro: skill desconhecida; as disponíveis são {', '.join(active)}"
        return await read_text(hub, active[name], path)

    return [StructuredTool.from_function(coroutine=load_skill), StructuredTool.from_function(coroutine=read_skill_file)]
