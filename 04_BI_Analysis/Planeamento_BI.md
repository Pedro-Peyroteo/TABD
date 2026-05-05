# Planeamento Estratégico de Business Intelligence (BI)

Esta secção detalha a camada de tradução de dados em inteligência. O objetivo não é apenas a visualização de dados, mas a criação de um **Decision Support System (DSS)** que permita à gestão da GlobalShop tomar decisões baseadas em evidências, incluindo a **dimensão geoespacial** da satisfação dos clientes.

## 1. Definição de Métricas e KPIs (Key Performance Indicators)

Para medir o sucesso da operação, definimos cinco métricas principais:

### 1.1. Net Sentiment Score (NSS)
Diferente da nota média, o NSS mede a polaridade emocional.
- **Fórmula:** $\text{NSS} = (\% \text{Positive}) - (\% \text{Negative})$
- **Interpretação:** Um NSS positivo indica que a marca é amada; um NSS negativo indica risco de churn (perda de clientes).
- **Aplicação Espacial:** Calculado por cidade, permite identificar regiões geograficamente insatisfeitas.

### 1.2. Quality Decay Rate (Taxa de Decaimento de Qualidade)
Monitora a queda de notas de produtos ao longo do tempo.
- **Métrica:** Diferença entre a nota média dos últimos 30 dias vs. a nota histórica.
- **Fórmula:** $\text{QDR} = \frac{\bar{r}_{30d} - \bar{r}_{hist}}{\bar{r}_{hist}} \times 100\%$
- **Objetivo:** Detetar lotes de produtos defeituosos antes que se tornem virais. Um QDR de -30% indica anomalia crítica.

### 1.3. Keyword Correlation Index (KCI)
Mapeia a correlação entre palavras-chave negativas e a nota final.
- **Fórmula:** $\text{KCI}(k) = \frac{\text{ocorrências de } k \text{ em reviews negativas}}{\text{ocorrências totais de } k} \times 100\%$
- **Exemplo:** Se a keyword "sobreaquecimento" aparece em 95% das reviews de nota 1-2, a falha é de hardware e não logística.

### 1.4. Geographic Sentiment Index (GSI)
Índice de satisfação agregado por cidade, visualizado em mapa.
- **Métrica:** NSS calculado por cidade, representado como bolha no mapa (tamanho = volume, cor = NSS).
- **Objetivo:** Identificar se um problema é nacional (todas as cidades afetadas) ou regional (concentrado numa área logística).

### 1.5. Anomaly Score (Detecção de Lote Defeituoso)
Pontuação automática de urgência para cada produto.
- **Trigger:** Queda de rating ≥ 30% em relação ao mês anterior.
- **Ação:** Emissão de alerta para o gestor de qualidade e bloqueio preventivo do lote.

---

## 2. Especificações Técnicas do Dashboard

O Dashboard está dividido em **quatro visões** complementares, desenhadas para diferentes níveis de gestão.

### Visão A: Executive Summary (Para CEOs/Diretores)
**Objetivo:** Visão macro da saúde da empresa.
- **KPI Cards:** NSS Global, Total de Reviews, Nota Média Global, Compras Verificadas.
- **Quality Decay Rate:** Métrica de tendência — comparação nota média dos últimos 30 dias vs. histórico, com indicador colorido (verde/amarelo/vermelho).
- **Gráfico de Rosca:** Distribuição de sentimentos (Positive/Neutral/Negative).
- **Gráfico de Linha:** Evolução da nota média mensal com linha de limite crítico (3.0).

### Visão B: Category Manager View (Para Gestores de Departamento)
**Objetivo:** Gestão tática de categorias e marcas.
- **Stacked Bar Chart:** Distribuição de sentimentos por categoria de produto.
- **Bar Chart:** Top 10 produtos com menor nota média (itens críticos).
- **Bar Chart:** Performance por marca com NSS como escala de cor.

### Visão C: Operational Root Cause (Para Analistas de Qualidade)
**Objetivo:** Resolução de problemas específicos e deteção de anomalias.
- **Word Cloud:** Frequência de palavras-chave em reviews negativas.
- **Bar Chart Horizontal:** Top 10 keywords negativas com frequência.
- **Tabela de Anomalias:** Produtos com maior queda de rating mês a mês (Quality Decay Rate por produto).

### Visão D: Análise Geoespacial (Para Diretores de Logística e Expansão)
**Objetivo:** Identificação de padrões geográficos de satisfação e problemas logísticos.
- **Mapa de Bolhas (Scatter Mapbox):** Cada cidade representada por uma bolha; tamanho = volume de reviews; cor = NSS (verde = satisfeito, vermelho = insatisfeito).
- **Bar Chart Horizontal:** NSS por cidade, ordenado do mais satisfeito ao mais insatisfeito.
- **Tabela de Resumo Regional:** Volume de reviews, nota média e NSS por cidade.

---

## 3. Fluxo de Dados (Data Pipeline)
A arquitetura segue o modelo ELT (Extract, Load, Transform):
1. **Extract:** Coleta de reviews via API/Logs com geolocalização (GeoJSON Point).
2. **Load:** Ingestão bruta no MongoDB com índice `2dsphere` ativo (Camada *Bronze*).
3. **Transform:** Aplicação das pipelines de agregação para gerar métricas de sentimento, decay e KCI (Camada *Silver*).
4. **Visualize:** Consumo dos dados processados pelo dashboard Streamlit com mapa interativo (Camada *Gold*).

---

## 4. Plano de Ação Baseado em Dados

O sistema implementa a seguinte lógica de resposta automática:

| Condição | Alerta | Ação |
| :--- | :--- | :--- |
| NSS de um produto ≤ -20% | 🔴 Vermelho | Notificar Gestor de Qualidade → Bloquear lote |
| Keyword "defeito" aumentar 20% | 🟠 Laranja | Escalar para Engenharia de Produto |
| Keyword "atraso" aumentar 15% numa cidade | 🟡 Amarelo | Notificar Logística → Auditar transportadora regional |
| GSI de uma cidade ≤ -30% | 🔴 Vermelho | Revisão do parceiro logístico na região |
| Quality Decay Rate ≤ -30% | 🔴 Vermelho | Suspensão preventiva do lote + investigação |

---

## 5. Arquitetura Tecnológica

```
┌─────────────────────────────────────────────────────────┐
│                   CAMADA DE DADOS                       │
│  MongoDB (NoSQL + 2dsphere Geospatial Index)            │
│  Coleção: reviews  |  Dataset: 25+ documentos GeoJSON   │
└────────────────────────┬────────────────────────────────┘
                         │ Aggregation Framework
                         ▼
┌─────────────────────────────────────────────────────────┐
│                CAMADA DE PROCESSAMENTO                  │
│  • Sentiment KPIs (NSS, KCI)                            │
│  • Quality Decay Rate                                   │
│  • Anomaly Detection                                    │
│  • Spatial Aggregation ($geoNear, $geoWithin)           │
└────────────────────────┬────────────────────────────────┘
                         │ JSON/pymongo
                         ▼
┌─────────────────────────────────────────────────────────┐
│               CAMADA DE VISUALIZAÇÃO                    │
│  Streamlit Dashboard (Python)                           │
│  • Plotly (charts + scatter_mapbox)                     │
│  • WordCloud  |  Pandas  |  Matplotlib                  │
└─────────────────────────────────────────────────────────┘
```
