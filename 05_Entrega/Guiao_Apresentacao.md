# Guião de Apresentação
## GlobalShop: Sistema NoSQL + Espacial de Business Intelligence

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD)
**Ano Letivo:** 2025/2026

> **Como usar este guião:** Cada secção corresponde a um momento da apresentação.
> Tempo estimado total: **15–20 minutos**
> Antes de começar: executar `streamlit run app_bi.py` e manter o browser aberto em `http://localhost:8501`.

---

## SLIDE 1 — Título (30 seg)

**Dizer:**
> "O nosso projeto chama-se GlobalShop Sentiment Intelligence. O objetivo é transformar avaliações de clientes em decisões de negócio — em minutos, não em dias. Para isso, combinamos duas tecnologias de base de dados: o MongoDB como base de dados NoSQL orientada a documentos, e o mesmo MongoDB como base de dados espacial, através do índice `2dsphere` e do padrão GeoJSON. O caso de uso é o mercado português, com cobertura de Lisboa, Porto, Coimbra, Braga, Faro e Setúbal."

---

## SLIDE 2 — Problema de Negócio (1–2 min)

**Contexto:**
A GlobalShop é um marketplace que opera em Portugal Continental. Recebe centenas de avaliações diárias, mas enfrenta três problemas operacionais críticos:

| Problema | Consequência |
| :--- | :--- |
| Deteta defeitos de produto com dias de atraso | Aumento de devoluções e perda de reputação |
| Não sabe em que região do país a insatisfação é maior | Decisões logísticas sem suporte geográfico |
| Não consegue isolar causa raiz (produto vs. entrega) | Ações corretivas direcionadas ao departamento errado |

**Dizer:**
> "Imaginem que um lote defeituoso de smartphones chega ao mercado. Sem o nosso sistema, a empresa demora dias a perceber que algo está errado. Com o DSS que implementámos, em minutos conseguimos ver: que o Smartphone X1 caiu 50% de rating em Abril; que a causa raiz é 'sobreaquecimento' e 'defeito' de hardware, não de logística; e que o problema está geograficamente concentrado em Braga e Faro. Isto permite uma ação corretiva precisa e imediata."

---

## SLIDE 3 — Por que NoSQL + Espacial? (2 min)

### Por que MongoDB (NoSQL)?

| Critério | SQL | MongoDB (NoSQL) |
| :--- | :--- | :--- |
| Esquema | Rígido — migrações dispendiosas | Dinâmico — novos atributos sem alteração |
| Escalabilidade | Vertical (hardware mais caro) | Horizontal — sharding nativo |
| Agregação | JOINs pesados entre tabelas normalizadas | Documentos auto-contidos — O(1) |

> "Cada review de eletrónicos tem atributos técnicos; cada review de moda fala de tamanho e tecido. Num modelo relacional, precisaríamos de dezenas de colunas nulas. No MongoDB, cada documento tem o schema que precisa."

### Por que MongoDB Geospatial (Base de Dados Espacial)?

> "Em vez de adicionar o PostGIS ao PostgreSQL — o que implicaria gerir um segundo sistema — o MongoDB suporta GeoJSON nativamente através do índice `2dsphere`. Isso significa que podemos fazer, na mesma pipeline de agregação, uma query como: 'qual é o NSS das reviews originadas num raio de 100 km de Lisboa?'. Uma única infraestrutura, zero configuração adicional."

**Mostrar o campo de localização no `dataset_exemplo.json`:**
```json
"location": {
  "city": "Braga",
  "country": "Portugal",
  "coordinates": { "type": "Point", "coordinates": [-8.4261, 41.5454] }
}
```

---

## SLIDE 4 — Arquitetura da Solução (1 min)

```
Reviews (GeoJSON Portugal) → MongoDB (NoSQL + 2dsphere) → Aggregation Pipelines → Streamlit Dashboard
```

**Três camadas:**
- **Bronze:** Ingestão bruta no MongoDB com índice espacial `2dsphere` ativo.
- **Silver:** Transformação via Aggregation Framework — NSS, QDR, KCI, queries espaciais.
- **Gold:** Visualização no dashboard com mapa interativo de Portugal.

---

## SLIDE 5 — DEMO AO VIVO: Dashboard (8–10 min)

> Abrir o browser em `http://localhost:8501`

