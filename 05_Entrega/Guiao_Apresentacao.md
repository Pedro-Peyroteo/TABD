# Guião de Apresentação
## GlobalShop: Sistema NoSQL + Espacial de Business Intelligence

> **Como usar este guião:** Cada secção corresponde a um momento da apresentação.  
> Tempo estimado total: **15–20 minutos**  
> Antes de começar: executar `streamlit run app_bi.py` e manter o browser aberto.

---

## SLIDE 1 — Título (30 seg)

**Dizer:**  
> "O nosso projeto chama-se GlobalShop Sentiment Intelligence. O objetivo é simples: transformar avaliações de clientes em decisões de negócio — e fazê-lo em minutos, não em dias. Para isso, combinámos duas tecnologias de base de dados: MongoDB como base de dados NoSQL, e o mesmo MongoDB como base de dados espacial, através do seu índice 2dsphere."

---

## SLIDE 2 — Problema de Negócio (1–2 min)

**Contexto:**  
A GlobalShop é um marketplace que opera em Angola (Luanda, Benguela, Huambo, Lubango, Malanje, Cabinda). Recebe milhares de avaliações diárias, mas tem três problemas críticos:

| Problema | Consequência |
| :--- | :--- |
| Deteta defeitos de produto com dias de atraso | Aumento de devoluções |
| Não sabe em que cidade a insatisfação é maior | Decisões logísticas cegas |
| Não consegue isolar causa raiz (produto vs. entrega) | Ações corretivas erradas |

**Dizer:**  
> "Imaginem que um lote defeituoso de smartphones chega ao mercado. Sem o nosso sistema, a empresa demora dias a perceber que algo está errado. Com o nosso DSS, em minutos conseguimos ver que a nota do Smartphone X1 caiu 50% em Abril, que a causa raiz é 'sobreaquecimento' e 'defeito', e que o problema está concentrado em Lubango e Malanje — o que aponta para um problema de transporte ou armazenamento específico a essa rota."

---

## SLIDE 3 — Por que NoSQL + Espacial? (2 min)

### Por que MongoDB (NoSQL)?

| Critério | SQL | MongoDB |
| :--- | :--- | :--- |
| Esquema | Rígido | Flexível (ideal para reviews variadas por categoria) |
| Escalabilidade | Vertical | Horizontal (Big Data) |
| Agregação | JOINs pesados | Documentos auto-contidos — O(1) |

### Por que MongoDB Geospatial (BD Espacial)?

> "Em vez de usar um sistema separado como o PostGIS, o MongoDB tem suporte nativo a GeoJSON através do índice `2dsphere`. Isso significa que podemos fazer, na mesma pipeline, uma query como: 'qual é a satisfação média das reviews originadas num raio de 200 km de Luanda?' — sem infraestrutura extra."

**Mostrar** o campo de localização no `dataset_exemplo.json`:
```json
"location": {
  "city": "Lubango",
  "coordinates": { "type": "Point", "coordinates": [13.4920, -14.9177] }
}
```

---

## SLIDE 4 — Arquitetura da Solução (1 min)

```
Reviews (GeoJSON) → MongoDB (NoSQL + 2dsphere) → Aggregation Pipelines → Streamlit Dashboard
```

Três camadas:
1. **Bronze:** Ingestão bruta no MongoDB com índice espacial ativo.
2. **Silver:** Transformação via Aggregation Framework (NSS, QDR, KCI, spatial).
3. **Gold:** Visualização no dashboard com mapa interativo.

---

## SLIDE 5 — DEMO AO VIVO: Dashboard (8–10 min)

> Abrir o browser em `http://localhost:8501`

### Aba 1 — Visão Executiva
**Mostrar e comentar:**
- **NSS (Net Sentiment Score):** "Mede a polaridade emocional. Um NSS positivo significa que a empresa está saudável emocionalmente."
- **Quality Decay Rate:** "Compara os últimos 30 dias com o histórico anterior. Um valor negativo é sinal de alerta."
- **Gráfico de linha mensal:** "Conseguimos ver a tendência de satisfação ao longo do tempo."

### Aba 2 — Análise Tática
**Mostrar e comentar:**
- "Aqui os gestores de categoria veem quais departamentos têm mais sentimentos negativos."
- Apontar o **Smartphone X1** no gráfico de produtos críticos: "Este produto está em alerta. Nota média abaixo do limite crítico de 3.0."

