# Arquitetura e Modelagem de Dados NoSQL

Nesta secção, detalhamos a engenharia de dados por trás do sistema GlobalShop. A modelagem em NoSQL difere fundamentalmente da modelagem relacional; enquanto no SQL modelamos para evitar a redundância, no NoSQL modelamos para **otimizar a consulta**.

## 1. Análise de Entidades e Relacionamentos
Identificamos três entidades principais no ecossistema:
1. **Review:** A entidade central, contendo a nota, o comentário e o timestamp.
2. **Product:** Informações sobre o item avaliado (nome, categoria, marca).
3. **Customer:** Perfil do utilizador que avaliou (localização, nível de membro).

No modelo relacional, teríamos 3 tabelas e 2 JOINs para cada consulta de BI. No nosso modelo NoSQL, consolidamos estas entidades num único documento.

## 2. Estratégia de Modelagem: Embedding (Incorporação)
Optámos pela estratégia de **Embedding**, onde as informações de `Produto` e `Cliente` são incorporadas diretamente dentro do documento de `Review`.

### Justificativa Técnica da Estratégia:
- **Atomicidade de Leitura:** O BI necessita de saber o nome do produto e a localização do cliente simultaneamente à nota. Com Embedding, recuperamos tudo numa única operação de disco (Single Disk Seek).
- **Imutabilidade Histórica:** Se um cliente mudar de morada hoje, a review que ele fez há um ano deve manter a localização de onde ele estava na altura. O embedding preserva o contexto histórico da transação.

## 3. Especificação Técnica do Documento (Schema)

O documento segue a especificação JSON/BSON:

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
      "country": "String"
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
    "language": "String"
  },
  "metadata": {
    "timestamp": "ISODate",
    "device": "String (Mobile|Web|App)"
  }
}
```

## 4. Análise de Complexidade
- **Complexidade de Escrita:** $\mathcal{O}(1)$. A inserção de uma review é uma operação simples de escrita de documento.
- **Complexidade de Leitura para BI:** $\mathcal{O}(1)$ por documento. Não existem JOINs, o que torna a agregação de milhões de registos significativamente mais rápida do que num sistema normalizado.
- **Espaço em Disco:** Há uma redundância de dados (o nome do produto repete-se em cada review), mas em sistemas de Big Data, o custo do armazenamento é inferior ao custo da latência de processamento (Trade-off Espaço vs Tempo).
