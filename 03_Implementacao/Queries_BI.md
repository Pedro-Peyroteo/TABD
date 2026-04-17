# Implementação Técnica: Engineering a NoSQL Data Pipeline

Nesta secção, detalhamos a implementação do pipeline de processamento de dados. O coração do sistema é o **Aggregation Framework** do MongoDB, que funciona como uma pipeline de processamento de dados onde cada etapa transforma os documentos para a etapa seguinte.

## 1. Arquitetura da Pipeline de Agregação
Diferente de queries SQL simples, as agregações do MongoDB permitem operações complexas de transformação. Abaixo, detalhamos a lógica de engenharia por trás de cada KPI.

### 1.1. KPI: Ranking de Satisfação (Detecção de Itens Críticos)
Esta pipeline identifica a performance média de cada produto para isolar falhas de qualidade.

```javascript
db.reviews.aggregate([
  {
    $group: {
      _id: "$product.name",
      notaMedia: { $avg: "$rating" },
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
- **$group**: Colapsa todos os documentos por nome de produto, calculando a média aritmética.
- **$match**: Filtra apenas a "cauda inferior" da distribuição (notas $\le$ 3).
- **Complexidade**: $\mathcal{O}(n)$ onde $n$ é o número de reviews.

### 1.2. KPI: Análise de Polaridade por Categoria
Esta operação permite entender a saúde emocional de cada departamento da GlobalShop.

```javascript
db.reviews.aggregate([
  {
    $group: {
      _id: { 
        categoria: "$product.category", 
        sentimento: "$sentiment" 
      },
      quantidade: { $sum: 1 }
    }
  },
  {
    $project: {
      categoria: "$_id.categoria",
      sentimento: "$_id.sentimento",
      percentagem: { 
        $multiply: [ { $divide: [ "$quantidade", 100 ] }, 100 ] 
      },
      _id: 0
    }
  }
])
```
**Análise Técnica:**
- **Multi-key Grouping**: Agrupamos por um objeto composto (categoria + sentimento), criando uma matriz de dados bidimensional ideal para gráficos de colunas empilhadas.

### 1.3. KPI: Mineração de Texto para Causa Raiz (Root Cause Analysis)
Esta é a query mais complexa, pois lida com dados em formato de array (palavras-chave).

```javascript
db.reviews.aggregate([
  { $match: { sentiment: "Negative" } },
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
- **$unwind**: Esta é a operação crítica. Ela "desconstrói" o array de keywords, criando um documento separado para cada palavra. Se uma review tem 3 keywords, o `$unwind` gera 3 documentos temporários.
- **Frequência Relativa**: Permite isolar se a insatisfação é causada por "Logística" (entrega) ou "Qualidade" (material).

## 2. Análise de Performance e Indexação
Para garantir que estas queries funcionem em escala de Big Data, propomos a criação dos seguintes índices:

1. **Índice Simples:** `{ "product.category": 1 }` $\rightarrow$ Acelera o agrupamento por categoria.
2. **Índice Composto:** `{ "sentiment": 1, "content.keywords": 1 }` $\rightarrow$ Otimiza a query de causa raiz, permitindo que o MongoDB ignore reviews positivas sem ler o documento completo.

## 3. Considerações de Memória
O MongoDB limita as etapas de agregação a 100MB de RAM. Para datasets massivos, ativaremos a opção `allowDiskUse: true`, permitindo que o sistema utilize arquivos temporários no disco para processar volumes de dados que excedam a memória volátil.
