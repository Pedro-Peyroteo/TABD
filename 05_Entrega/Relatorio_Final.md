# Relatório Técnico Final
## GlobalShop Sentiment Intelligence — Sistema NoSQL + Espacial de BI

**Projeto:** TABD — Tecnologias e Aplicações de Bases de Dados  
**Dataset:** GlobalShop Marketplace (fictício, mercados PALOP)  
**Data de Entrega:** Maio de 2026

---

## 1. Resumo Executivo

Este projeto implementa um sistema completo de **Business Intelligence** para a plataforma de e-commerce GlobalShop, combinando uma **base de dados NoSQL** (MongoDB) com capacidades de **base de dados espacial** (índice `2dsphere` + GeoJSON) para transformar avaliações de clientes em decisões estratégicas em tempo quase real.

O sistema resolve três problemas críticos identificados na GlobalShop:
1. **Latência de deteção de problemas:** reduzida de dias para minutos.
2. **Cegueira geográfica:** a empresa agora visualiza onde (cidade/região) a insatisfação se concentra.
3. **Falta de causa raiz:** o sistema identifica automaticamente se o problema é de produto, qualidade ou logística.

---

## 2. Objetivos e Requisitos

### 2.1 Objetivos Técnicos
- Implementar uma base de dados NoSQL com esquema dinâmico para suportar reviews heterogéneas.
- Integrar suporte a dados espaciais através do padrão GeoJSON e índice `2dsphere` do MongoDB.
- Construir um pipeline de agregação para extração de KPIs de sentimento, qualidade e anomalias.
- Desenvolver um dashboard interativo com visualizações analíticas e geoespaciais.

### 2.2 Requisitos Funcionais
| ID | Requisito | Status |
| :--- | :--- | :--- |
| RF01 | Armazenar reviews com localização geográfica (GeoJSON) | ✅ Implementado |
| RF02 | Calcular Net Sentiment Score (NSS) global e por cidade | ✅ Implementado |
| RF03 | Detetar decaimento de qualidade (Quality Decay Rate) | ✅ Implementado |
| RF04 | Identificar anomalias de rating por produto | ✅ Implementado |
| RF05 | Executar queries geoespaciais (raio, NSS por cidade) | ✅ Implementado |
| RF06 | Visualizar mapa interativo de satisfação por cidade | ✅ Implementado |
| RF07 | Analisar causa raiz via keywords negativas (KCI) | ✅ Implementado |
| RF08 | Filtrar dados por categoria, membership e localização | ✅ Implementado |

---

## 3. Arquitetura da Solução

### 3.1 Visão Geral

