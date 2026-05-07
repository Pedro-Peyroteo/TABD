# Planeamento Estratégico de Business Intelligence (BI)

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD)
**Ano Letivo:** 2025/2026

---

O objetivo desta camada não é apenas a visualização de dados, mas a criação de um **Sistema de Suporte à Decisão (DSS)** que permita à gestão da GlobalShop Portugal tomar decisões baseadas em evidências, integrando a dimensão geoespacial da satisfação dos clientes numa visão operacional acionável.

---

## 1. Definição de Métricas e KPIs

Foram definidas cinco métricas principais, cobrindo as dimensões de sentimento, qualidade, causa raiz e geografia.

### 1.1 Net Sentiment Score (NSS)

Mede a polaridade emocional agregada, diferenciando-se da nota média por capturar a distribuição de sentimentos extremos.

$$\text{NSS} = (\% \text{Positive}) - (\% \text{Negative})$$

**Interpretação:** Um NSS positivo indica que a marca gera mais promotores do que detratores. Um NSS negativo assinala risco de churn e deterioração da reputação. Calculado globalmente e por cidade portuguesa para a componente geoespacial.

### 1.2 Quality Decay Rate (QDR)

Monitoriza a deterioração da perceção de qualidade ao longo do tempo.

$$\text{QDR} = \frac{\bar{r}_{30d} - \bar{r}_{hist}}{\bar{r}_{hist}} \times 100\%$$

Onde $\bar{r}_{30d}$ é a nota média dos últimos 30 dias e $\bar{r}_{hist}$ é a nota média do período anterior. Um QDR de -30% ou inferior constitui um alerta crítico que pode indicar um lote defeituoso em circulação.

### 1.3 Keyword Correlation Index (KCI)

Correlaciona palavras-chave com sentimento negativo, permitindo isolar a causa raiz de um problema.

$$\text{KCI}(k) = \frac{\text{ocorrências de } k \text{ em reviews Negative}}{\text{total de ocorrências de } k} \times 100\%$$

**Exemplo aplicado:** Se a keyword "sobreaquecimento" apresenta KCI = 95%, o problema é de hardware — não de logística ou entrega. Esta distinção é crítica para direcionar a ação corretiva ao departamento certo.

### 1.4 Geographic Sentiment Index (GSI)

Extensão geoespacial do NSS: o índice de sentimento é calculado por cidade e representado visualmente num mapa interativo.

**Lógica de decisão:**
- Cidades com GSI positivo → satisfação com produto e entrega na região.
- Cidades com GSI negativo → potencial falha logística regional ou concentração de lote defeituoso.
- GSI negativo numa única cidade + keyword "atraso" → auditar parceiro de entrega regional.
- GSI negativo em múltiplas cidades + keyword "defeito" → problema de produto de âmbito nacional.

### 1.5 Anomaly Score — Deteção Automática de Lotes Defeituosos

Identifica automaticamente produtos com queda de rating superior a 30% entre dois meses consecutivos.

**Regras de classificação:**

| Queda de Rating | Classificação | Ação Recomendada |
| :--- | :--- | :--- |
| ≥ 30% | 🔴 Crítico | Alerta imediato ao gestor de qualidade; análise de lote |
| 10–29% | 🟡 Atenção | Monitorização aumentada; revisão de fornecedor |
| < 10% | 🟢 Estável | Sem ação necessária |

---

## 2. Arquitetura do Dashboard

O dashboard está organizado em quatro visões complementares, cada uma orientada a um perfil de utilizador distinto.

### Visão A — Executiva (Diretores / CEO)

**Objetivo:** Panorama macro da saúde da plataforma em Portugal.

Componentes:
- **5 KPI Cards:** NSS Global, Total de Reviews, Nota Média Global, Compras Verificadas (%), Quality Decay Rate com indicador colorido.
- **Gráfico de Rosca (Donut):** Distribuição percentual de sentimentos (Positive / Neutral / Negative).
- **Gráfico de Linha Temporal:** Evolução da nota média mensal com linha de limite crítico (3.0).

**Pergunta respondida:** "A plataforma está a melhorar ou a deteriorar-se? Há sinais de alerta este mês?"

---

### Visão B — Tática (Gestores de Categoria / Merchandising)

