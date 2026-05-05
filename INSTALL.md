# Guia de Implementação Técnica: GlobalShop BI

Este guia contém todos os passos necessários para executar o ecossistema de dados da GlobalShop, composto por uma base de dados **NoSQL** (MongoDB) com suporte a **dados espaciais** (GeoJSON + índice `2dsphere`) e um dashboard interativo Streamlit.

---

## Pré-requisitos

- **Python 3.10+** instalado.
- **MongoDB Community Server (v6.0+)** instalado e em execução (opcional — o dashboard pode correr em modo JSON).
- **MongoDB Compass** (interface visual) instalado (opcional).

---

## 1. Instalação das Dependências Python

Na raiz do repositório (`TABD/`), execute:

```bash
pip install -r requirements.txt
```

O ficheiro `requirements.txt` instala: `streamlit`, `pandas`, `plotly`, `wordcloud`, `matplotlib`, `pymongo`.

---

## 2. Lançar o Dashboard BI

Na raiz do repositório:

```bash
streamlit run app_bi.py
```

O browser abrirá automaticamente em `http://localhost:8501` com o dashboard interativo de 4 abas.

---

## 3. Configuração do MongoDB (Base de Dados NoSQL + Espacial)

### 3.1 Criar a Base de Dados e Coleção

1. Abra o **MongoDB Compass** e conecte-se a `mongodb://localhost:27017`.
2. Clique em **"Create Database"**:
   - Database Name: `GlobalShop`
   - Collection Name: `reviews`

### 3.2 Importar o Dataset

1. Com a coleção `reviews` aberta, clique em **"Add Data"** → **"Import JSON or CSV File"**.
2. Selecione o ficheiro: `03_Implementacao/dataset_exemplo.json`
3. Clique em **Import**.

### 3.3 Criar Índices de Performance e Espacial

No **Mongosh** (terminal integrado do Compass), execute:

```javascript
// Índice para agrupamentos por categoria
db.reviews.createIndex({ "product.category": 1 });

// Índice composto para análise de causa raiz
db.reviews.createIndex({ "metrics.sentiment": 1, "content.keywords": 1 });

// Índice temporal para cálculo de Quality Decay Rate
db.reviews.createIndex({ "metadata.timestamp": -1 });

// Índice 2dsphere — transforma MongoDB em Base de Dados Espacial
// Habilita $geoNear, $geoWithin, $near sobre GeoJSON Points
db.reviews.createIndex({ "customer.location.coordinates": "2dsphere" });
```

> O índice `2dsphere` é o elemento que habilita as **queries geoespaciais** descritas em `03_Implementacao/Queries_BI.md`, como "todas as reviews num raio de 200 km de Luanda".

### 3.4 Verificar o Schema dos Documentos

Após a importação, confirme que os documentos têm a estrutura correta:

```javascript
db.reviews.findOne()
// Deve mostrar campos: review_id, product{}, customer{location{coordinates{type, coordinates[]}}}, metrics{}, content{keywords[]}, metadata{}
```

---

## 4. Execução de Analytics no MongoDB Compass

Vá à aba **"Aggregations"** do Compass e consulte as pipelines em `03_Implementacao/Queries_BI.md` para executar:

- **KPI 1:** Ranking de satisfação (produtos críticos com nota ≤ 3.0)
- **KPI 2:** Análise de polaridade por categoria
- **KPI 3:** Root Cause Analysis (keywords negativas)
- **KPI 4:** Quality Decay Rate mensal por produto
- **KPI 5:** Anomaly Detection (quedas abruptas de rating)
- **KPI Geo 1:** Reviews num raio de 200 km de Luanda
- **KPI Geo 2:** Net Sentiment Score (NSS) por cidade
- **KPI Geo 3:** Concentração regional de keywords de problema
- **KPI Geo 4:** Keyword Correlation Index (KCI)

---

## 5. Estrutura do Repositório

```
TABD/
├── app_bi.py                          # Dashboard Streamlit (4 abas)
├── requirements.txt                   # Dependências Python com versões
├── .gitignore                         # Ficheiros ignorados pelo Git
├── README.md                          # Visão geral do projeto
├── INSTALL.md                         # Este guia
├── 01_Definicao/
│   └── Definicao_Projeto.md           # Problema de negócio + justificativa NoSQL + Espacial
├── 02_Modelagem/
│   └── Modelagem_Dados.md             # Schema GeoJSON + estratégia de indexação
├── 03_Implementacao/
│   ├── dataset_exemplo.json           # 25 registos com GeoJSON (Angola)
│   └── Queries_BI.md                  # Pipelines MongoDB (analíticas + espaciais)
├── 04_BI_Analysis/
│   └── Planeamento_BI.md              # KPIs, especificações do dashboard, arquitetura
└── 05_Entrega/
    └── Relatorio_Final.md             # Relatório técnico consolidado
```
