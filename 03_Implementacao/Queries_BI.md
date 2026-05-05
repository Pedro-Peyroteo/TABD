# Implementação Técnica: NoSQL + Spatial Data Pipeline

Nesta secção, detalhamos a implementação do pipeline de processamento de dados. O coração do sistema é o **Aggregation Framework** do MongoDB, que funciona como uma pipeline de processamento onde cada etapa transforma os documentos. A integração com o índice `2dsphere` adiciona a dimensão geoespacial ao pipeline.

> **Nota sobre campos:** O schema utilizado segue a estrutura aninhada definida em `02_Modelagem/Modelagem_Dados.md`. Os campos de rating estão em `metrics.rating`, sentiment em `metrics.sentiment`, keywords em `content.keywords`, e as coordenadas em `customer.location.coordinates`.

---

## 1. Configuração Inicial de Índices

Antes de executar as queries, criar os índices de performance no **Mongosh**:

```javascript
// Índice de categoria para agrupamentos
db.reviews.createIndex({ "product.category": 1 });

// Índice composto para análise de causa raiz
db.reviews.createIndex({ "metrics.sentiment": 1, "content.keywords": 1 });

// Índice temporal para análises de decaimento
db.reviews.createIndex({ "metadata.timestamp": -1 });

// Índice espacial 2dsphere — transforma MongoDB em BD Espacial
db.reviews.createIndex({ "customer.location.coordinates": "2dsphere" });
```

---

## 2. Queries de Business Intelligence

### 2.1 KPI: Ranking de Satisfação (Detecção de Itens Críticos)
Identifica os 10 produtos com pior performance média.

```javascript
db.reviews.aggregate([
  {
    $group: {
      _id: "$product.name",
      notaMedia: { $avg: "$metrics.rating" },
      totalReviews: { $sum: 1 },
      marca: { $first: "$product.brand" }
    }
  },
  { $match: { notaMedia: { $lte: 3.0 } } },
  { $sort: { notaMedia: 1 } },
  { $limit: 10 }
])
```

**Análise Técnica:**
- **$group**: Colapsa todos os documentos por nome de produto, calculando a média aritmética da nota (campo `metrics.rating`).
- **$match**: Filtra apenas a "cauda inferior" da distribuição (notas ≤ 3).
- **Complexidade**: $\mathcal{O}(n)$ onde $n$ é o número de reviews.

---

### 2.2 KPI: Análise de Polaridade por Categoria
Cria uma matriz bidimensional de sentimentos por departamento.

```javascript
db.reviews.aggregate([
  {
    $group: {
      _id: {
        categoria: "$product.category",
        sentimento: "$metrics.sentiment"
      },
      quantidade: { $sum: 1 }
    }
  },
  {
    $project: {
      categoria: "$_id.categoria",
      sentimento: "$_id.sentimento",
      quantidade: 1,
      _id: 0
    }
  },
  { $sort: { categoria: 1 } }
])
```

---

### 2.3 KPI: Mineração de Texto para Causa Raiz (Root Cause Analysis)
Descobre as palavras-chave mais frequentes em reviews negativas.

```javascript
db.reviews.aggregate([
  { $match: { "metrics.sentiment": "Negative" } },
  { $unwind: "$content.keywords" },
  {
    $group: {
      _id: "$content.keywords",
      frequencia: { $sum: 1 }
    }
  },
  { $sort: { frequencia: -1 } },
  { $limit: 20 }
])
```

**Análise Técnica:**
- **$unwind**: Desconstrói o array `content.keywords`, criando um documento separado para cada palavra-chave. Se uma review tem 3 keywords, o `$unwind` gera 3 documentos temporários.
- Permite isolar se a insatisfação é causada por "Logística" (ex: *entrega*, *atraso*) ou "Qualidade" (ex: *defeito*, *sobreaquecimento*).

---

### 2.4 KPI: Quality Decay Rate (Taxa de Decaimento de Qualidade)
Monitora a queda de rating de um produto ao longo dos meses, detetando lotes defeituosos.

```javascript
db.reviews.aggregate([
  {
    $group: {
      _id: {
        produto: "$product.name",
        mes: { $dateToString: { format: "%Y-%m", date: "$metadata.timestamp" } }
      },
      notaMedia: { $avg: "$metrics.rating" },
      totalReviews: { $sum: 1 }
    }
  },
  { $sort: { "_id.produto": 1, "_id.mes": 1 } },
  {
    $group: {
      _id: "$_id.produto",
      evolucaoMensal: {
        $push: {
          mes: "$_id.mes",
          notaMedia: "$notaMedia",
          totalReviews: "$totalReviews"
        }
      }
    }
  }
])
```

---

### 2.5 KPI: Anomaly Detection (Detecção de Queda Abrupta)
Identifica produtos cuja nota média caiu mais de 30% no último mês face ao mês anterior.

