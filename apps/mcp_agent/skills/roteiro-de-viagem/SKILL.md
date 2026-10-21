---
name: roteiro-de-viagem
description: Monta um roteiro de viagem com voo, deslocamentos e horário local. Use quando o usuário pedir para planejar uma viagem, um roteiro ou um passeio em outra cidade.
---

1. Se o usuário informou origem e data, busque o voo mais barato com a ferramenta de voos e anote preço, duração e escalas.
2. Escolha três pontos turísticos da cidade de destino e calcule com a ferramenta de rotas o tempo a pé entre eles, na ordem da visita. Passe os lugares pelo nome em inglês seguido da cidade, como "Forbidden City, Beijing", que é como o OpenStreetMap os encontra.
3. Consulte o horário local atual do destino e a diferença para o horário de Brasília.
4. Responda com:
   - uma linha com o voo (preço na moeda devolvida pela ferramenta, duração e escalas);
   - uma tabela com as colunas Ordem, Lugar e Tempo a pé até o próximo;
   - uma linha com a diferença de fuso.

Se o conector de voos ou o de mapas não estiver ativo, diga qual parte do roteiro ficou de fora e monte o resto.
