# Definicao do Projeto: FitMap

**UC:** Tecnologias e Aplicacoes de Bases de Dados (TABD) | **Ano letivo:** 2025/2026

---

## 1. Problema e Motivacao

Encontrar onde praticar desporto em Portugal — especialmente em cidades desconhecidas ou em modalidades de nicho — e uma tarefa fragmentada. Plataformas como o Google Maps cobrem estabelecimentos comerciais generico, mas oferecem controlo limitado sobre filtros tipologicos (piscinas municipais, dojos de jiu-jitsu, estudios de pilates) e nao integram dados comunitarios auditaveis.

O **FitMap** resolve este problema com uma plataforma WebSIG dedicada a instalacoes desportivas, alimentada por dados abertos do OpenStreetMap e com pesquisa espacial nativa via MongoDB.

---

## 2. Objetivos

- Recolher e normalizar dados reais de instalacoes desportivas em Portugal via Overpass API (OSM)
- Armazenar os dados num SGBD NoSQL documental com suporte geoespacial nativo (MongoDB 7, indice `2dsphere`)
- Expor uma API REST com queries geoespaciais: `$geoNear` (proximidade), `$geoWithin` (poligono), `$facet` (KPIs paralelos)
- Construir uma SPA Leaflet que permita pesquisa por GPS, selecao de area, filtros e calculo de rotas

---

## 3. Justificacao NoSQL + Espacial

### Por que MongoDB?

| Criterio | MongoDB | PostgreSQL + PostGIS |
|---|---|---|
| Schema dos dados OSM | Flexivel — campos opcionais variam por instalacao | Requer ALTER TABLE a cada nova tag |
| Workload | Leituras dominantes, sem OLAP complexo | Melhor para analise pesada multi-tabela |
| Operacoes espaciais | `$geoNear`, `$geoWithin` sobre Points — suficiente | Suporte completo OGC (topologia, buffers) |
| Curva de aprendizagem | Aggregation Pipeline expressivo, drivers nativos | SQL + extensao espacial adicional |

Para o caso de uso do FitMap (pesquisa de pontos proximos, filtros de area, KPIs globais), o MongoDB e a escolha otima.

### Indice 2dsphere

O indice `2dsphere` indexa geometrias GeoJSON sobre uma superficie esferica, considerando a curvatura da Terra. Habilita:

- `$geoNear` — distancia geodesica entre dois pontos em metros
- `$geoWithin` — instalacoes contidas num poligono desenhado pelo utilizador
- `$nearSphere` — alternativa para queries `find()` simples

---

## 4. Fonte de Dados

**OpenStreetMap via Overpass API**

- ~45 000 elementos brutos para Portugal (nodes, ways, relations)
- Apos normalizacao e filtragem (sem nome, sem coordenadas): **3 390 documentos**
- Tags usadas: `leisure=fitness_centre`, `leisure=swimming_pool`, `leisure=sports_centre`, `club=martial_arts`, `sport=*`

**Categorias normalizadas:**

| Categoria | Contagem |
|---|---|
| Centro Desportivo | 1 453 |
| Piscina | 806 |
| Ginasio | 707 |
| Escalada | 253 |
| Outro | 90 |
| Estudio de Danca | 53 |
| Artes Marciais | 22 |
| Yoga / Pilates | 5 |
| Boxe / Kickboxing | 1 |

---

## 5. Stack Tecnologico

```
OpenStreetMap  →  seed_osm.py (ETL)  →  MongoDB 7 (fitmap.facilities)
                                               │
                                          FastAPI (9 endpoints)
                                               │
                                         Leaflet.js SPA
                                          + OSRM routing
                                          + Nominatim geocoding
```
