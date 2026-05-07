# GlobalShop: Sistema de Análise de Sentimentos e Inteligência de Negócio

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD) | **Ano Letivo:** 2025/2026

Este projeto consiste no design, implementação e análise de uma infraestrutura de dados **NoSQL** com suporte a **dados espaciais**, integrada com Business Intelligence (BI) para a empresa fictícia **GlobalShop** — um marketplace de e-commerce que opera em Portugal Continental, com cobertura das cidades de Lisboa, Porto, Coimbra, Braga, Faro e Setúbal.

O objetivo central é resolver o problema de "silos de dados não estruturados", transformando avaliações de clientes em decisões estratégicas de qualidade, experiência do utilizador e **inteligência geográfica de satisfação**.

---

## Visão Geral do Ecossistema

O sistema opera num cenário de **Big Data**, combinando duas tecnologias de base de dados numa solução unificada:

1. **MongoDB (NoSQL):** Base de dados orientada a documentos com schema dinâmico, ideal para reviews com atributos variados por categoria de produto.
2. **MongoDB Geospatial (Espacial):** O índice `2dsphere` sobre campos GeoJSON transforma o MongoDB numa base de dados espacial nativa, habilitando operadores como `$geoNear`, `$geoWithin` e `$near` para análise geográfica da satisfação por cidade e região.

---

## Estrutura do Repositório

```
TABD/
├── app_bi.py                        # Dashboard Streamlit — 4 abas interativas
├── requirements.txt                 # Dependências Python com versões mínimas
├── INSTALL.md                       # Guia completo de instalação e execução
├── README.md                        # Este ficheiro
├── 01_Definicao/
│   └── Definicao_Projeto.md         # Cenário de negócio, problema, justificativa NoSQL + Espacial
├── 02_Modelagem/
│   └── Modelagem_Dados.md           # Schema GeoJSON, coordenadas de Portugal, estratégia de embedding e índices
├── 03_Implementacao/
│   ├── dataset_exemplo.json         # 25 reviews com coordenadas GeoJSON (cidades portuguesas)
│   └── Queries_BI.md                # 9 pipelines de agregação MongoDB (5 analíticas + 4 geoespaciais)
├── 04_BI_Analysis/
│   └── Planeamento_BI.md            # KPIs, especificações do dashboard, stack tecnológico
└── 05_Entrega/
    ├── Relatorio_Final.md           # Relatório técnico final consolidado
    └── Guiao_Apresentacao.md        # Guião detalhado para a apresentação oral
```

---

## Instalação Rápida

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Lançar o dashboard
streamlit run app_bi.py
```

O browser abrirá automaticamente em `http://localhost:8501`. Para configuração completa do MongoDB e criação dos índices espaciais, consulte `INSTALL.md`.

---

## Dashboard BI — 4 Abas Interativas

| Aba | Público-Alvo | Conteúdo |
| :--- | :--- | :--- |
| 📊 **Visão Executiva** | CEOs / Diretores | NSS Global, Quality Decay Rate, tendência mensal, distribuição de sentimento |
| 🏷️ **Análise Tática** | Gestores de Categoria | Sentimento por categoria, top produtos críticos, performance por marca |
| 🔍 **Análise Operacional** | Analistas de Qualidade | Word Cloud de keywords negativas, anomaly detection (quedas abruptas de rating) |
| 🗺️ **Análise Geoespacial** | Diretores de Logística | Mapa interativo de NSS por cidade portuguesa, Geographic Sentiment Index, resumo regional |

---

## KPIs Implementados

- **Net Sentiment Score (NSS):** $(\% \text{Positive}) - (\% \text{Negative})$ — polaridade emocional global e por cidade.
- **Quality Decay Rate (QDR):** Variação da nota média dos últimos 30 dias vs. histórico — deteta lotes defeituosos.
- **Anomaly Detection:** Identifica produtos com queda de rating ≥ 30% entre meses consecutivos.
- **Keyword Correlation Index (KCI):** Correlação entre keywords negativas e notas baixas — isola a causa raiz.
- **Geographic Sentiment Index (GSI):** NSS calculado por cidade e visualizado em mapa interativo de Portugal.

---

## Tecnologias Utilizadas

| Componente | Tecnologia | Papel |
| :--- | :--- | :--- |
| Base de Dados NoSQL | MongoDB | Armazenamento de documentos com schema dinâmico |
| Base de Dados Espacial | MongoDB + índice `2dsphere` | Queries geoespaciais sobre GeoJSON |
| Formato de Dados | GeoJSON (RFC 7946) | Representação padronizada de localizações geográficas |
| Dashboard | Streamlit | Interface interativa de BI |
| Visualizações | Plotly Express | Gráficos interativos e mapa scatter_mapbox |
| NLP Básico | WordCloud + Matplotlib | Visualização de keywords negativas |
| Processamento | Pandas | Transformação e agregação de dados |
| Driver Python | pymongo | Conexão ao MongoDB em modo produção |

---

## Exemplo de Query Geoespacial (MongoDB)

```javascript
// Reviews num raio de 100 km de Lisboa
db.reviews.find({
  "customer.location.coordinates": {
    $nearSphere: {
      $geometry: { type: "Point", coordinates: [-9.1393, 38.7223] },
      $maxDistance: 100000
    }
  }
})
```

---

## Valor Estratégico

O sistema permite à GlobalShop Portugal:
- Detetar **problemas de qualidade em minutos**, não em dias.
- Identificar se um problema é **nacional ou logístico regional** (via mapa de sentimento por cidade).
- Priorizar **ações corretivas baseadas em evidências geográficas** — ex: auditar transportadora em Faro se o NSS do Algarve for < -30%.
- Monitorizar **decaimento de qualidade por lote** antes que se torne viral nas redes sociais.
