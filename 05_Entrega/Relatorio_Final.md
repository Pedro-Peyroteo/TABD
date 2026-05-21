# Relatorio Tecnico Final: FitMap

**UC:** Tecnologias e Aplicacoes de Bases de Dados (TABD) | **Ano letivo:** 2025/2026

> O relatorio completo encontra-se em formato Word: `Relatorio_FitMap.docx` (raiz do repositorio).
> Este ficheiro e um resumo executivo em Markdown.

---

## Resumo

O **FitMap** e uma plataforma WebSIG funcional para descoberta de instalacoes desportivas em Portugal. Integra 3 390 instalacoes reais do OpenStreetMap, armazenadas no MongoDB 7 com indice `2dsphere`, servidas por uma API FastAPI e visualizadas num mapa Leaflet interativo.

---

## Arquitetura

```
OpenStreetMap (Overpass API)
        |
   seed_osm.py  (ETL Python)
        |
   MongoDB 7  (colecao facilities, indice 2dsphere)
        |
   FastAPI  (9 endpoints REST)
        |
   Leaflet SPA  +  OSRM routing  +  Nominatim geocoding
```

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Base de dados | MongoDB 7, indice `2dsphere` |
| Backend | FastAPI + uvicorn + pymongo |
| Frontend | Leaflet 1.9 + Leaflet.draw + Routing Machine |
| Routing | OSRM (car / foot / bike) |
| Geocoding | Nominatim com cache local |
| Orquestracao | Docker Compose v2 |

---

## Queries MongoDB Implementadas

| Operacao | Endpoint | Pipeline |
|---|---|---|
| Proximidade | `/api/geo/nearby` | `$geoNear` |
| Area poligonal | `/api/geo/within` | `$geoWithin` + `$facet` |
| KPIs globais | `/api/overview` | `$facet` (5 sub-pipelines) |
| Modalidades | `/api/sports` | `$unwind` + `$group` |
| Cidades | `/api/cities` | `$group` + `$sort` |

---

## Resultados

- **3 390** instalacoes georreferenciadas em **234+** municipios
- Latencia media das queries geoespaciais: **45–80 ms** (Docker local)
- Auto-expansao de raio GPS: 3→5→10→25→50→100 km
- Routing multimodal integrado (carro, a pe, bicicleta)
- Selecao poligonal com breakdown por categoria em tempo real

---

## Limitacoes e Trabalho Futuro

- Cobertura OSM varia por regiao (interior sub-representado)
- Sem autenticacao nem CRUD para utilizadores finais
- OSRM publico com rate limits — instancia local recomendada para producao
- Camada de transportes publicos (bus_stops OSM) nao implementada
- Clustering de marcadores em zoom baixo (Leaflet.markercluster)