```javascript
db.reviews.aggregate([
  {
    $group: {
      _id: {
        produto: "$product.name",
        mes: { $dateToString: { format: "%Y-%m", date: "$metadata.timestamp" } }
      },
      notaMedia: { $avg: "$metrics.rating" }
    }
  },
  { $sort: { "_id.produto": 1, "_id.mes": 1 } },
  {
    $group: {
      _id: "$_id.produto",
      historico: { $push: { mes: "$_id.mes", nota: "$notaMedia" } }
    }
  },
  {
    $project: {
      ultimoMes: { $arrayElemAt: ["$historico", -1] },
      penultimoMes: { $arrayElemAt: ["$historico", -2] }
    }
  },
  {
    $project: {
      queda: {
        $subtract: ["$penultimoMes.nota", "$ultimoMes.nota"]
      },
      ultimoMes: 1,
      penultimoMes: 1
    }
  },
  { $match: { queda: { $gte: 1.0 } } },
  { $sort: { queda: -1 } }
])
```

---

## 3. Queries Geoespaciais (MongoDB como Base de Dados Espacial)

O índice `2dsphere` sobre `customer.location.coordinates` habilita operadores espaciais que permitem análises geográficas nativas, sem sistemas externos.

### 3.1 Reviews num Raio de 200 km de Luanda
Identifica todas as reviews originadas num raio de 200 km do centro de Luanda (útil para análise de logística de última milha).

```javascript
db.reviews.find({
  "customer.location.coordinates": {
    $nearSphere: {
      $geometry: {
        type: "Point",
        coordinates: [13.2343, -8.8368]
      },
      $maxDistance: 200000  // 200 km em metros
    }
  }
})
```

---

### 3.2 Net Sentiment Score (NSS) por Cidade
Calcula o índice de satisfação líquida para cada cidade — a métrica geoespacial central do dashboard.

```javascript
db.reviews.aggregate([
  {
    $group: {
      _id: "$customer.location.city",
      cidade: { $first: "$customer.location.city" },
      lon: { $first: { $arrayElemAt: ["$customer.location.coordinates.coordinates", 0] } },
      lat: { $first: { $arrayElemAt: ["$customer.location.coordinates.coordinates", 1] } },
      totalReviews: { $sum: 1 },
      notaMedia: { $avg: "$metrics.rating" },
      positivos: {
        $sum: { $cond: [{ $eq: ["$metrics.sentiment", "Positive"] }, 1, 0] }
      },
      negativos: {
        $sum: { $cond: [{ $eq: ["$metrics.sentiment", "Negative"] }, 1, 0] }
      }
    }
  },
  {
    $project: {
      cidade: 1,
      lon: 1,
      lat: 1,
      totalReviews: 1,
      notaMedia: { $round: ["$notaMedia", 2] },
      nss: {
        $subtract: [
          { $multiply: [{ $divide: ["$positivos", "$totalReviews"] }, 100] },
          { $multiply: [{ $divide: ["$negativos", "$totalReviews"] }, 100] }
        ]
      }
    }
  },
  { $sort: { nss: -1 } }
])
```

---

### 3.3 Concentração Regional de Reclamações por Keyword
Determina em que cidade uma keyword de problema específica é mais reportada (ex: "atraso", "defeito").

```javascript
db.reviews.aggregate([
  { $match: { "metrics.sentiment": "Negative" } },
  { $unwind: "$content.keywords" },
  {
    $group: {
      _id: {
        cidade: "$customer.location.city",
        keyword: "$content.keywords"
      },
      frequencia: { $sum: 1 },
      lon: { $first: { $arrayElemAt: ["$customer.location.coordinates.coordinates", 0] } },
      lat: { $first: { $arrayElemAt: ["$customer.location.coordinates.coordinates", 1] } }
    }
  },
  { $match: { "_id.keyword": "atraso" } },
  { $sort: { frequencia: -1 } }
])
```

---

### 3.4 Keyword Correlation Index (KCI) — Correlação Keyword / Rating
Mapeia quais keywords têm maior correlação com notas baixas.

```javascript
db.reviews.aggregate([
  { $unwind: "$content.keywords" },
  {
    $group: {
      _id: "$content.keywords",
      notaMedia: { $avg: "$metrics.rating" },
      frequencia: { $sum: 1 },
      occNegativas: {
        $sum: { $cond: [{ $eq: ["$metrics.sentiment", "Negative"] }, 1, 0] }
      }
    }
  },
  {
    $project: {
      keyword: "$_id",
      notaMedia: { $round: ["$notaMedia", 2] },
      frequencia: 1,
      kci: {
        $multiply: [{ $divide: ["$occNegativas", "$frequencia"] }, 100]
      },
      _id: 0
    }
  },
  { $match: { frequencia: { $gte: 2 } } },
  { $sort: { kci: -1 } },
  { $limit: 15 }
])
```

---

## 4. Análise de Performance e Indexação

| Query | Índice Utilizado | Complexidade | Ganho de Performance |
| :--- | :--- | :--- | :--- |
| Ranking de produtos | `product.category: 1` | $\mathcal{O}(n)$ | Evita full-collection scan |
| Root Cause Analysis | `metrics.sentiment: 1, content.keywords: 1` | $\mathcal{O}(\log n + k)$ | Skip direto de reviews positivas |
| Decay Rate temporal | `metadata.timestamp: -1` | $\mathcal{O}(\log n)$ | Ordenação pré-computada |
| Queries espaciais | `2dsphere` (R-tree) | $\mathcal{O}(\log n)$ | Filtro geográfico antes de processar |

## 5. Considerações de Memória
O MongoDB limita as etapas de agregação a 100MB de RAM. Para datasets massivos, ativar a opção `allowDiskUse: true`:

```javascript
db.reviews.aggregate([...], { allowDiskUse: true })
```