**Objetivo:** Gestão de desempenho por produto, categoria e marca.

Componentes:
- **Histograma Agrupado:** Distribuição de sentimentos por categoria de produto.
- **Ranking de Produtos Críticos:** Top 10 produtos com nota média mais baixa, com escala de cor RdYlGn.
- **Performance por Marca:** Nota média por marca com NSS como escala de cor.

**Pergunta respondida:** "Qual categoria tem mais insatisfação? Qual produto específico está em alerta?"

---

### Visão C — Operacional (Analistas de Qualidade / Suporte)

**Objetivo:** Resolução de problemas específicos e deteção de anomalias de lote.

Componentes:
- **Word Cloud:** Frequência visual das palavras-chave em reviews negativas (colormap Reds).
- **Top 10 Keywords Negativas:** Gráfico de barras horizontal com frequência de ocorrência.
- **Tabela de Anomaly Detection:** Produtos com maior queda de rating mês a mês, com alerta 🔴/🟡/🟢.

**Pergunta respondida:** "Qual é a causa raiz da insatisfação? Há lotes defeituosos em circulação?"

---

### Visão D — Geoespacial (Diretores de Logística / Operações Regionais)

**Objetivo:** Análise territorial da satisfação e deteção de falhas logísticas regionais em Portugal.

Componentes:
- **Mapa de Bolhas Interativo (scatter_mapbox):** Cada bolha representa uma cidade portuguesa; o tamanho indica o volume de reviews e a cor indica o NSS (verde = satisfeito, vermelho = insatisfeito). Powered by MongoDB Geospatial (índice `2dsphere`).
- **NSS por Cidade:** Gráfico de barras horizontal ordenado por NSS, com linha de referência zero.
- **Volume e Nota Média por Cidade:** Barras verticais com número de reviews e nota média por cidade.
- **Tabela de Resumo Regional:** NSS, nota média, total de reviews e distribuição de sentimentos por cidade.

**Pergunta respondida:** "Em que região de Portugal está a insatisfação concentrada? O problema é nacional ou logístico regional?"

---

## 3. Filtros Dinâmicos (Sidebar)

O dashboard implementa três filtros de cross-filtragem aplicados globalmente a todas as abas:

| Filtro | Campo MongoDB | Valores Possíveis |
| :--- | :--- | :--- |
| Categoria | `product.category` | Eletrónicos, Moda, Casa, Livros |
| Membership | `customer.membership` | Gold, Silver, Bronze |
| Localização | `customer.location.city` | Lisboa, Porto, Coimbra, Braga, Faro, Setúbal |

---

## 4. Stack Tecnológico

| Componente | Tecnologia | Versão Mínima | Papel |
| :--- | :--- | :--- | :--- |
| Base de Dados NoSQL | MongoDB | 6.0+ | Armazenamento de documentos com schema dinâmico |
| Índice Espacial | MongoDB `2dsphere` | 6.0+ | Queries geoespaciais sobre GeoJSON |
| Formato Espacial | GeoJSON (RFC 7946) | — | Representação padronizada de localizações |
| Interface BI | Streamlit | 1.32+ | Dashboard interativo web |
| Visualizações | Plotly Express | 5.20+ | Gráficos interativos e mapa scatter_mapbox |
| Word Cloud | WordCloud + Matplotlib | 1.9.3+ | Visualização de keywords negativas |
| Processamento | Pandas | 2.2+ | Transformação e agregação de dados em memória |
| Driver Python | pymongo | 4.6+ | Conexão ao MongoDB (modo produção) |

---

## 5. Cenário de Uso: Deteção de Lote Defeituoso

O seguinte fluxo operacional ilustra o valor do DSS no contexto da GlobalShop Portugal:

1. **Aba 1 (Executiva):** O Quality Decay Rate aparece a -33% → sinal de alerta nacional.
2. **Aba 3 (Operacional):** A tabela de anomalias identifica o Smartphone X1 com queda de 33% em Abril. O Word Cloud mostra "sobreaquecimento", "defeito" e "bateria" como termos dominantes.
3. **Aba 3 (KCI):** O KCI de "sobreaquecimento" = 95% → confirma falha de hardware, não de entrega.
4. **Aba 4 (Geoespacial