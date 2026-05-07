# Guia de Instalação e Execução: GlobalShop BI

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD) | **Ano Letivo:** 2025/2026

Este guia detalha todos os passos necessários para executar o ecossistema de dados da GlobalShop Portugal, composto por uma base de dados **NoSQL** (MongoDB) com suporte a **dados espaciais** (GeoJSON + índice `2dsphere`) e um dashboard interativo Streamlit.

---

## Pré-requisitos

- **Python 3.10+** instalado e no PATH do sistema.
- **MongoDB Community Server 6.0+** instalado e em execução na porta padrão `27017` (opcional — o dashboard funciona em modo JSON sem MongoDB).
- **MongoDB Compass** (interface visual opcional, recomendada para executar as queries de `Queries_BI.md`).

---

## 1. Instalação das Dependências Python

Na raiz do repositório (`TABD/`), executar:

```bash
pip install -r requirements.txt
```

O ficheiro `requirements.txt` instala: `streamlit`, `pandas`, `plotly`, `wordcloud`, `matplotlib` e `pymongo`.

---

## 2. Lançar o Dashboard BI

Na raiz do repositório:

```bash
streamlit run app_bi.py
```

O browser abrirá automaticamente em `http://localhost:8501` com o dashboard interativo de 4 abas. O dashboard carrega os dados diretamente de `03_Implementacao/dataset_exemplo.json` — **não requer MongoDB** para demonstração.

---

## 3. Configuração do MongoDB (Base de Dados NoSQL + Espacial)

### 3.1 Criar a Base de Dados e Coleção

1. Abrir o **MongoDB Compass** e conectar a `mongodb://localhost:27017`.
2. Clicar em **"Create Database"**:
   - Database Name: `GlobalShop`
   - Collection Name: `reviews`

### 3.2 Importar o Dataset

1. Com a coleção `reviews` aberta, clicar em **"Add Data"** → **"Import JSON or CSV File"**.
2. Selecionar o ficheiro: `03_Implementacao/dataset_exemplo.json`
3. Clicar em **Import**.

O dataset contém 25 documentos com coordenadas GeoJSON reais de seis cidades portuguesas (Lisboa, Porto, Coimbra, Braga, Faro e Setúbal).

### 3.3 Criar Índices de Performance e Espacial

No **Mongosh** (terminal integrado do Compass), executar:

```javascript
// 1. Índice para agrupamentos por categoria
db.reviews.createIndex({ "product.category": 1 });

// 2. Índice composto para análise de causa raiz
db.reviews.createIndex({ "metrics.sentiment": 1, "content.keywords": 1 });

// 3. Índice temporal para cálculo de Quality Decay Rate
db.reviews.createIndex({ "metadata.timestamp": -1 });

// 4. Índice 2dsphere — transforma o MongoDB em Base de Dados Espacial
//    Habilita $geoNear, $geoWithin e $near sobre os campos GeoJSON Point
db.reviews.createIndex({ "customer.location.coordinates": "2dsphere" });
```

> O índice `2dsphere` é o elemento que habilita as queries geoespaciais descritas em `03_Implementacao/Queries_BI.md`, como "todas as reviews num raio de 100 km de Lisboa".

### 3.4 Verificar a Importação

```javascript
// Deve retornar 25
db.reviews.countDocuments()

// Verificar a estrutura GeoJSON de um documento
db.reviews.findOne({}, { "customer.location": 1, "product.name": 1 })
```

---

## 4. Executar as Queries de Analytics

No **MongoDB Compass**, aceder à aba **"Aggregations"** e executar as 9 pipelines documentadas em `03_Implementacao/Queries_BI.md`:

**Pipelines Analíticas:**
- KPI 1 — Ranking de satisfação (produtos com nota ≤ 3.0)
- KPI 2 — Análise de polaridade por categoria
- KPI 3 — Root Cause Analysis (keywords negativas e KCI)
- KPI 4 — Quality Decay Rate mensal por produto
- KPI 5 — Anomaly Detection (quedas ≥ 30% de rating)

**Pipelines Geoespaciais:**
- KPI Geo 1 — Reviews num raio de 100 km de Lisboa
- KPI Geo 2 — Net Sentiment Score (NSS) por cidade portuguesa
- KPI Geo 3 — Concentração regional de keywords de problema
- KPI Geo 4 — Keyword Correlation Index (KCI) geoespacial

---

## 5. Estrutura do Repositório

```
TABD/
├── app_bi.py                        # Dashboard Streamlit (4 abas interativas)
├── requirements.txt                 # Dependências Python com versões mínimas
├── INSTALL.md                       # Este guia
├── README.md                        # Visão geral do projeto
├── 01_Definicao/
│   └── Definicao_Projeto.md         # Problema de negócio + justificativa NoSQL + Espacial
├── 02_Modelagem/
│   └── Modelagem_Dados.md           # Schema GeoJSON + coordenadas de Portugal + indexação
├── 03_Implementacao/
│   ├── dataset_exemplo.json         # 25 documentos com GeoJSON (Portugal Continental)
│   └── Queries_BI.md                # 9 pipelines MongoDB (analíticas + geoespaciais)
├── 04_BI_Analysis/
│   └── Planeamento_BI.md            # KPIs, especificações do dashboard, arquitetura
└── 05_Entrega/
    ├── Relatorio_Final.md           # Relatório técnico final consolidado
    └── Guiao_Apresentacao.md        # Guião detalhado para a apresentação oral
```

---

## 6. Resolução de Problemas Comuns

| Problema | Causa Provável | Solução |
| :--- | :--- | :--- |
| `ModuleNotFoundError: wordcloud` | Dependência não instalada | `pip install wordcloud` |
| Dashboard não abre no browser | Streamlit a usar porta diferente | Aceder manualmente a `http://localhost:8501` |
| Erro ao importar JSON no Compass | Ficheiro com encoding incorreto | Verificar que o ficheiro está em UTF-8 |
| Query `$nearSphere` falha | Índice `2dsphere` não criado | Executar o `createIndex` da secção 3.3 |
| `UserWarning: timezone` no terminal | Timestamps com timezone UTC | Aviso não-crítico — não afeta o funcionamento |
