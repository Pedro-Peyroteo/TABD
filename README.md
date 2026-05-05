# GlobalShop: Sistema Avançado de Análise de Sentimentos e Inteligência de Negócio

Este projeto consiste no design, implementação e análise de uma infraestrutura de dados **NoSQL** com suporte a **dados espaciais**, integrada com Business Intelligence (BI) para a empresa fictícia **GlobalShop**, um marketplace de e-commerce com foco nos mercados africanos de língua portuguesa.

O objetivo central é a resolução do problema de "silos de dados não estruturados", transformando centenas de milhares de feedbacks de clientes em ativos estratégicos para a gestão de qualidade, experiência do utilizador e **inteligência geográfica de satisfação**.

---

## Visão Geral do Ecossistema

O sistema foi concebido para operar num cenário de **Big Data**, combinando duas tecnologias de base de dados numa única solução:

1. **MongoDB (NoSQL):** Base de dados orientada a documentos com esquema dinâmico, ideal para reviews com atributos variados por categoria.
2. **MongoDB Geospatial (Espacial):** O índice `2dsphere` sobre campos GeoJSON transforma o MongoDB numa base de dados espacial nativa, habilitando operadores como `$geoNear`, `$geoWithin` e `$near` para análise geográfica da satisfação de clientes por cidade e região.

---

## Estrutura do Repositório

```
TABD/
├── app_bi.py                      # Dashboard Streamlit — 4 abas interativas
├── requirements.txt               # Dependências Python
├── .gitignore
├── INSTALL.md                     # Guia completo de instalação e execução
├── 01_Definicao/
│   └── Definicao_Projeto.md       # Cenário de negócio, problema, justificativa NoSQL + Espacial
├── 02_Modelagem/
│   └── Modelagem_Dados.md         # Schema GeoJSON, estratégia de embedding, índices
├── 03_Implementacao/
│   ├── dataset_exemplo.json       # 25 reviews com coordenadas GeoJSON (cidades de Angola)
│   └── Queries_BI.md              # Pipelines de agregação MongoDB (analíticas + geoespaciais)
├── 04_BI_Analysis/
│   └── Planeamento_BI.md          # KPIs, especificações do dashboard, arquitetura de dados
└── 05_Entrega/
    └── Relatorio_Final.md         # Relatório técnico final consolidado
```

---

## Pré-requisitos e Instalação Rápida

```bash
# Instalar dependências
pip install -r requirements.txt

# Lançar o dashboard
streamlit run app_bi.py
```

Para configuração completa do MongoDB e criação dos índices espaciais, consulte `INSTALL.md`.

---

## Dashboard BI — 4 Abas Interativas

| Aba | Público-Alvo | Conteúdo |
| :--- | :--- | :--- |
| 📊 **Visão Executiva** | CEOs / Diretores | NSS Global, Quality Decay Rate, tendência mensal, distribuição de sentimento |
| 🏷️ **Análise Tática** | Gestores de Categoria | Sentimento por categoria, top produtos críticos, performance por marca |
| 🔍 **Análise Operacional** | Analistas de Qualidade | Word Cloud de keywords negativas, anomaly detection (quedas abruptas de rating) |
| 🗺️ **Análise Geoespacial** | Diretores de Logística | Mapa interativo de NSS por cidade, Geographic Sentiment Index, resumo regional |

---

## KPIs Implementados

- **Net Sentiment Score (NSS):** $(\% \text{Positive}) - (\% \text{Negative})$ — mede polaridade emocional global e por cidade.
- **Quality Decay Rate:** Variação da nota média dos últimos 30 dias vs. histórico — deteta lotes defeituosos.
- **Anomaly Detection:** Identifica produtos com queda de rating ≥ 30% entre meses consecutivos.
- **Keyword Correlation Index (KCI):** Correlação entre keywords negativas e notas baixas — isola causas raiz.
- **Geographic Sentiment Index (GSI):** NSS calculado por cidade e visualizado em mapa interativo.

---

## Tecnologias Utilizadas

| Componente | Tecnologia | Papel |
| :--- | :--- | :--- |
| Base de Dados NoSQL | MongoDB | Armazenamento de documentos flexíveis |
| Base de Dados Espacial | MongoDB + índice `2dsphere` | Queries geoespaciais sobre GeoJSON |
| Formato de Dados | GeoJSON (RFC 7946) | Representação de localizações geográficas |
| Dashboard | Streamlit | Interface interativa de BI |
| Visualizações | Plotly + Matplotlib | Gráficos e mapa interativo (scatter_mapbox) |
| NLP Básico | WordCloud | Visualização de keywords negativas |
| Processamento | Pandas | Transformação e agregação de dados |

---

## Exemplo de Query Geoespacial (MongoDB)

```javascript
// Reviews num raio de 200 km de Luanda
db.reviews.find({
  "customer.location.coordinates": {
    $nearSphere: {
      $geometry: { type: "Point", coordinates: [13.2343, -8.8368] },
      $maxDistance: 200000
    }
  }
})
```

---

## Valor Estratégico

O sistema permite à GlobalShop:
- Detetar **problemas de qualidade em horas**, não dias.
- Identificar se um problema é **nacional ou logístico regional** (via mapa de sentimento).
- Priorizar **ações corretivas baseadas em evidências geográficas** (ex: auditar transportadora em Malanje se NSS < -30%).
- Monitorizar **decaimento de qualidade por lote** antes que se torne viral.
