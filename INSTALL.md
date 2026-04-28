# 🛠️ Guia de Implementação Técnica: GlobalShop BI

Este guia contém todos os passos necessários para deploying do ecossistema de dados da GlobalShop.

## 📋 Pré-requisitos
- **MongoDB Community Server** (v5.0+) instalado e rodando.
- **MongoDB Compass** (Interface Visual) instalado.

---

## 🚀 Passo a Passo de Execução

### 1. Provisionamento do Banco de Dados
1. Abra o **MongoDB Compass**.
2. Conecte-se ao cluster local (`mongodb://localhost:27017`).
3. Clique em **"Create Database"**:
   - Database Name: `GlobalShop`
   - Collection Name: `reviews`

### 2. Ingestão de Dados (Importação)
1. Com a collection `reviews` aberta, clique na aba **"Add Data"** $\rightarrow$ **"Import JSON or CSV File"**.
2. Selecione o arquivo: `05_projects/current/code/projeto_bd/03_implementacao/dataset_exemplo.json`.
3. Clique em **Import**.

### 3. Lançando a Interface Gráfica (Dashboard BI)
Para rodar a interface visual do projeto, execute os seguintes comandos no seu terminal:

```bash
# Instalar dependências necessárias
pip install streamlit pandas plotly wordcloud matplotlib

# Rodar a aplicação
streamlit run 05_projects/current/code/projeto_bd/app_bi.py
```
O navegador abrirá automaticamente em `http://localhost:8501` com o dashboard interativo.

### 4. Otimização de Performance (Indexação)
Para garantir a velocidade do BI em escala de Big Data, execute estes comandos no **Mongosh** (terminal do Compass):


```javascript
// Índice para acelerar filtros por categoria
db.reviews.createIndex({ "product.category": 1 });

// Índice composto para análise de causa raiz (Sentimento + Keywords)
db.reviews.createIndex({ "sentiment": 1, "content.keywords": 1 });
```

---

## 📊 Execução de Analytics (Pipelines de BI)

Vá na aba **"Aggregations"** do MongoDB Compass e cole as seguintes etapas:

### KPI 1: Ranking de Satisfação (Itens Críticos)
**Objetivo:** Identificar os 10 piores produtos (Nota $\le$ 3.0).
```javascript
[
  { $group: { _id: "$product.name", notaMedia: { $avg: "$rating" }, totalReviews: { $sum: 1 }, marca: { $first: "$product.brand" } } },
  { $match: { notaMedia: { $lte: 3.0 } } },
  { $sort: { notaMedia: 1 } },
  { $limit: 10 }
]
```

### KPI 2: Saúde Emocional por Categoria
**Objetivo:** Matriz de sentimentos por departamento.
```javascript
[
  { $group: { _id: { categoria: "$product.category", sentimento: "$sentiment" }, quantidade: { $sum: 1 } } },
  { $project: { categoria: "$_id.categoria", sentimento: "$_id.sentimento", quantidade: 1, _id: 0 } }
]
```

### KPI 3: Mineração de Causa Raiz (Root Cause)
**Objetivo:** Descobrir POR QUE os clientes estão insatisfeitos.
```javascript
[
  { $match: { sentiment: "Negative" } },
  { $unwind: "$content.keywords" },
  { $group: { _id: "$content.keywords", frequencia: { $sum: 1 } } },
  { $sort: { frequencia: -1 } },
  { $limit: 20 }
]
```
