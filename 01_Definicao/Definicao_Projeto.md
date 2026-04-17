# Definição Estratégica do Projeto: GlobalShop Sentiment Intelligence

## 1. Contextualização e Cenário de Negócio
A **GlobalShop** é um ecossistema de e-commerce que opera num modelo de marketplace global. Com a expansão acelerada, a empresa passou a receber centenas de milhares de avaliações diárias. Estes dados, embora valiosos, encontram-se em estado "bruto" (raw data), consistindo em textos livres, notas numéricas e metadados variados.

Atualmente, a empresa utiliza métodos de amostragem manual para entender a satisfação do cliente, o que gera um atraso crítico na resposta a problemas de qualidade. Se um lote de produtos chega com defeito, a empresa demora dias a detetar o padrão nas reviews, resultando num aumento de devoluções e perda de reputação.

## 2. Problema de Negócio e Desafios Técnicos
O desafio principal é a **falta de visibilidade em tempo real sobre a qualidade do catálogo**. Os problemas específicos identificados foram:
- **Inconsistência de Dados:** Reviews de eletrónicos contêm informações técnicas, enquanto reviews de moda focam-se em tamanho e tecido. Um modelo relacional exigiria centenas de colunas nulas ou tabelas de ligação complexas.
- **Latência de Análise:** A extração de tendências a partir de texto livre é lenta em bases de dados SQL tradicionais.
- **Incapacidade de Pivotagem:** A gestão não consegue filtrar rapidamente a insatisfação por região geográfica ou nível de fidelidade do cliente.

## 3. Proposta de Solução: NoSQL-BI Pipeline
A solução proposta consiste na implementação de uma pipeline de dados moderna, dividida em três camadas:

### A. Camada de Ingestão e Armazenamento (NoSQL)
Implementação de uma base de dados orientada a documentos (MongoDB). Esta escolha permite que cada review seja tratada como um objeto independente, suportando a variabilidade dos atributos sem a necessidade de migrações de esquema constantes.

### B. Camada de Processamento (Aggregation Framework)
Utilização de pipelines de agregação para transformar dados semiestruturados em métricas quantificáveis. O foco será a extração de:
- **Métricas de Volume:** Total de reviews por categoria.
- **Métricas de Qualidade:** Nota média ponderada.
- **Métricas de Sentimento:** Distribuição de polaridade (Positivo/Neutro/Negativo).

### C. Camada de Visualização (Business Intelligence)
Integração dos dados processados com ferramentas de BI para a criação de dashboards executivos. O objetivo é que um gestor de categoria possa, em 5 segundos, identificar qual o produto com maior taxa de reclamações na região de Luanda, por exemplo.

## 4. Justificativa Técnica Aprofundada (Por que MongoDB?)
A escolha do MongoDB em detrimento de soluções como PostgreSQL ou MySQL justifica-se pelos seguintes critérios técnicos:

| Critério | Base de Dados Relacional (SQL) | MongoDB (NoSQL) | Vantagem GlobalShop |
| :--- | :--- | :--- | :--- |
| **Esquema** | Rígido (Fixed Schema) | Flexível (Dynamic Schema) | Suporta atributos variados por categoria. |
| **Escalabilidade** | Vertical (Scale-up) | Horizontal (Scale-out) | Pronto para crescer para milhões de reviews. |
| **Performance** | JOINs pesados para agregação | Documentos auto-contidos | Leitura instantânea para o BI. |
| **Modelagem** | Normalização (3NF) | Denormalização (Embedding) | Menor latência no acesso aos dados. |

---
**Conclusão da Definição:** O projeto não visa apenas a implementação de uma base de dados, mas a criação de um sistema de suporte à decisão (Decision Support System - DSS) que reduz o tempo de resposta da empresa a incidentes de qualidade de dias para minutos.
