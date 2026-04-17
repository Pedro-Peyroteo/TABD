# Planeamento Estratégico de Business Intelligence (BI)

Esta secção detalha a camada de tradução de dados em inteligência. O objetivo não é apenas a visualização de dados, mas a criação de um **Decision Support System (DSS)** que permita à gestão da GlobalShop tomar decisões baseadas em evidências.

## 1. Definição de Métricas e KPIs (Key Performance Indicators)

Para medir o sucesso da operação, definimos três métricas principais:

### 1.1. Net Sentiment Score (NSS)
Diferente da nota média, o NSS mede a polaridade emocional.
- **Fórmula:** $\frac{(\% \text{Positive}) - (\% \text{Negative})}{100}$
- **Interpretação:** Um NSS positivo indica que a marca é amada; um NSS negativo indica risco de churn (perda de clientes).

### 1.2. Quality Decay Rate (Taxa de Decaimento de Qualidade)
Monitora a queda de notas de produtos ao longo do tempo.
- **Métrica:** Diferença entre a nota média dos últimos 30 dias vs. a nota histórica.
- **Objetivo:** Detetar lotes de produtos defeituosos antes que se tornem virais.

### 1.3. Keyword Correlation Index (KCI)
Mapeia a correlação entre palavras-chave negativas e a nota final.
- **Exemplo:** Se a keyword "entrega" aparece em 80% das reviews de nota 1, a falha é logística e não de produto.

## 2. Especificações Técnicas do Dashboard

O Dashboard será dividido em três visões complementares, desenhadas para diferentes níveis de gestão.

### Visão A: Executive Summary (Para CEOs/Diretores)
- **Objetivo:** Visão macro da saúde da empresa.
- **Visualizações:**
    - **Gauge Chart:** NSS Global da empresa.
    - **Treemap:** Distribuição de sentimentos por categoria (Tamanho do bloco = Volume de reviews; Cor = Sentimento).
    - **Big Number:** Total de reviews processadas em tempo real.

### Visão B: Category Manager View (Para Gestores de Departamento)
- **Objetivo:** Gestão tática de categorias.
- **Visualizações:**
    - **Stacked Bar Chart:** Comparação de sentimentos entre marcas da mesma categoria.
    - **Line Chart:** Evolução da nota média mensal por categoria.
    - **Filtros Dinâmicos:** Filtro por Região (ex: Luanda, Benguela) e Nível de Membro (Gold, Silver, Bronze).

### Visão C: Operational Root Cause (Para Analistas de Qualidade)
- **Objetivo:** Resolução de problemas específicos.
- **Visualizações:**
    - **Word Cloud:** Frequência de palavras-chave em reviews negativas.
    - **Scatter Plot:** Correlação entre o tempo de entrega e a nota final.
    - **Top 10 Table:** Lista de produtos com a maior queda de rating na última semana.

## 3. Fluxo de Dados (Data Pipeline)
A arquitetura segue o modelo ELT (Extract, Load, Transform):
1. **Extract:** Coleta de reviews via API/Logs.
2. **Load:** Ingestão bruta no MongoDB (Camada *Bronze*).
3. **Transform:** Aplicação das pipelines de agregação para gerar métricas (Camada *Silver*).
4. **Visualize:** Consumo dos dados processados pelo Power BI (Camada *Gold*).

## 4. Plano de Ação Baseado em Dados
O sistema implementa a seguinte lógica de resposta:
- **Alerta Vermelho:** Se NSS de um produto $\le$ -20% $\rightarrow$ Notificar Gestor de Qualidade $\rightarrow$ Bloquear venda do lote.
- **Alerta Amarelo:** Se keyword "Atraso" aumentar 15% $\rightarrow$ Notificar Logística $\rightarrow$ Auditar transportadora.
