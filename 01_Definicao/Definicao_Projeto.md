# Definição Estratégica do Projeto: GlobalShop Sentiment Intelligence

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD)
**Ano Letivo:** 2025/2026

---

## 1. Contextualização e Cenário de Negócio

A **GlobalShop** é um marketplace de comércio eletrónico que opera em Portugal Continental, com presença ativa nas principais cidades do país — Lisboa, Porto, Coimbra, Braga, Faro e Setúbal. Com uma base de clientes crescente e um catálogo diversificado de produtos (eletrónicos, moda, equipamentos domésticos e livros), a plataforma recebe diariamente centenas de avaliações de clientes, distribuídas por diferentes regiões geográficas.

Estas avaliações constituem um ativo estratégico de elevado valor, contendo não apenas notas numéricas, mas também comentários em linguagem natural, palavras-chave associadas e, de forma determinante, a **localização geográfica** (coordenadas GeoJSON) do cliente no momento da compra. No entanto, estes dados encontram-se em estado bruto, não estruturado, impossibilitando a sua análise eficiente com sistemas relacionais tradicionais.

A ausência de um pipeline de análise automatizado gera um atraso crítico na deteção de problemas de qualidade e impede a compreensão da **distribuição geográfica da satisfação do cliente**, comprometendo decisões logísticas e de gestão de catálogo.

---

## 2. Problema de Negócio

O desafio central é a **falta de visibilidade em tempo quase real sobre a qualidade do catálogo e a sua expressão territorial**. Os problemas operacionais identificados são:

**2.1 Heterogeneidade dos Dados**
As reviews de eletrónicos contêm atributos técnicos (processador, RAM, autonomia de bateria), enquanto as reviews de moda incidem sobre tamanho, tecido e corte. Um modelo relacional exigiria dezenas de colunas nulas ou tabelas de ligação complexas, resultando em queries lentas e esquemas frágeis.

**2.2 Latência na Deteção de Anomalias**
Se um lote defeituoso de smartphones chega ao mercado, a empresa demora dias a identificar o padrão nas reviews. Esta latência aumenta o volume de devoluções e degrada a reputação da plataforma antes de qualquer ação corretiva ser possível.

**2.3 Ausência de Inteligência Geográfica**
A gestão não dispõe de mecanismos para filtrar a insatisfação por região. Não é possível determinar, por exemplo, se um problema de entrega está concentrado na zona de Faro (apontando para uma falha logística regional) ou distribuído por todo o país (indicando um problema de produto). Esta cegueira geográfica origina ações corretivas desalinhadas com a causa raiz.

**2.4 Análise de Causa Raiz Ineficiente**
Sem correlação automática entre palavras-chave negativas e notas baixas, a equipa de qualidade analisa manualmente centenas de comentários sem uma priorização objetiva.

---

## 3. Proposta de Solução: Pipeline NoSQL + Spatial BI

A solução proposta estrutura-se em três camadas funcionais, combinando uma base de dados NoSQL com capacidades nativas de análise geoespacial.

### Camada A — Ingestão e Armazenamento (MongoDB NoSQL + Geoespacial)

Implementação de uma base de dados orientada a documentos (MongoDB), onde cada review é persistida como um documento auto-contido com esquema dinâmico. A localização do cliente é armazenada em formato **GeoJSON Point** (RFC 7946), habilitando o MongoDB a funcionar simultaneamente como **base de dados espacial** através do índice `2dsphere` e dos operadores `$geoNear`, `$geoWithin` e `$near`.

### Camada B — Processamento Analítico e Espacial (Aggregation Framework)

Utilização do Aggregation Framework do MongoDB para transformar os documentos brutos em métricas estratégicas:
- **Métricas de Sentimento:** Net Sentiment Score (NSS) global e por cidade.
- **Métricas de Qualidade:** Quality Decay Rate e Anomaly Detection por produto.
- **Métricas de Causa Raiz:** Keyword Correlation Index (KCI) — correlação entre palavras-chave e notas baixas.
- **Métricas Espaciais:** NSS por cidade, concentração geográfica de reclamações, raios de influência logística.

### Camada C — Visualização e Suporte à Decisão (Streamlit Dashboard)

Dashboard interativo com quatro visões complementares, incluindo um **mapa geoespacial interativo** que representa o índice de satisfação por cidade portuguesa. O objetivo operacional é que, em menos de 30 segundos, um gestor consiga identificar qual produto apresenta maior taxa de reclamações em Lisboa, ou se um problema de entrega está concentrado na região do Algarve.

---

## 4. Justificativa Técnica: MongoDB como Base de Dados NoSQL e Espacial

### 4.1 Comparativo NoSQL vs. SQL

| Critério | Base de Dados Relacional (SQL) | MongoDB (NoSQL) | Impacto no Projeto |
| :--- | :--- | :--- | :--- |
| **Esquema** | Rígido — requer migração para novos atributos | Dinâmico — novos campos sem alteração de schema | Suporta a variabilidade de atributos por categoria de produto |
| **Escalabilidade** | Vertical (Scale-up — hardware mais caro) | Horizontal (Scale-out — sharding nativo) | Preparado para crescimento para milhões de reviews |
| **Leitura para BI** | JOINs pesados entre tabelas normalizadas | Documentos auto-contidos — leitura em O(1) | Latência mínima no carregamento do dashboard |
| **Modelagem** | Normalização (3NF) — redundância eliminada | Embedding — redundância controlada para performance | Produto e localização incorporados no documento de review |
| **Flexibilidade Operacional** | Alterações de schema exigem migrações críticas | Schema-less — evolução incremental sem downtime | Adicionar novos atributos sem impacto nos documentos existentes |

### 4.2 Comparativo Espacial: PostGIS vs. MongoDB Geospatial

| Critério | PostGIS (extensão PostgreSQL) | MongoDB Geospatial | Impacto no Projeto |
| :--- | :--- | :--- | :--- |
| **Integração** | Sistema separado do BD principal (extensão) | Nativo no mesmo documento e 