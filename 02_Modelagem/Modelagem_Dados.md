# Arquitetura e Modelagem de Dados NoSQL + Espacial

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD)
**Ano Letivo:** 2025/2026

---

## 1. Análise de Entidades e Relacionamentos

O ecossistema de dados da GlobalShop Portugal centra-se em três entidades principais:

1. **Review** — entidade central, contendo a nota numérica, o comentário em linguagem natural e o timestamp da avaliação.
2. **Produto** — informação sobre o artigo avaliado: nome, categoria, marca e especificações técnicas variáveis.
3. **Cliente** — perfil do utilizador que avaliou, incluindo o nível de membership e, de forma crítica, a **localização geográfica** em formato GeoJSON.

Num modelo relacional clássico, estas três entidades corresponderiam a três tabelas distintas, exigindo dois JOINs em cada query de BI. No modelo NoSQL adotado, as entidades são consolidadas num único documento, eliminando os JOINs e habilitando a análise geoespacial nativa.

---

## 2. Estratégia de Modelagem: Embedding (Incorporação)

Optou-se pela estratégia de **Embedding**, em que os dados de Produto e Cliente são incorporados diretamente dentro do documento de Review, formando um objeto auto-contido.

### Justificativa Técnica

**Atomicidade de Leitura:** O dashboard de BI necessita simultaneamente do nome do produto, da localização do cliente e da nota. Com Embedding, todos estes dados são recuperados numa única operação de disco (*single disk seek*), sem custo de JOIN.

**Imutabilidade Histórica:** Se um cliente mudar de cidade, as reviews anteriores devem preservar a localização do momento da compra. O Embedding garante o congelamento do contexto histórico por design.

**Consultas Espaciais Integradas:** A presença das coordenadas GeoJSON diretamente no documento permite combinar, na mesma pipeline de agregação, filtros analíticos (sentimento, categoria) com filtros geoespaciais (raio de Lisboa, NSS por cidade). Esta combinação é inviável num modelo normalizado sem extensões como o PostGIS.

---

## 3. Especificação Técnica do Schema (JSON/BSON + GeoJSON)

O documento segue o padrão JSON/BSON com suporte a **GeoJSON RFC 7946**:

```json
{
  "_id": "ObjectId",
  "review_id": "String (UUID)",
  "product": {
    "product_id": "String",
    "name": "String",
    "category": "String",
    "brand": "String",
    "specifications": { "<campo_dinâmico>": "<valor>" }
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
    "membership": "String (Gold | Silver | Bronze)"
  },
  "metrics": {
    "rating": "Number (1–5)",
    "sentiment": "String (Positive | Neutral | Negative)",
    "verified_purchase": "Boolean"
  },
  "content": {
    "comment": "String (texto livre)",
    "keywords": ["Array de Strings"],
    "language": "String (pt | en)"
  },
  "metadata": {
    "timestamp": "ISODate",
    "device": "String (Mobile | Web | App)"
  }
}
```

### Exemplo de Documento Real — Lisboa

```json
{
  "_id": "ObjectId('...')",
  "review_id": "R021",
  "product": {
    "product_id": "P101",
    "name": "Smartphone X1",
    "category": "Eletrónicos",
    "brand": "TechCorp"
  },
  "customer": {
    "customer_id": "C521",
    "name": "Sérgio Matos",
    "location": {
      "city": "Lisboa",
      "country": "Portugal",
      "coordinates": { "type": "Point", "coordinates": [-9.1393, 38.7223] }
    },
    "membership": "Gold"
  },
  "metrics": { "rating": 1, "sentiment": "Negative", "verified_purchase": true },
  "content": {
    "comment": "O telemóvel avariou completamente. Defeito grave, sobreaquecimento e bateria expandida.",
    "keywords": ["defeito", "sobreaquecimento", "bateria", "avaria"],
    "language": "pt"
  },
  "metadata": { "timestamp": "2026-05-01T08:00:00Z", "device": "Mobile" }
}
```

