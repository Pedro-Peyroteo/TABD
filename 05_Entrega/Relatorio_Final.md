# Relatório Técnico Final
## GlobalShop Sentiment Intelligence — Sistema NoSQL + Espacial de BI

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD)
**Ano Letivo:** 2025/2026
**Dataset:** GlobalShop Marketplace — Mercado Português
**Data de Entrega:** Maio de 2026

---

## 1. Resumo Executivo

Este projeto implementa um sistema completo de **Business Intelligence** para a plataforma de comércio eletrónico GlobalShop, que opera em seis cidades de Portugal Continental — Lisboa, Porto, Coimbra, Braga, Faro e Setúbal. O sistema combina uma **base de dados NoSQL** (MongoDB com schema dinâmico) com capacidades de **base de dados espacial** (índice `2dsphere` + GeoJSON RFC 7946), transformando avaliações de clientes em decisões estratégicas em tempo quase real.

O sistema resolve três problemas críticos identificados na GlobalShop:

1. **Latência de deteção de problemas de qualidade:** reduzida de dias para minutos, através de Anomaly Detection automático com Quality Decay Rate.
2. **Ausência de inteligência geográfica:** a empresa passa a visualizar onde (cidade/região de Portugal) a insatisfação se concentra, através do Geographic Sentiment Index em mapa interativo.
3. **Dificuldade na identificação de causa raiz:** o sistema isola automaticamente se um problema é de produto (afeta todo o país), de hardware (KCI de keywords técnicas elevado) ou logístico (concentrado numa região específica).

---

## 2. Objetivos e Requisitos

### 2.1 Objetivos Técnicos

- Implementar uma base de dados NoSQL com schema dinâmico, capaz de suportar reviews com atributos heterogéneos por categoria de produto.
- Integrar suporte nativo a dados geoespaciais através do padrão GeoJSON e do índice `2dsphere` do MongoDB.
- Construir pipelines de agregação para extração de KPIs de sentimento, qualidade temporal e análise espacial.
- Desenvolver um dashboard interativo com quatro visões complementares orientadas a diferentes perfis de utilizador.

### 2.2 Requisitos Funcionais

| ID | Requisito | Status |
| :--- | :--- | :--- |
| RF01 | Armazenar reviews com localização geográfica GeoJSON de cidades portuguesas | ✅ Implementado |
| RF02 | Calcular Net Sentiment Score (NSS) global e por cidade | ✅ Implementado |
| RF03 | Detetar decaimento de qualidade mensal (Quality Decay Rate) | ✅ Implementado |
| RF04 | Identificar anomalias de rating por produto | ✅ Implementado |
| RF05 | Executar queries geoespaciais (raio de Lisboa, NSS por cidade) | ✅ Implementado |
| RF06 | Visualizar mapa interativo de satisfação por cidade portuguesa | ✅ Implementado |
| RF07 | Analisar causa raiz via keywords negativas (Keyword Correlation Index) | ✅ Implementado |
| RF08 | Filtrar dados por categoria, membership e localização | ✅ Implementado |

---

## 3. Arquitetura da Solução

### 3.1 Visão Geral

