"""Servidor MCP da disciplina: regimento da UFRN, notebooks e questões de revisão.

    python apps/mcp_agent/servers/course.py

A busca no regimento usa o índice chroma_regimento, gerado pelo notebook 11 - RAG
na raiz do repositório, e precisa da OPENAI_API_KEY para o embedding da pergunta.
O .mcp.json da raiz registra este servidor no Claude Code, e o catálogo do agente
MCP (config/catalog.json) o oferece como o conector "disciplina".
"""

import json
from pathlib import Path

from langchain.embeddings import init_embeddings
from langchain_chroma import Chroma
from fastmcp import FastMCP
from fastmcp.server.providers.skills import SkillsDirectoryProvider

ROOT = Path(__file__).resolve().parents[3]
INDEX = ROOT / "chroma_regimento"

mcp = FastMCP("disciplina")
# Cada pasta em servers/skills vira os recursos skill://{nome}/SKILL.md e skill://{nome}/_manifest.
mcp.add_provider(SkillsDirectoryProvider(Path(__file__).parent / "skills"))


def lessons() -> dict[str, Path]:
    """Mapeia o número de cada aula para o arquivo do notebook."""
    return {path.name[:2]: path for path in sorted(ROOT.glob("[0-9][0-9] - *.ipynb"))}


def notebook_text(path: Path) -> str:
    """Junta as células de um notebook em texto, com o código entre cercas e sem as saídas."""
    cells = json.loads(path.read_text())["cells"]
    parts = ["".join(c["source"]) if c["cell_type"] == "markdown" else "```python\n" + "".join(c["source"]) + "\n```" for c in cells]
    return "\n\n".join(parts)


@mcp.tool()
def search_regiment(query: str, k: int = 4) -> str:
    """Busca no Regimento Geral da UFRN os trechos mais parecidos com a pergunta, com a página de cada um."""
    if not INDEX.exists():
        return "erro: índice chroma_regimento não encontrado; rode o notebook 11 - RAG para gerá-lo"
    store = Chroma(collection_name="regimento", embedding_function=init_embeddings("openai:text-embedding-3-small"), persist_directory=str(INDEX))
    return "\n\n".join(f"(página {doc.metadata['page']}) {doc.page_content}" for doc in store.similarity_search(query, k=k))


@mcp.resource("curso://programa")
def syllabus() -> str:
    """Ementa e cronograma da disciplina de IA Agêntica, por unidade."""
    return (ROOT / "README.md").read_text()


@mcp.resource("curso://aulas")
def lesson_list() -> str:
    """Lista dos notebooks de aula, um por linha, com número e título."""
    return "\n".join(path.stem for path in lessons().values())


@mcp.resource("curso://aula/{number}")
def lesson(number: str) -> str:
    """Conteúdo de um notebook de aula, com markdown e código, pelo número de dois dígitos."""
    path = lessons().get(number.zfill(2))
    return notebook_text(path) if path else f"erro: não existe aula {number}"


@mcp.prompt()
def review_questions(number: str, count: str = "5") -> str:
    """Pede questões de revisão sobre uma aula, com o notebook anexado."""
    return f"""Crie {count} questões de revisão sobre a aula abaixo, em português, misturando conceito e código.
Cada questão traz a resposta esperada em uma ou duas frases, e nenhuma pergunta o que o texto já responde literalmente.

{lesson(number)}"""


if __name__ == "__main__":
    mcp.run(show_banner=False)
