# Implementação Técnica: NoSQL + Spatial Data Pipeline

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD)
**Ano Letivo:** 2025/2026

---

O Aggregation Framework do MongoDB funciona como uma pipeline de transformação sequencial, onde cada estágio (`$match`, `$group`, `$sort`, `$project`, etc.) recebe os documentos do estágio anterior e os transforma progressivamente. A integração do índice `2dsphere` adiciona a dimensão geoespacial à mesma pipeline, sem necessidade de sistemas externos.

> **Nota sobre campos:** O schema segue a estrutura aninhada definida em `02_Modelagem/Modelagem_Dados.md`. Os campos de rating estão em `metrics.rating`, sentimento em `metrics.sentiment`, keywords em `content.keywords`, e as coordenadas em `customer.location.coordinates`.

---

## 1. Configuração Inicial dos Índices

Antes de executar qualquer query, criar os índices no **Mongosh**:

```javascript
// 1. Índice de categoria para agrupamentos
db.reviews.createIndex({ "product.category": 1 });

// 2. Índice composto para análise de causa raiz
db.reviews.createIndex({ "metrics.sentiment": 1, "content.keywords": 1 });

// 3. Índice temporal para cálculo de Quality Decay Rate
db.reviews.createIndex({ "metadata.timestamp": -1 });

// 4. Índice 2dsphere — transforma o MongoDB em Base de Dados Espacial
//    Habilita $geoNear, $geoWithin e $near sobre os campos GeoJSON Point
db.reviews.createIndex({ "customer.location.coordinates": "2dsphere" });
```

---

## 2. Queries Analíticas (BI)

### 2.1 KPI: Ranking de Satisfação — Deteção de Produtos Críticos

Identifica os produtos com pior performance média, filtrando aqueles com nota ≤ 3.0.

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
- `$group`: Agrega todos os documentos por nome de produto, calculando a média aritmética do campo `metrics.rating`.
- `$match` pós-group: Filtra apenas a "cauda inferior" da distribuição (notas ≤ 3.0 — zona de risco).
- **Complexidade:** $\mathcal{O}(n)$ na fase de group, $\mathcal{O}(\log n)$ com índice de categoria na fase de match.

---

### 2.2 KPI: Análise de Polaridade por Categoria

Cria uma matriz bidimensional de sentimentos (Positive, Neutral, Negative) por departamento de produto.

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

**Análise Técnica:**
- Chave composta `_id: { categoria, sentimento }` permite o agrupamento bidimensional sem subqueries.
- `$project` com `_id: 0` limpa o output para consumo direto pelo dashboard.

---

### 2.3 KPI: Root Cause Analysis — Frequência de Keywords Negativas

Expande os arrays de keywords e conta a frequência de cada termo em reviews com sentimento Negative.

```javascript
db.reviews.aggregate([
  { $match: { "metrics.sentiment": "Negative" } },
  { $unwind: "$content.keywords" },
  {
    $group: {
      _id: "$content.keywords",
      frequencia: { $sum: 1 },
      notaMedia: { $avg: "$metrics.rating" }
    }
  },
  { $sort: { frequencia: -1 } },
  { $limit: 15 }
])
```

**Análise Técnica:**
- `$match` no início da pipeline — o MongoDB aplica o índice composto (`sentiment + keywords`) para restringir o conjunto de documentos antes do `$unwind`, reduzindo significativamente o volume processado.
- `$unwind` "explode" o array de keywords, criando um documento por cada elemento.

---

### 2.4 KPI: Quality Decay Rate — Decaimento de Qualidade por Produto

Calcula a evolução da nota média mensal por produto, permitindo a identificação de tendências de decaimento.

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
  { $sort: { "_id.produto": 1, "_id.mes": 1 } }
])
```

**Análise Técnica:**
- `$dateToString` com formato `%Y-%m` trunca o timestamp para granularidade mensal, agrupando todas as reviews de um produto num mesmo mês.
- O índice temporal (`metadata.timestamp: -1`) otimiza o acesso sequencial por data.

---

### 2.5 KPI: Anomaly Detection — Deteção Automática de Lotes Defeituosos

Identifica produtos com queda de rating ≥ 30% entre o penúltimo e o último mês com dados, emitindo um alerta de anomalia.

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
      produto: "$_id",
      ultimoMes: { $arrayElemAt: ["$historico", -1] },
      penultimoMes: { $arrayElemAt: ["$historico", -2] }
    }
  },
  {
    $project: {
      produto: 1,
      ultimoMes: 1,
      penultimoMes: 1,
      quedaPct: {
        $multiply: [
          { $divide: [
            { $subtract: ["$penultimoMes.nota", "$ultimoMes.nota"] },
            "$penultimoMes.nota"
          ]},
          100
        ]
      }
    }
  },
  { $match: { quedaPct: { $gte: 30 } } },
  { $sort: { quedaPct: -1 } }
])
```

**Análise Técnica:**
- Padrão "double-group": o primeiro `$group` calcula a média mensal; o segundo consolida o histórico por produto num array ordenado cronologicamente.
- `$arrayElemAt` com índice `-1` e `-2` extrai o último e o penúltimo elemento sem subqueries.

---

## 3. Queries Geoespaciais

### 3.1 Reviews num Raio de 100 km de Lisboa

Recupera todas as reviews originadas num raio de 100 km a partir do centro de Lisboa, utilizando geometria esférica real.

```javascript
db.reviews.find({
  "customer.location.coordinates": {
    $nearSphere: {
      $geometry: { type: "Point", coordinates: [-9.1393, 38.7223] },
      $maxDistance: 100000
    }
  }
})
```