```
┌──────────────────────────────────────────────────────────────────┐
│  FONTE DE DADOS: Reviews de Clientes (25 documentos de demo)     │
│  Cidades: Lisboa, Porto, Coimbra, Braga, Faro, Setúbal           │
│           — coordenadas GeoJSON reais de Portugal Continental    │
└─────────────────────────┬────────────────────────────────────────┘
                          │ Ingestão (JSON Import / pymongo)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  CAMADA DE DADOS: MongoDB                                        │
│  ├─ Coleção: reviews                                             │
│  ├─ Índice: product.category (simples)                           │
│  ├─ Índice: sentiment + keywords (composto)                      │
│  ├─ Índice: timestamp (temporal)                                 │
│  └─ Índice: customer.location.coordinates (2dsphere) ★          │
│     ★ Habilita MongoDB como Base de Dados Espacial               │
└─────────────────────────┬────────────────────────────────────────┘
                          │ Aggregation Framework
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  CAMADA DE PROCESSAMENTO: Pipelines de Agregação                 │
│  ├─ Analíticas: NSS, ranking de produtos, performance de marca   │
│  ├─ Temporal: Quality Decay Rate, Anomaly Detection              │
│  ├─ NLP: Root Cause Analysis, Keyword Correlation Index          │
│  └─ Espacial: $geoNear, NSS por cidade, KCI geográfico           │
└─────────────────────────┬────────────────────────────────────────┘
                          │ pandas + plotly
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  CAMADA DE VISUALIZAÇÃO: Streamlit Dashboard (4 abas)            │
│  ├─ Tab 1: Visão Executiva (NSS, QDR, tendência mensal)          │
│  ├─ Tab 2: Análise Tática (categorias, marcas, produtos)         │
│  ├─ Tab 3: Análise Operacional (anomalias, keywords, word cloud) │
│  └─ Tab 4: Análise Geoespacial (mapa, NSS por cidade) ★          │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Base de Dados NoSQL — MongoDB

O MongoDB foi escolhido pela sua capacidade de armazenar documentos com schema dinâmico, ideal para reviews cujos atributos variam por categoria (eletrónicos vs. moda vs. casa). A estratégia de **Embedding** consolida produto, cliente e métricas num único documento, eliminando JOINs e proporcionando leitura em $\mathcal{O}(1)$.

### 3.3 Base de Dados Espacial — MongoDB Geospatial

A localização de cada cliente é armazenada como um **GeoJSON Point** (RFC 7946), com coordenadas reais das cidades portuguesas. O índice `2dsphere` transforma o MongoDB numa base de dados espacial nativa, sem necessidade de sistemas externos como o PostGIS. As queries espaciais e analíticas coexistem na mesma pipeline de agregação.

**Vantagens sobre PostGIS:**
- Uma única infraestrutura — sem extensão adicional nem sistema separado.
- GeoJSON é um padrão aberto interoperável com APIs REST e frontends modernos.
- O índice `2dsphere` utiliza geometria esférica real (fórmula de Haversine), garantindo distâncias precisas à superfície da Terra.

---

## 4. Modelagem de Dados

### 4.1 Schema do Documento (JSON/BSON + GeoJSON)

```json
{
  "review_id": "R016",
  "product": {
    "product_id": "P101",
    "name": "Smartphone X1",
    "category": "Eletrónicos",
    "brand": "TechCorp"
  },
  "customer": {
    "customer_id": "C516",
    "name": "Nuno Ferreira",
    "location": {
      "city": "Braga",
      "country": "Portugal",
      "coordinates": { "type": "Point", "coordinates": [-8.4261, 41.5454] }
    },
    "membership": "Silver"
  },
  "metrics": { "rating": 2, "sentiment": "Negative", "verified_purchase": true },
  "content": {
    "comment": "A bateria começa a sobreaquecer. Parece defeito de lote!",
    "keywords": ["bateria", "sobreaquecimento", "defeito"],
    "language": "pt"
  },
  "metadata": { "timestamp": "2026-04-02T10:00:00Z", "device": "Mobile" }
}
```

### 4.2 Estratégia de Indexação

| Índice | Tipo | Campo | Complexidade | Operadores |
| :--- | :--- | :--- | :--- | :--- |
| Categoria | Simples | `product.category: 1` | $\mathcal{O}(\log n)$ | `$match`, `$group` |
| Causa Raiz | Composto | `sentiment` + `keywords` | $\mathcal{O}(\log n + k)$ | `$match` seletivo |
| Temporal | Simples | `metadata.timestamp: -1` | $\mathcal{O}(\log n)$ | Range queries |
| **Espacial** | **2dsphere** | `location.coordinates` | $\mathcal{O}(\log n)$ | `$near`, `$geoNear`, `$geoWithin` |

---

## 5. Implementação

### 5.1 Dataset de Demonstração

O dataset contém **25 documentos** representando reviews de 7 produtos em 6 cidades portuguesas (Lisboa, Porto, Coimbra, Braga, Faro e Setúbal), cobrindo o período de Janeiro a Maio de 2026. As coordenadas GeoJSON são reais e correspondem aos centros geográficos de cada cidade.

O Smartphone X1 (TechCorp) apresenta um padrão de decaimento deliberado para validar o Anomaly Detection: rating Jan 5.0 → Fev 4.0 → Mar 3.0 → Abr 1.5 → Mai 1.0, com keywords "sobreaquecimento", "defeito" e "bateria" a dominar o período de anomalia.

### 5.2 Pipelines de Agregação MongoDB

Foram implementadas **9 pipelines** documentadas em `03_Implementacao/Queries_BI.md`:

- 5 pipelines analíticas: ranking de produtos, polaridade por categoria, root cause analysis, quality decay rate e anomaly detection.
- 4 pipelines geoespaciais: raio de proximidade a Lisboa, NSS por cidade, concentração regional de keywords e Keyword Correlation Index geoespacial.

### 5.3 Dashboard Streamlit

O dashboard `app_bi.py` implementa **4 abas interativas** com filtros dinâmicos globais (categoria, membership, cidade):

**Tab 1 — Visão Executiva:** 5 KPI cards (NSS, total reviews, nota média, compras verificadas, Quality Decay Rate), gráfico de rosca de distribuição de sentimentos e linha de tendência mensal com limite crítico (3.0).

**Tab 2 — Análise Tática:** Histograma agrupado de sentimentos por categoria, ranking dos 10 produtos com nota mais baixa e performance por marca com NSS como escala de cor.

**Tab 3 — Análise Operacional:** Word cloud de keywords negativas (colormap Reds), top 10 keywords por frequência e tabela de Anomaly Detection com alertas 🔴/🟡/🟢.

**Tab 4 — Análise Geoespacial:** Mapa interativo scatter_mapbox (OpenStreetMap) com bolhas por cidade portuguesa (tamanho = volume, cor = NSS), NSS por cidade em barras, volume e nota média por cidade e tabela de resumo regional.

---

## 6. Resultados e Validação

### 6.1 Caso de Uso: Deteção de Lote Defeituoso

O Smartphone X1 (TechCorp) apresentou o seguinte padrão nos dados de demonstração:

| Mês | Nota Média | Sentimento Dominante | Alerta |
| :--- | :--- | :--- | :--- |
| Janeiro 2026 | 5.0 | Positive | 🟢 Estável |
| Fevereiro 2026 | 4.0 | Positive | 🟢 Estável |
| Março 2026 | 3.0 | Neutral | 🟡 Atenção |
| Abril 2026 | 1.5 | Negative | 🔴 Crítico (-50%) |
| Maio 2026 | 1.0 | Negative | 🔴 Crítico (-33%) |

As keywords "sobreaquecimento" e "defeito" apresentam KCI > 90%, confirmando um problema de hardware no lote de Abril — não uma falha logística.

### 6.2 Caso de Uso: Análise Geoespacial em Portugal

O dashboard geoespacial permite identificar imediatamente:
- Cidades com NSS positivo (ex: Porto, Coimbra) → satisfação com produto e entrega na região Norte e Centro.
- Cidades com NSS negativo (ex: Braga, Faro) → concentração de reviews do Smartphone X1 defeituoso, distribuído por rotas de entrega específicas.
- Concentração geográfica da keyword "atraso" em Faro → possível falha do parceiro logístico do Algarve, independente do defeito de hardware.

---

## 7. Conclusões

### 7.1 Objetivos Alcançados

- ✅ Base de dados NoSQL com schema dinâmico para reviews heterogéneas por categoria.
- ✅ Base de dados espacial nativa via índice `2dsphere` com coordenadas GeoJSON de Portugal.
- ✅ Pipeline completa: ingestão → aggregation → visualização.
- ✅ Dashboard com 4 visões orientadas a diferentes perfis de gestão.
- ✅ 5 KPIs implementados: NSS, Quality Decay Rate, Anomaly Detection, KCI e GSI.
- ✅ 9 pipelines MongoDB documentadas (5 analíticas + 4 geoespaciais).

### 7.2 Valor Demonstrado

O sistema transforma a GlobalShop de uma empresa reativa — que deteta problemas após viralização nas redes sociais — para uma empresa proativa, capaz de identificar anomalias em minutos com localização geográfica precisa da causa. A integração da dimensão espacial acrescenta uma camada de inteligência que distingue problemas de produto (afetam todas as cidades de Portugal) de problemas logísticos (geograficamente concentrados numa região).

### 7.3 Trabalhos Futuros

- Integração com API REST para ingestão de reviews em tempo real (Atlas Data API ou Kafka).
- Substituição da categorização manual de sentimentos por modelos de NLP (spaCy com modelos em português).
- Implementação de alertas automáticos por email/webhook quando QDR < -30%.
- Expansão da cobertura geográfica a ilhas (Açores, Madeira) com geometrias `MultiPoint`.
- Integração com Power BI Service para camada Gold de um pipeline ELT empresarial.

---

## 8. Referências

- MongoDB Documentation — Geospatial Queries: https://www.mongodb.com/docs/manual/geospatial-queries/
- GeoJSON Specification (RFC 7946): https://tools.ietf.org/html/rfc7946
- MongoDB Aggregation Framework: https://www.mongodb.com/docs/manual/aggregation/
- Streamlit Documentation: https://docs.streamlit.io/
- Plotly Scatter Mapbox: https://plotly.com/python/scattermapbox/
- MongoDB Index Types — 2dsphere: https://www.mongodb.com/docs/manual/core/2dsphere/
