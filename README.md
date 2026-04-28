# 🛒 GlobalShop: Sistema Avançado de Análise de Sentimentos e Inteligência de Negócio

Este projeto consiste no design, implementação e análise de uma infraestrutura de dados NoSQL integrada com Business Intelligence (BI) para a empresa fictícia **GlobalShop**, um marketplace de e-commerce de escala global. 

O objetivo central é a resolução do problema de "silos de dados não estruturados", transformando milhões de feedbacks de clientes em ativos estratégicos para a gestão de qualidade e experiência do utilizador (UX).

---

## 📌 Visão Geral do Ecossistema
O sistema foi concebido para operar num cenário de **Big Data**, onde a velocidade de ingestão e a variedade dos dados tornam os sistemas relacionais tradicionais ineficientes. A solução utiliza o paradigma de documentos para permitir a evolução orgânica do esquema de dados sem a necessidade de interrupções para migrações (Zero Downtime Schema Evolution).

## 📁 Estrutura Detalhada do Repositório
O projeto está organizado seguindo a metodologia de ciclo de vida de desenvolvimento de software (SDLC), garantindo rastreabilidade total desde a definição do problema até a entrega final:

### 📂 [01_Definicao](./01_Definicao)
Contém a fundação estratégica do projeto.
- **Definição do Problema:** Análise detalhada dos gargalos operacionais da GlobalShop.
- **Justificativa Tecnológica:** Comparativo técnico entre SQL vs NoSQL para este cenário específico.

### 📂 [02_Modelagem](./02_Modelagem)
Documentação da arquitetura de dados.
- **Design de Esquema:** Definição de coleções e estruturas de documentos.
- **Estratégia de Performance:** Explicação técnica sobre a escolha de *Embedding* vs *Referencing* para otimização de leitura em BI.

### 📂 [03_Implementacao](./03_Implementacao)
A camada técnica e operacional.
- **Dataset Sintético:** Conjunto de dados em JSON simulando cenários reais de mercado (incluindo regionalismos e variabilidade de notas).
- **Engine de Agregação:** Scripts de processamento utilizando o *Aggregation Framework* do MongoDB para a extração de KPIs.

### 📂 [04_BI_Analysis](./04_BI_Analysis)
A camada de tradução de dados em decisões.
- **Mapeamento de KPIs:** Definição de métricas como *Net Sentiment Score* e *Churn Predictor*.
- **Design de Dashboards:** Especificações visuais para a implementação em ferramentas de BI (Power BI/Tableau).

### 📂 [05_Entrega](./05_Entrega)
O resultado final consolidado.
- **Relatório Técnico Formal:** Documento académico-profissional com todas as conclusões, metodologias e validações do projeto.

---

## 🛠️ Guia de Implementação Técnica

### 📋 Pré-requisitos do Ambiente
Para reproduzir este projeto, é necessário instalar:
1. **MongoDB Community Server (v5.0+):** O motor de base de dados.
2. **MongoDB Compass:** A interface de gestão visual para a execução das pipelines de agregação.
3. **Ferramenta de BI (Opcional):** Power BI Desktop ou Tableau Public para a visualização dos resultados.

### 🚀 Fluxo de Execução Passo a Passo
1. **Provisionamento:** Iniciar o serviço do MongoDB e conectar via Compass.
2. **Criação do Namespace:** Criar a Database `GlobalShop` e a Collection `reviews`.
3. **Ingestão de Dados:** 
   - Aceder a `Add Data` $\rightarrow$ `Import JSON`.
   - Carregar o ficheiro `03_Implementacao/dataset_exemplo.json`.
4. **Execução de Analytics:** 
   - Abrir a aba `Aggregations`.
   - Implementar sequencialmente as pipelines descritas em `03_Implementacao/Queries_BI.md`.
5. **Visualização:** Exportar os resultados das queries para CSV e importar no Power BI para gerar os dashboards previstos em `04_BI_Analysis`.

## 📈 KPIs e Valor Agregado
O sistema não se limita a contar estrelas; ele implementa:
- **Detecção de Anomalias:** Identificação automática de produtos cuja nota média caiu mais de 20% numa semana.
- **Análise de Causa Raiz:** Cruzamento de palavras-chave negativas com categorias de produto para isolar falhas logísticas de falhas de fabrico.
- **Segmentação de Cliente:** Análise de sentimento diferenciada para clientes *Gold* vs *Bronze*.