```
┌──────────────────────────────────────────────────────────────┐
│  FONTE DE DADOS: Reviews de Clientes (25 registos demo)      │
│  Cidades: Luanda, Benguela, Huambo, Lubango, Malanje,        │
│           Cabinda — coordenadas GeoJSON reais de Angola      │
└───────────────────────┬──────────────────────────────────────┘
                        │ Ingestão (JSON Import / pymongo)
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  CAMADA DE DADOS: MongoDB                                    │
│  ├─ Coleção: reviews                                         │
│  ├─ Índice: product.category (simples)                       │
│  ├─ Índice: sentiment + keywords (composto)                  │
│  ├─ Índice: timestamp (temporal)                             │
│  └─ Índice: customer.location.coordinates (2dsphere) ★      │
│     ★ Habilita MongoDB como Base de Dados Espacial           │
└───────────────────────┬──────────────────────────────────────┘
                        │ Aggregation Framework
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  CAMADA DE PROCESSAMENTO: Pipelines de Agregação             │
│  ├─ KPI Analytics: NSS, rating ranking, brand performance    │
│  ├─ Temporal: Quality Decay Rate, Anomaly Detection          │
│  ├─ NLP: Root Cause Analysis, Keyword Correlation Index      │
│  └─ Spatial: $geoNear, NSS por cidade, KCI geográfico        │
└───────────────────────┬──────────────────────────────────────┘
                        │ pandas + plotly
                        ▼
┌──────────────────────────────────────────────────────────────┐
│  CAMADA DE VISUALIZAÇÃO: Streamlit Dashboard (4 abas)        │
│  ├─ Tab 1: Visão Executiva (NSS, QDR, tendência mensal)      │
│  ├─ Tab 2: Análise Tática (categorias, marcas, produtos)     │
│  ├─ Tab 3: Análise Operacional (anomalias, keywords)         │
│  └─ Tab 4: Análise Geoespacial (mapa, NSS por cidade) ★      │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Base de Dados NoSQL — MongoDB
O MongoDB foi escolhido pela sua capacidade de armazenar documentos com esquema dinâmico, ideal para reviews que diferem em atributos por categoria (eletrónicos vs. moda). A estratégia de **Embedding** consolida produto, cliente e métricas num único documento, eliminando JOINs e reduzindo a latência de leitura para $\mathcal{O}(1)$.

### 3.3 Base de Dados Espacial — MongoDB Geospatial
A localização de cada cliente é armazenada como um **GeoJSON Point** (padrão RFC 7946), com longitude e latitude das cidades angolanas. O índice `2dsphere` transforma o MongoDB numa base de dados espacial sem necessidade de sistemas externos como PostGIS, mantendo as queries espaciais e analíticas na mesma pipeline de agregação.

**Vantagens desta abordagem sobre PostGIS:**
- Uma única infraestrutura (sem sistema adicional).
- GeoJSON é interoperável com APIs REST modernas.
- O índice `2dsphere` usa geometria esférica real (haversine), garantindo distâncias precisas na superfície terrestre.

---

## 4. Modelagem de Dados

### 4.1 Schema do Documento (JSON/BSON + GeoJSON)
```json
{
  "review_id": "R016",
  "product": { "product_id": "P101", "name": "Smartphone X1", "category": "Eletrónicos", "brand": "TechCorp" },
  "customer": {
    "customer_id": "C516", "name": "Nuno Ferreira",
    "location": {
      "city": "Lubango", "country": "Angola",
      "coordinates": { "type": "Point", "coordinates": [13.4920, -14.9177] }
    },
    "membership": "Silver"
  },
  "metrics": { "rating": 2, "sentiment": "Negative", "verified_purchase": true },
  "content": { "comment": "A bateria começa a sobreaquecer. Parece defeito de lote!", "keywords": ["bateria", "sobreaquecimento", "defeito"], "language": "pt" },
  "metadata": { "timestamp": "2026-04-02T10:00:00Z", "device": "Mobile" }
}
```

### 4.2 Estratégia de Indexação
| Índice | Tipo | Campo | Complexidade |
| :--- | :--- | :--- | :--- |
| Categoria | Simples | `product.category: 1` | $\mathcal{O}(\log n)$ |
| Causa Raiz | Composto | `metrics.sentiment + content.keywords` | $\mathcal{O}(\log n + k)$ |
| Temporal | Simples | `metadata.timestamp: -1` | $\mathcal{O}(\log n)$ |
| **Espacial** | **2dsphere** | `customer.location.coordinates` | $\mathcal{O}(\log n)$ |

---

## 5. Implementação

### 5.1 Dataset
O dataset contém **25 documentos** representando reviews de 6 produtos em 6 cidades de Angola (Janeiro a Maio de 2026), com coordenadas GeoJSON reais. O Smartphone X1 apresenta um padrão deliberado de decaimento de qualidade (rating médio: Jan 5.0 → Abr 1.5 → Mai 1.0) para validar a funcionalidade de anomaly detection.

### 5.2 Pipelines de Agregação MongoDB
Foram implementadas 9 pipelines documentadas em `03_Implementacao/Queries_BI.md`:
- 5 pipelines analíticas (NSS, ranking, causa raiz, decay rate, anomaly detection)
- 4 pipelines geoespaciais (raio, NSS por cidade, KCI geográfico, keyword regional)

### 5.3 Dashboard Streamlit
O dashboard `app_bi.py` implementa **4 abas interativas** com filtros dinâmicos por categoria, membership e localização:

1. **Visão Executiva:** 5 KPI cards (NSS, total reviews, nota média, verificadas, Quality Decay Rate), gráfico de rosca e linha de tendência mensal.
2. **Análise Tática:** Histograma de sentimentos por categoria, top produtos críticos e performance por marca com NSS como escala de cor.
3. **Análise Operacional:** Word cloud de keywords negativas, top 10 keywords por frequência, tabela de anomaly detection com alertas coloridos (🔴/🟡/🟢).
4. **Análise Geoespacial:** Mapa interativo (scatter_mapbox OpenStreetMap) com bolhas por cidade, NSS por cidade em barras, volume e nota média por cidade, tabela de resumo regional.

---

## 6. Resultados e Validação

### 6.1 Caso de Uso: Deteção de Lote Defeituoso
O Smartphone X1 (TechCorp) apresentou o seguinte padrão nos dados de demonstração:

| Mês | Nota Média | Sentimento Dominante | Alerta |
| :--- | :--- | :--- | :--- |
| Janeiro 2026 | 5.0 | Positive | 🟢 Normal |
| Fevereiro 2026 | 4.0 | Positive | 🟢 Normal |
| Março 2026 | 3.0 | Neutral | 🟡 Atenção |
| Abril 2026 | 1.5 | Negative | 🔴 Crítico (-50%) |
| Maio 2026 | 1.0 | Negative | 🔴 Crítico (-33%) |

A keyword "sobreaquecimento" e "defeito" aparecem como causa raiz, confirmando um problema de hardware no lote de Abril.

### 6.2 Caso de Uso: Análise Geoespacial
O dashboard geoespacial permite identificar que:
- Cidades com NSS positivo → satisfação com produto e entrega.
- Cidades com NSS negativo → potencial problema logístico regional ou lote defeituoso distribuído nessa área.
- A concentração geográfica de keywords como "atraso" permite isolar falhas do transportador regional.

---

## 7. Conclusões

### 7.1 Objetivos Alcançados
- ✅ Sistema NoSQL com esquema dinâmico para reviews heterogéneas.
- ✅ Base de dados espacial nativa via índice `2dsphere` do MongoDB.
- ✅ Pipeline completa: ingestão → agregação → visualização.
- ✅ Dashboard com 4 visões: executiva, tática, operacional e geoespacial.
- ✅ Métricas implementadas: NSS, Quality Decay Rate, Anomaly Detection, KCI, GSI.

### 7.2 Valor Demonstrado
O sistema transforma a GlobalShop de uma empresa reativa (deteta problemas após viralização) para uma empresa proativa (deteta anomalias em horas, com localização geográfica da causa). A integração da dimensão espacial acrescenta uma camada de inteligência que permite diferenciar problemas de produto (afetam todas as cidades) de problemas logísticos (concentrados geograficamente).

### 7.3 Trabalhos Futuros
- Integração com API REST para ingestão de reviews em tempo real.
- Análise de sentimento com NLP (spaCy/NLTK) para substituir a categorização manual.
- Implementação de alertas automáticos por email/SMS quando QDR < -30%.
- Expansão para outros mercados PALOP (Moçambique, Cabo Verde, São Tomé).
- Integração com Power BI para camada Gold do ELT.

---

## 8. Referências Técnicas

- MongoDB Documentation — Geospatial Queries: https://www.mongodb.com/docs/manual/geospatial-queries/
- GeoJSON Specification (RFC 7946): https://tools.ietf.org/html/rfc7946
- MongoDB Aggregation Framework: https://www.mongodb.com/docs/manual/aggregation/
- Streamlit Documentation: https://docs.streamlit.io/
- Plotly Scatter Mapbox: https://plotly.com/python/scattermapbox/