---

## 4. Coordenadas GeoJSON das Cidades Portuguesas

O dataset utiliza coordenadas reais das seis cidades portuguesas cobertas pelo sistema:

| Cidade | Longitude | Latitude | Região |
| :--- | :--- | :--- | :--- |
| Lisboa | -9.1393 | 38.7223 | Área Metropolitana de Lisboa |
| Porto | -8.6291 | 41.1579 | Área Metropolitana do Porto |
| Coimbra | -8.4291 | 40.2033 | Centro |
| Braga | -8.4261 | 41.5454 | Norte (Minho) |
| Faro | -7.9304 | 37.0194 | Algarve |
| Setúbal | -8.8951 | 38.5244 | Península de Setúbal |

> As coordenadas seguem o padrão GeoJSON: `[longitude, latitude]` (atenção à ordem — inversa ao par lat/lon convencional).

---

## 5. Estratégia de Indexação

A performance das queries analíticas e espaciais é garantida por quatro índices complementares:

### 5.1 Índice Simples — Categoria

```javascript
db.reviews.createIndex({ "product.category": 1 });
```

Otimiza os agrupamentos por categoria de produto (Tab 2 do dashboard). Complexidade: $\mathcal{O}(\log n)$ vs. $\mathcal{O}(n)$ sem índice.

### 5.2 Índice Composto — Causa Raiz

```javascript
db.reviews.createIndex({ "metrics.sentiment": 1, "content.keywords": 1 });
```

Permite o skip direto de documentos com sentimento Positive/Neutral nas queries de análise de causa raiz, reduzindo o conjunto de documentos a processar.

### 5.3 Índice Temporal — Quality Decay Rate

```javascript
db.reviews.createIndex({ "metadata.timestamp": -1 });
```

Suporta a separação eficiente entre o período recente (últimos 30 dias) e o histórico anterior, necessária para o cálculo do Quality Decay Rate.

### 5.4 Índice Espacial — 2dsphere ⭐

```javascript
db.reviews.createIndex({ "customer.location.coordinates": "2dsphere" });
```

O índice `2dsphere` é o elemento central da componente espacial do sistema. Transforma o MongoDB numa base de dados espacial nativa, habilitando:
- Queries de proximidade (`$near`, `$nearSphere`) — "reviews num raio de X km de Lisboa"
- Queries de contenção (`$geoWithin`) — "reviews dentro de um polígono geográfico"
- Cálculo de distâncias reais usando geometria esférica (fórmula de Haversine)

| Índice | Tipo | Campo(s) | Complexidade | Operadores Habilitados |
| :--- | :--- | :--- | :--- | :--- |
| Categoria | Simples | `product.category` | $\mathcal{O}(\log n)$ | `$match`, `$group` |
| Causa Raiz | Composto | `sentiment` + `keywords` | $\mathcal{O}(\log n + k)$ | `$match` seletivo |
| Temporal | Simples | `metadata.timestamp` | $\mathcal{O}(\log n)$ | Range queries temporais |
| **Espacial** | **2dsphere** | `location.coordinates` | $\mathcal{O}(\log n)$ | `$near`, `$geoNear`, `$geoWithin` |

---

## 6. Comparativo de Estratégias de Modelagem

| Estratégia | Quando Usar | Desvantagem |
| :--- | :--- | :--- |
| **Embedding** *(adotada)* | Dados acedidos em conjunto; relação 1-para-poucos | Duplicação controlada de dados |
| **Referencing** | Dados partilhados por muitas entidades; documentos muito grandes | Requer `$lookup` (equivalente ao JOIN) |

Para o caso da GlobalShop, o Embedding é a escolha correta: cada review é uma entidade autónoma, o produto e o cliente são contextos históricos imutáveis, e a leitura conjunta é o padrão dominante de acesso.
