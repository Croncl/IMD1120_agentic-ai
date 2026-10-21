# Agente MCP

Agente com ferramentas vindas de servidores MCP e instruções vindas de skills, com interface em Streamlit. Os servidores são escolhidos em um catálogo ou adicionados pela interface, as skills são escritas na própria interface ou publicadas pelos servidores, e o agente passa a usar umas e outras sem nenhuma linha de código nova.

## Execução

```bash
conda activate ai
pip install -e apps/mcp_agent                 # com o servidor da disciplina: pip install -e "apps/mcp_agent[course]"
streamlit run apps/mcp_agent/app.py
```

A instalação precisa ser editável (`-e`), porque o app encontra o catálogo, o `workspace/` e o `data/` a partir da pasta do projeto.

A chave da OpenAI vem da `OPENAI_API_KEY`, no ambiente ou em um `.env` nesta pasta ou na raiz do repositório. Os conectores locais são iniciados com `uvx` (instalado junto, pelo pacote `uv`) ou com `npx`, que vem com o Node.js. Um conector cujo comando não está no `PATH` aparece desabilitado, com o motivo.

## Páginas

| Página | Uso |
|---|---|
| Chat | conversas, chamadas de ferramenta ao vivo, prompts e recursos dos servidores, arquivos do workspace |
| Conectores | liga e desliga os conectores do catálogo, mostra as ferramentas, os recursos e os prompts de cada um e adiciona conectores novos |
| Skills | liga e desliga skills, mostra o `SKILL.md` de cada uma e cria, edita, importa e apaga as locais |
| Configurações | modelo, temperatura, limite de passos, mensagem de sistema e memória das conversas |

Os conectores novos podem ser um servidor remoto (URL e cabeçalhos), um comando local (comando, argumentos e variáveis de ambiente) ou o JSON `mcpServers` copiado do README de um servidor. Antes de ser salvo, cada conector é testado: o app conecta, lista as primitivas e mostra o erro se algo falhar. Valores como `${MEU_TOKEN}` são lidos do ambiente na hora da conexão, então o segredo não é gravado em arquivo.

## Estrutura

```text
apps/mcp_agent/
├── app.py                  # entrada do Streamlit: navegação entre as páginas
├── pyproject.toml
├── config/
│   └── catalog.json        # conectores prontos, no formato mcpServers
├── skills/                 # skills locais, uma pasta com SKILL.md por skill
├── servers/
│   ├── course.py           # servidor MCP da disciplina
│   └── skills/             # skills que o servidor da disciplina publica por MCP
├── src/mcp_agent/
│   ├── settings.py         # caminhos, modelo e mensagem de sistema
│   ├── connectors.py       # catálogo, conectores adicionados e validação
│   ├── runtime.py          # laço de eventos em segundo plano
│   ├── hub.py              # uma conexão aberta por conector ativo
│   ├── agent.py            # create_agent com as ferramentas dos conectores
│   ├── skills.py           # skills locais e de conectores, load_skill e read_skill_file
│   ├── conversations.py    # conversas lidas do checkpointer
│   └── ui/                 # páginas: chat, conectores, skills, configurações
├── data/                   # criado ao rodar: conectores ativos, configurações, memória
└── workspace/              # criado ao rodar: arquivos do filesystem e PDFs do arXiv
```

Três decisões explicam a maior parte do código:

- **Uma conexão por conector.** O `hub.py` abre um `MCPAdapter` para cada servidor ativo e prefixa as ferramentas com o nome do conector. Um servidor que falha ao iniciar não derruba os outros, e ligar ou desligar um conector mexe só na conexão dele.
- **Um laço de eventos em segundo plano.** O Streamlit reexecuta o script inteiro a cada interação, de forma síncrona, enquanto as conexões MCP são assíncronas e precisam continuar abertas. O `runtime.py` mantém um laço em outra thread durante toda a vida do processo, e a interface envia corrotinas para ele.
- **O histórico no checkpointer.** O agente é recriado a cada turno com os conectores e as configurações do momento, e as conversas continuam porque vivem no `InMemorySaver`, separadas por `thread_id`. A lista de conversas e o histórico na tela são lidos do próprio checkpointer. Trocá-lo por um `SqliteSaver` manteria as conversas depois que o processo termina.

## Skills

Uma skill é uma pasta com um `SKILL.md`, no formato aberto usado por Claude, Codex, Cursor e outros agentes: o frontmatter traz `name` e `description`, o corpo traz as instruções, e a pasta pode ter arquivos de apoio, como um modelo de documento. A ferramenta ensina o agente a agir; a skill ensina como fazer um tipo de tarefa com as ferramentas que ele tem.

O agente vê só o nome e a descrição de cada skill ligada, em um trecho que o app acrescenta à mensagem de sistema. Quando o pedido corresponde a uma delas, ele chama `load_skill`, e o corpo entra no contexto; se o corpo cita um arquivo, ele chama `read_skill_file`. Essa revelação progressiva mantém o contexto pequeno com muitas skills, e um pedido sem relação com nenhuma delas não carrega nada.

| Skill | Origem | Usa |
|---|---|---|
| `relatorio-de-pesquisa` | `skills/` | arxiv, huggingface e filesystem, com o modelo em `modelo.md` |
| `roteiro-de-viagem` | `skills/` | kiwi, openstreetmap e time |
| `regimento` | conector disciplina | `search_regiment`, com a citação do artigo e da página |

Um servidor MCP publica skills como recursos `skill://{nome}/SKILL.md`; no FastMCP, basta `mcp.add_provider(SkillsDirectoryProvider(pasta))`, como faz o `servers/course.py`. O conector do Hugging Face, por exemplo, publica mais de vinte. As skills locais começam ligadas e as de conectores começam desligadas, porque são instruções de terceiros que entram na mensagem de sistema e merecem uma leitura antes.

## Catálogo

| Categoria | Conectores |
|---|---|
| Web e arquivos | fetch, filesystem, playwright |
| Busca e pesquisa | exa, arxiv, wikipedia, huggingface |
| Desenvolvimento | deepwiki, context7, github (`GITHUB_TOKEN`), git |
| Viagem e mapas | kiwi, openstreetmap, airbnb |
| Memória e raciocínio | memory, time, sequential-thinking |
| Disciplina | disciplina (`servers/course.py`, `OPENAI_API_KEY`) |

Os marcadores `{workspace}`, `{data}`, `{servers}`, `{repository}` e `{python}` do `catalog.json` são trocados pelos caminhos do projeto na hora da conexão. Mais servidores em [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers).

O servidor da disciplina também roda sozinho, com `python apps/mcp_agent/servers/course.py`, e é o que o `.mcp.json` da raiz registra no Claude Code.