### Aba 1 — Visão Executiva
**Mostrar e comentar:**
- **NSS Global:** "Mede a polaridade emocional. NSS positivo significa que a plataforma tem mais promotores do que detratores."
- **Quality Decay Rate:** "Compara os últimos 30 dias com o histórico. O valor negativo aqui é o primeiro sinal de alerta — algo deteriorou-se recentemente."
- **Gráfico de linha mensal:** "Vemos a nota a descer consistentemente a partir de Março — padrão claro de deterioração."

### Aba 2 — Análise Tática
**Mostrar e comentar:**
- "Aqui os gestores de categoria veem quais departamentos têm mais sentimentos negativos — Eletrónicos destaca-se."
- Apontar o **Smartphone X1** no gráfico de produtos críticos: "Este produto está em zona crítica. Nota média abaixo de 2.0, o que é extremamente preocupante."

### Aba 3 — Análise Operacional
**Mostrar e comentar:**
- **Word Cloud:** "As palavras maiores são as mais frequentes nas reviews negativas. 'Sobreaquecimento', 'defeito' e 'bateria' dominam — apontam inequivocamente para um problema de hardware."
- **Tabela de Anomaly Detection:** "O Smartphone X1 tem uma queda de 50% — classificado como 🔴 Crítico. Este é o gatilho automático para o gestor de qualidade."

### Aba 4 — Análise Geoespacial ⭐ (ponto diferenciador)
**Mostrar e comentar:**
- **Mapa de bolhas:** "Cada bolha é uma cidade portuguesa. O tamanho representa o volume de reviews, a cor representa o NSS — verde é satisfação, vermelho é insatisfação. Braga e Faro aparecem a vermelho — é aqui que o lote defeituoso está concentrado."
- **NSS por cidade:** "Conseguimos ver instantaneamente quais regiões de Portugal têm clientes mais insatisfeitos."
- **Resumo regional:** "Um diretor de logística usa esta tabela para decidir se deve auditar o parceiro de entrega regional do Algarve ou se o problema é nacional."

---

## SLIDE 6 — Queries Geoespaciais MongoDB (1 min)

**Mostrar o código de `Queries_BI.md` e dizer:**

> "Estas queries só são possíveis porque criámos o índice `2dsphere`. Por exemplo, esta query recupera todas as reviews de clientes num raio de 100 km de Lisboa — usando geometria esférica real, em haversine."

```javascript
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

## SLIDE 7 — KPIs Implementados (30 seg)

| KPI | Fórmula | Onde no Dashboard |
| :--- | :--- | :--- |
| NSS | (% Positive) − (% Negative) | Tab 1 + Tab 4 |
| Quality Decay Rate | (média 30d − média hist.) / hist. × 100% | Tab 1 |
| Anomaly Detection | Queda ≥ 30% entre meses consecutivos | Tab 3 |
| Keyword Correlation Index | % ocorrências negativas por keyword | Tab 3 + Queries_BI.md |
| Geographic Sentiment Index | NSS calculado por cidade — visualizado no mapa | Tab 4 |

---

## SLIDE 8 — Conclusões (1 min)

**Dizer:**
> "O projeto demonstra que o MongoDB pode servir simultaneamente como base de dados NoSQL para dados não estruturados e como base de dados espacial para análise geográfica — sem infraestrutura adicional, usando GeoJSON como standard aberto. O resultado é um DSS que reduz o tempo de deteção de problemas de dias para minutos, e que acrescenta a dimensão geográfica à análise de satisfação — algo que um SQL clássico não consegue sem extensões complexas."

**Resultados concretos do projeto:**
- ✅ Lote defeituoso detetado automaticamente — Smartphone X1, Abril 2026, queda de 50%.
- ✅ Causa raiz identificada via KCI: `sobreaquecimento` + `defeito` (hardware, não logística).
- ✅ Dimensão geográfica: mapa de NSS por cidade de Portugal Continental.
- ✅ 9 pipelines MongoDB documentadas (5 analíticas + 4 geoespaciais).
- ✅ Dashboard com 4 visões orientadas a CEO, gestores de categoria, analistas de qualidade e diretores de logística.

---

## Possíveis Perguntas e Respostas

**P: Por que não usaram PostGIS em vez do MongoDB Geos