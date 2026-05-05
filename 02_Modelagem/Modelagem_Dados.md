# Arquitetura e Modelagem de Dados NoSQL + Espacial

Nesta secção, detalhamos a engenharia de dados por trás do sistema GlobalShop. A modelagem em NoSQL difere fundamentalmente da modelagem relacional; enquanto no SQL modelamos para evitar a redundância, no NoSQL modelamos para **otimizar a consulta**. A dimensão espacial é incorporada diretamente no documento através do padrão **GeoJSON**, transformando o MongoDB também numa base de dados espacial.

## 1. Análise de Entidades e Relacionamentos
Identificamos três entidades principais no ecossistema:
1. **Review:** A entidade central, contendo a nota, o comentário e o timestamp.
2. **Product:** Informações sobre o item avaliado (nome, categoria, marca).
3. **Customer:** Perfil do utilizador que avaliou (localização geoespacial, nível de membro).

No modelo relacional, teríamos 3 tabelas e 2 JOINs para cada consulta de BI. No nosso modelo NoSQL, consolidamos estas entidades num único documento, incluindo as **coordenadas geográficas** do cliente.

## 2. Estratégia de Modelagem: Embedding (Incorporação)
Optámos pela estratégia de **Embedding**, onde as informações de `Produto` e `Cliente` são incorporadas diretamente dentro do documento de `Review`.

### Justificativa Técnica da Estratégia:
- **Atomicidade de Leitura:** O BI necessita de saber o nome do produto, a localização do cliente e a nota simultaneamente. Com Embedding, recuperamos tudo numa única operação de disco (Single Disk Seek).
- **Imutabilidade Histórica:** Se um cliente mudar de morada hoje, a review que ele fez há um ano deve manter a localização de onde ele estava na altura. O embedding preserva o contexto histórico da transação.
- **Consultas Espaciais Integradas:** Ao incluir as coordenadas GeoJSON diretamente no documento, é possível combinar filtros de sentimento com filtros geoespaciais numa única pipeline de agregação, sem necessidade de JOINs ou sistemas externos.

## 3. Especificação Técnica do Documento (Schema)

O documento segue a especificação JSON/BSON com suporte a **GeoJSON (RFC 7946)**:

```json
{
  "_id": "ObjectId",
  "review_id": "UUID",
  "product": {
    "product_id": "String",
    "name": "String",
    "category": "String",
    "brand": "String",
    "specifications": { "dynamic_field": "Value" }
  },
  "customer": {
    "customer_id": "String",
    "name": "String",
    "location": {
      "city": "String",
      "country": "String",
      "coordinates": {
        "type": "Point",
        "coordinates": ["Longitude (Number)", "Latitude (Number)"]
      }
    },
    "membership": "String (Gold|Silver|Bronze)"
  },
  "metrics": {
    "rating": "Number (1-5)",
    "sentiment": "String (Positive|Neutral|Negative)",
    "verified_purchase": "Boolean"
  },
  "content": {
    "comment": "String",
    "keywords": ["Array of Strings"],
    "language": "String (pt|en|fr)"
  },
  "metadata": {
    "timestamp": "ISODate",
    "device": "String (Mobile|Web|App)"
  }
}
```

### Exemplo de Documento Real:
```json
{
  "_id": "ObjectId('...')",
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
      "city": "Lubango",
      "country": "Angola",
      "coordinates": {
        "type": "Point",
        "coordinates": [13.4920, -14.9177]
      }
    },
    "membership": "Silver"
  },
  "metrics": {
    "rating": 2,
    "sentiment": "Negative",
    "verified_purchase": true
  },
  "content": {
    "comment": "A bateria começa a sobreaquecer. Parece defeito de lote!",
    "keywords": ["bateria", "sobreaquecimento", "defeito"],
    "language": "pt"
  },
  "metadata": {
    "timestamp": "2026-04-02T10:00:00Z",
    "device": "Mobile"
  }
}
```

## 4. Estratégia de Indexação

Para garantir performance em escala de Big Data, são criados os seguintes índices:

| Índice | Tipo | Campo | Objetivo |
| :--- | :--- | :--- | :--- |
| `idx_category` | Simples | `product.category: 1` | Acelera agrupamentos por categoria |
| `idx_sentiment_keywords` | Composto | `metrics.sentiment: 1, content.keywords: 1` | Otimiza análise de causa raiz |
| `idx_timestamp` | Simples | `metadata.timestamp: -1` | Suporta análises temporais (decay rate) |
| `idx_geo` | **2dsphere** | `customer.location.coordinates` | Habilita consultas espaciais (raio, polígono) |

O índice `2dsphere` é o que transforma o MongoDB numa **base de dados espacial**, permitindo consultas como "todas as reviews num raio de 100 km de Luanda" ou "comparação de satisfação entre províncias".

## 5. Análise de Complexidade
- **Complexidade de Escrita:** $\mathcal{O}(1)$. A inserção de uma review é uma operação simples de escrita de documento.
- **Complexidade de Leitura para BI:** $\mathcal{O}(1)$ por documento. Não existem JOINs, o que torna a agregação de milhões de registos significativamente mais rápida do que num sistema normalizado.
- **Complexidade de Consulta Espacial:** $\mathcal{O}(\log n)$ com índice `2dsphere`. A estrutura de árvore R-tree subjacente permite localizar documentos geográficos em tempo logarítmico.
- **Espaço em Disco:** Há uma redundância de dados (o nome do produto repete-se em cada review), mas em sistemas de Big Data, o custo do armazenamento é inferior ao custo da latência de processamento (Trade-off Espaço vs Tempo).
