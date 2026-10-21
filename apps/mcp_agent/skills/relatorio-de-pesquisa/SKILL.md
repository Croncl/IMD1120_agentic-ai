---
name: relatorio-de-pesquisa
description: Pesquisa um tema em artigos científicos e grava um relatório em Markdown no workspace. Use quando o usuário pedir um levantamento, estado da arte, revisão ou relatório sobre um assunto técnico ou científico.
---

1. Busque artigos sobre o tema com as ferramentas do arXiv, priorizando os dos últimos dois anos. Escolha de três a cinco.
2. Leia o resumo de cada artigo escolhido. Não descreva um artigo cujo resumo você não leu.
3. Se o conector do Hugging Face estiver ativo, procure modelos, datasets ou Spaces ligados ao tema e anote os mais baixados.
4. Leia o arquivo `modelo.md` desta skill e escreva o relatório exatamente nesse formato.
5. Grave o relatório no workspace, com o nome `relatorio-<tema-em-minusculas-com-hifens>.md`, e responda com o nome do arquivo e um resumo de duas frases.

Cite cada artigo pelo identificador do arXiv, como `arXiv:2501.01234`. Se uma ferramenta falhar, diga qual etapa ficou incompleta em vez de preencher a seção com suposições.