**Análise Técnica:**
- `$nearSphere` requer o índice `2dsphere` — sem ele, o MongoDB lança um erro. O índice garante que apenas os documentos dentro do raio especificado são retornados, sem full-collection scan.
- `$maxDistance` é expresso em **metros** (100 000 m = 100 km).
- Os resultados são ordenados automaticamente por distância crescente ao ponto de referência.

---

### 3.2 Net Sentiment Score (NSS) por Cidade

Calcula o NSS para cada cidade portuguesa, agregando polaridade por localização geográfica.

```javascript
db.reviews.aggregate([
  {
    $group: {
      _id: "$customer.location.city",
      totalReviews: { $sum: 1 },
      positivos: {
        $sum: { $cond: [{ $eq: ["$metrics.sentiment", "Positive"] }, 1, 0] }
      },
      negativos: {
        $sum: { $cond: [{ $eq: ["$metrics.sentiment", "Negative"] }, 1, 0] }
      },
      notaMedia: { $avg: "$metrics.rating" },
      lat: { $first: { $arrayElemAt: ["$customer.location.coordinates.coordinates", 1] } },
      lon: { $first: { $arrayElemAt: ["$customer.location.coordinates.coordinates", 0] } }
    }
  },
  {
    $project: {
      cidade: "$_id",
      totalReviews: 1,
      notaMedia: { $round: ["$notaMedia", 2] },
      nss: {
        $subtract: [
          { $multiply: [{ $divide: ["$positivos", "$totalReviews"] }, 100] },
          { $multiply: [{ $divide: ["$negativos", "$totalReviews"] }, 100] }
        ]
      },
      lat: 1,
      lon: 1,
      _id: 0
    }
  },
  { $sort: { nss: -1 } }
])
```

**Análise Técnica:**
- `$cond` com `$eq` implementa uma soma condicional inline — equivalente ao `CASE WHEN` do SQL mas sem subqueries.
- `$arrayElemAt` com índice 1 e 0 extrai latitude e longitude do array GeoJSON `[lon, lat]`, preservando as coordenadas para visualização no mapa.

---

### 3.3 Concentração Regional de Keywords de Problema

Identifica quais palavras-chave negativas estão geograficamente concentradas em certas cidades.

```javascript
db.reviews.aggregate([
  { $match: { "metrics.sentiment": "Negative" } },
  { $unwind: "$content.keywords" },
  {
    $group: {
      _id: {
        keyword: "$content.keywords",
        cidade: "$customer.location.city"
      },
      frequencia: { $sum: 1 },
      lat: { $first: { $arrayElemAt: ["$customer.location.coordinates.coordinates", 1] } },
      lon: { $first: { $arrayElemAt: ["$customer.location.coordinates.coordinates", 0] } }
    }
  },
  { $sort: { frequencia: -1 } }
])
```

**Análise Técnica:**
- Esta query combina análise textual (keyword) com análise geoespacial (cidade), numa única pipeline — impossível de forma nativa em SQL sem extensões geoespaciais.
- Permite identificar, por exemplo, que a keyword "atraso" é predominante em Faro, sinalizando uma falha no parceiro logístico regional do Algarve.

---

### 3.4 Keyword Correlation Index (KCI) — Correlação Keyword / Rating

Mapeia quais palavras-chave têm maior correlação com notas baixas, calculando o KCI para priorização de causa raiz.

```javascript
db.reviews.aggregate([
  { $unwind: "$content.keywords" },
  {
    $group: {
      _id: "$content.keywords",
      notaMedia: { $avg: "$metrics.rating" },
      frequencia: { $sum: 1 },
      ocorrenciasNegativas: {
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
        $multiply: [{ $divide: ["$ocorrenciasNegativas", "$frequencia"] }, 100]
      },
      _id: 0
    }
  },
  { $match: { frequencia: { $gte: 2 } } },
  { $sort: { kci: -1 } },
  { $limit: 15 }
])
```

**Fórmula do KCI:**

$$\text{KCI}(k) = \frac{\text{ocorrências de } k \text{ em reviews negativas}}{\text{total de ocorrências de } k} \times 100\%$$

Um KCI de 90% para a keyword "sobreaquecimento" significa que 90% das vezes que este termo aparece, a review é Negative — confirmando uma falha de hardware específica.

---

## 4. Análise de Performance e Indexação

| Query | Índice Utilizado | Complexidade Sem Índice | Complexidade Com Índice | Ganho |
| :--- | :--- | :--- | :--- | :--- |
| Ranking de produtos | `product.category: 1` | $\mathcal{O}(n)$ — full scan | $\mathcal{O}(\log n)$ | Evita varredura completa da coleção |
| Root Cause Analysis | `sentiment + keywords` composto | $\mathcal{O}(n)$ | $\mathcal{O}(\log n + k)$ | Skip direto de reviews Positive/Neutral |
| Quality Decay Rate | `metadata.timestamp: -1` | $\mathcal{O}(n \log n)$ | $\mathcal{O}(\log n)$ | Ordenação temporal pré-computada |
| Queries espaciais | `2dsphere` (R-tree esférico) | Impossível nativamente | $\mathcal{O}(\log n)$ | Filtro geográfico antes de processar documentos |

---

## 5. Considerações de Escala

Para datasets superiores a 100 MB de RAM disponível, ativar `allowDiskUse`:

```javascript
db.reviews.aggregate([...], { allowDiskUse: true })
```

Para escala horizontal (milhões de reviews), o MongoDB suporta **sharding** nativo com shard key em `product.category` ou `metadata.timestamp`, mantendo a compatibilidade com todos os operadores geoespaciais documentados nesta secção.