### Aba 3 — Análise Operacional
**Mostrar e comentar:**
- **Word Cloud:** "As palavras maiores são as mais frequentes em reviews negativas. Vemos claramente 'sobreaquecimento', 'defeito', 'bateria'."
- **Tabela de Anomaly Detection:** "O Smartphone X1 tem uma queda de 50% — marcado a 🔴 Crítico. Isto é o que dispara o alerta automático para o gestor de qualidade."

### Aba 4 — Análise Geoespacial ⭐ (ponto diferenciador)
**Mostrar e comentar:**
- **Mapa de bolhas:** "Cada bolha é uma cidade. O tamanho representa o volume de reviews, a cor representa o NSS — verde é satisfação, vermelho é insatisfação. Isto é a BD Espacial em ação."
- **Barras de NSS por cidade:** "Conseguimos ver instantaneamente quais cidades têm clientes mais insatisfeitos."
- **Resumo regional:** "Um diretor de logística pode usar esta tabela para priorizar auditorias regionais."

---

## SLIDE 6 — Queries Geoespaciais MongoDB (1 min)

**Mostrar o código de `Queries_BI.md` e dizer:**

> "Estas queries só são possíveis porque temos o índice `2dsphere` ativo. Por exemplo, esta query encontra todas as reviews originadas num raio de 200 km de Luanda — algo impossível num sistema SQL sem extensão geoespacial."

```javascript
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

## SLIDE 7 — KPIs Implementados (30 seg)

| KPI | Fórmula | Onde |
| :--- | :--- | :--- |
| NSS | (% Positive) − (% Negative) | Tab 1 + Tab 4 |
| Quality Decay Rate | (média 30d − média hist.) / hist. × 100% | Tab 1 |
| Anomaly Detection | Queda ≥ 30% entre meses | Tab 3 |
| Keyword Correlation Index | % ocorrências negativas por keyword | Tab 3 + Queries_BI.md |
| Geographic Sentiment Index | NSS por cidade no mapa | Tab 4 |

---

## SLIDE 8 — Conclusões (1 min)

**Dizer:**
> "O projeto demonstra que o MongoDB pode servir simultaneamente como base de dados NoSQL para dados não estruturados e como base de dados espacial para análise geográfica — sem infraestrutura adicional. O resultado é um DSS que reduz o tempo de deteção de problemas de dias para minutos, e que acrescenta a dimensão geográfica à análise de satisfação."

**Resultados concretos:**
- ✅ Lote defeituoso detetado automaticamente (Smartphone X1, Abril 2026).
- ✅ Causa raiz identificada: `sobreaquecimento` + `defeito` (hardware, não logística).
- ✅ Dimensão geográfica: mapa de NSS por cidade de Angola.
- ✅ 9 pipelines MongoDB documentadas (5 analíticas + 4 espaciais).

---

## Possíveis Perguntas e Respostas

**P: Por que não usaram PostGIS em vez do MongoDB Geospatial?**  
R: "O MongoDB Geospatial elimina a necessidade de um sistema separado. As queries espaciais e analíticas coexistem na mesma pipeline de agregação, usando GeoJSON que é um padrão aberto (RFC 7946). Para o nosso caso de uso — análise de reviews com dimensão geográfica — é a solução mais simples e eficiente."

**P: O sistema funciona com dados reais do MongoDB ou só com JSON?**  
R: "O dashboard foi desenvolvido para leitura direta do JSON (dataset demo). Para produção, bastaria substituir a função `load_data()` por uma query pymongo — a estrutura de dados é idêntica. O guia em `INSTALL.md` documenta os passos de importação e indexação no MongoDB."

**P: Como escala para milhões de reviews?**  
R: "Os índices que criámos garantem complexidade O(log n) nas queries mais pesadas. Para escala horizontal, o MongoDB suporta sharding nativo. A opção `allowDiskUse: true` nas aggregations permite processar volumes que excedem a RAM disponível."

**P: O que significa o Quality Decay Rate negativo?**  
R: "Um QDR de -30% significa que a nota média dos últimos 30 dias caiu 30% face ao histórico anterior. É o trigger para emissão de alerta vermelho e bloqueio preventivo do lote."
