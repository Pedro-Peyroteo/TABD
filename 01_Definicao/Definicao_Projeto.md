# Definição Estratégica do Projeto: GlobalShop Sentiment Intelligence

## 1. Contextualização e Cenário de Negócio
A **GlobalShop** é um ecossistema de e-commerce que opera num modelo de marketplace global, com foco nos mercados africanos de língua portuguesa. Com a expansão acelerada, a empresa passou a receber centenas de milhares de avaliações diárias, distribuídas por cidades como Luanda, Benguela, Huambo, Lubango, Malanje e Cabinda. Estes dados, embora valiosos, encontram-se em estado "bruto" (raw data), consistindo em textos livres, notas numéricas e metadados variados, incluindo a **localização geográfica** de cada cliente.

Atualmente, a empresa utiliza métodos de amostragem manual para entender a satisfação do cliente, o que gera um atraso crítico na resposta a problemas de qualidade. Se um lote de produtos chega com defeito, a empresa demora dias a detetar o padrão nas reviews, resultando num aumento de devoluções e perda de reputação. Adicionalmente, não existe visibilidade sobre **como a insatisfação se distribui geograficamente**, impedindo a identificação de falhas logísticas regionais.

## 2. Problema de Negócio e Desafios Técnicos
O desafio principal é a **falta de visibilidade em tempo real sobre a qualidade do catálogo e a sua distribuição geográfica**. Os problemas específicos identificados foram:
- **Inconsistência de Dados:** Reviews de eletrónicos contêm informações técnicas, enquanto reviews de moda focam-se em tamanho e tecido. Um modelo relacional exigiria centenas de colunas nulas ou tabelas de ligação complexas.
- **Latência de Análise:** A extração de tendências a partir de texto livre é lenta em bases de dados SQL tradicionais.
- **Incapacidade de Pivotagem Regional:** A gestão não consegue filtrar rapidamente a insatisfação por região geográfica ou nível de fidelidade do cliente.
- **Ausência de Análise Espacial:** Não é possível identificar, por exemplo, que a cidade de Malanje concentra 40% das reclamações de entrega, sinalizando um problema específico com o transportador regional.

## 3. Proposta de Solução: NoSQL + Spatial BI Pipeline
A solução proposta consiste na implementação de uma pipeline de dados moderna, dividida em três camadas, com suporte nativo a dados geoespaciais:

### A. Camada de Ingestão e Armazenamento (NoSQL + Geoespacial)
Implementação de uma base de dados orientada a documentos (MongoDB). Esta escolha permite que cada review seja tratada como um objeto independente, suportando a variabilidade dos atributos sem a necessidade de migrações de esquema constantes. A localização de cada cliente é armazenada em formato **GeoJSON (tipo Point)**, habilitando o MongoDB a funcionar como **base de dados espacial** através dos seus operadores geoespaciais nativos (`$geoNear`, `$geoWithin`, `$near`) e do índice `2dsphere`.

### B. Camada de Processamento (Aggregation Framework + Spatial Queries)
Utilização de pipelines de agregação para transformar dados semiestruturados em métricas quantificáveis. O foco será a extração de:
- **Métricas de Volume:** Total de reviews por categoria e por região geográfica.
- **Métricas de Qualidade:** Nota média ponderada e taxa de decaimento por lote.
- **Métricas de Sentimento:** Distribuição de polaridade (Positivo/Neutro/Negativo) por cidade.
- **Métricas Espaciais:** Concentração de reclamações por zona geográfica e raio de influência logística.

### C. Camada de Visualização (Business Intelligence + Mapa Interativo)
Integração dos dados processados com um dashboard Streamlit que inclui, além das análises tradicionais, uma **visão geoespacial interativa** com mapa de calor de satisfação por cidade. O objetivo é que um gestor de categoria possa, em 5 segundos, identificar qual o produto com maior taxa de reclamações na região de Luanda, ou se um problema de entrega está concentrado numa província específica.

## 4. Justificativa Técnica: Por que MongoDB como Base de Dados NoSQL e Espacial?

### 4.1 Comparativo NoSQL vs SQL
| Critério | Base de Dados Relacional (SQL) | MongoDB (NoSQL) | Vantagem GlobalShop |
| :--- | :--- | :--- | :--- |
| **Esquema** | Rígido (Fixed Schema) | Flexível (Dynamic Schema) | Suporta atributos variados por categoria. |
| **Escalabilidade** | Vertical (Scale-up) | Horizontal (Scale-out) | Pronto para crescer para milhões de reviews. |
| **Performance** | JOINs pesados para agregação | Documentos auto-contidos | Leitura instantânea para o BI. |
| **Modelagem** | Normalização (3NF) | Denormalização (Embedding) | Menor latência no acesso aos dados. |

### 4.2 Comparativo Espacial: PostGIS vs MongoDB Geospatial
| Critério | PostGIS (PostgreSQL) | MongoDB Geospatial | Vantagem GlobalShop |
| :--- | :--- | :--- | :--- |
| **Integração** | Sistema separado do BD principal | Nativo no mesmo documento | Uma única base de dados para tudo. |
| **Formato** | Tipos espaciais proprietários | GeoJSON (padrão aberto) | Interoperabilidade com APIs modernas. |
| **Índice Espacial** | GIST/BRIN | `2dsphere` (esfera terrestre) | Cálculos de distância reais (haversine). |
| **Complexidade Operacional** | Alta (extensão + configuração) | Baixa (índice + operadores) | Menos infraestrutura para gerir. |

A escolha do **MongoDB** como base de dados espacial elimina a necessidade de um sistema separado (como PostGIS), reduzindo a complexidade operacional e permitindo que as queries espaciais e analíticas coexistam na mesma pipeline de agregação.

---
**Conclusão da Definição:** O projeto não visa apenas a implementação de uma base de dados, mas a criação de um sistema de suporte à decisão (Decision Support System - DSS) que combina análise de sentimentos NoSQL com inteligência geoespacial, reduzindo o tempo de resposta da empresa a incidentes de qualidade de dias para minutos e adicionando a dimensão geográfica à análise de satisfação do cliente.
