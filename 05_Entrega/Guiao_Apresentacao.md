# Guiao de Apresentacao: FitMap

**UC:** Tecnologias e Aplicacoes de Bases de Dados (TABD) | **Ano letivo:** 2025/2026  
**Duracao sugerida:** 15–20 minutos

---

## Estrutura da Apresentacao

### 1. Introducao (2 min)

- "O FitMap responde a uma pergunta simples: onde posso treinar perto de mim?"
- Mostrar a **landing page** — 3 390 instalacoes, 9 categorias, 234+ cidades
- Destacar: dados reais do OpenStreetMap, nao sinteticos

### 2. Demonstracao ao vivo (8 min)

**Cenario 1 — Pesquisa por proximidade GPS**
1. Clicar "Usar a minha localizacao"
2. Mostrar o circulo de raio no mapa e os resultados ordenados por distancia
3. Mostrar o painel `$geoNear · 3 km · $SGEONEAR` com resultados
4. Expandir o raio automaticamente se nao houver resultados

**Cenario 2 — Filtro por cidade e categoria**
1. Selecionar "Lisboa" na lista de cidades
2. Clicar no filtro "Ginasio"
3. Mostrar os 69 ginasios de Lisboa

**Cenario 3 — Selecao por area**
1. Clicar "Desenhar area"
2. Desenhar um poligono sobre uma zona
3. Mostrar o painel com instalacoes + breakdown por categoria

**Cenario 4 — Rota e eventos**
1. Clicar num marcador → abrir painel de detalhe
2. Mostrar modalidades, acessibilidade, eventos proximos
3. Clicar "Calcular rota" → rota de carro → mudar para a pe

### 3. Arquitetura e MongoDB (5 min)

- Mostrar diagrama: OSM → seed → MongoDB → FastAPI → Leaflet
- Explicar indice `2dsphere`: "indexa pontos sobre uma esfera, distancia geodesica"
- Mostrar pipeline `$geoNear` no codigo (web/server.py)
- Explicar `$facet`: "5 agregacoes paralelas numa unica query"
- Explicar `$unwind` + `$group` para modalidades multikey

### 4. Stack e Decisoes (3 min)

- Por que MongoDB e nao PostgreSQL + PostGIS?
  - Schema flexivel para dados OSM heterogeneos
  - `$geoNear` e `$geoWithin` suficientes para points
- Por que FastAPI?
  - ASGI async, documentacao automatica `/docs`
- Por que OSRM publico?
  - Zero configuracao, 3 perfis, < 100 ms de resposta

### 5. Conclusao (2 min)

- 3 390 instalacoes reais, 234+ municipios, 9 categorias
- Latencia media: 45–80 ms para queries geoespaciais
- Cobertura nacional completa com dados auditaveis
- Extensoes possiveis: clustering, heatmap, bus stops, reviews

---

## Perguntas Previstas

**"Como e que o $geoNear funciona internamente?"**
> O indice 2dsphere organiza os pontos numa arvore espacial. O $geoNear percorre-a do mais proximo para o mais distante, sem fazer scan completo. Daí os ~45 ms mesmo com 3 390 documentos.

**"Porque nao usaram PostGIS?"**
> Os dados OSM sao heterogeneos — cada instalacao tem um conjunto diferente de tags. O modelo documental elimina ALTER TABLE a cada nova tag. Para operacoes de ponto ($geoNear, $geoWithin), o MongoDB e equivalente ao PostGIS em termos funcionais.

**"Os dados sao atualizados?"**
> Sao um snapshot OSM. Para producao, o seed poderia correr periodicamente (cron) sem parar o servidor web, aproveitando a separacao seed/web do Docker Compose.

**"O que e o $facet?"**
> Permite executar multiplas sub-pipelines de agregacao em paralelo sobre o mesmo conjunto de dados numa unica query. Usamos para calcular totais, categorias, modalidades e cidades ao mesmo tempo.
