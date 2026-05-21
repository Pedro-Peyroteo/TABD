<div align="center">
  <img src="web/static/img/logo.svg" width="60" alt="FitMap Logo"/>
  <h1>FitMap</h1>
  <p><strong>Plataforma WebSIG para Descoberta de Instalacoes Desportivas em Portugal</strong></p>
  <p>
    <img src="https://img.shields.io/badge/MongoDB-7.0-47A248?logo=mongodb&logoColor=white" alt="MongoDB"/>
    <img src="https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/Leaflet-1.9-199900?logo=leaflet&logoColor=white" alt="Leaflet"/>
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker"/>
    <img src="https://img.shields.io/badge/dados-OpenStreetMap-7EBC6F?logo=openstreetmap&logoColor=white" alt="OSM"/>
  </p>
  <p>
    <a href="http://localhost:8000"><strong>Demo local</strong></a> &nbsp;·&nbsp;
    <a href="INSTALL.md"><strong>Instalacao</strong></a> &nbsp;·&nbsp;
    <a href="Relatorio_FitMap.docx"><strong>Relatorio</strong></a>
  </p>
</div>

---

## O que e o FitMap?

O **FitMap** e uma aplicacao WebSIG funcional que responde a uma pergunta simples: _"onde posso treinar perto de mim?"_. Agrega **3 390 instalacoes desportivas reais** de todo o territorio portugues — ginasios, piscinas, centros desportivos, dojos, estudios e campos — recolhidas diretamente do [OpenStreetMap](https://www.openstreetmap.org) e pesquisaveis por proximidade GPS, modalidade, cidade ou area desenhada no mapa.

O projeto foi desenvolvido para a unidade curricular de **Tecnologias e Aplicacoes de Bases de Dados (TABD)** da Universidade de Aveiro e demonstra na pratica tres tecnologias centrais do programa:

| Pilar | Tecnologia | Demonstrado por |
|---|---|---|
| Bases de dados espaciais | MongoDB 7 + indice `2dsphere` | `$geoNear`, `$geoWithin` |
| Bases de dados NoSQL | MongoDB Aggregation Framework | `$facet`, `$unwind`, `$group` |
| Tecnologias Web | FastAPI + Leaflet.js + OSRM | API REST + SPA interativa |

---

## Funcionalidades

- **Mapa interativo** com 3 390 marcadores coloridos por categoria e legenda dinamica
- **Pesquisa por raio GPS** — `$geoNear` com auto-expansao automatica (3 → 5 → 10 → 25 → 50 → 100 km) quando nao ha resultados proximos
- **Selecao poligonal** — desenhe uma area no mapa e veja todas as instalacoes dentro (`$geoWithin`)
- **Filtros combinaveis** por categoria, modalidade e cidade sem combinacoes ilogicas
- **Painel de detalhe** com modalidades, contactos, horarios e acessibilidade
- **Calculo de rotas** multimodal — carro / a pe / bicicleta via OSRM
- **Eventos desportivos** geolocalizados com ligacao a instalacao mais proxima
- **KPIs em tempo real** — instalacoes visiveis, taxa de horarios, taxa de websites

---

## Quickstart

```bash
git clone https://github.com/Pedro-Peyroteo/TABD.git
cd TABD
docker compose up --build
```

Abrir em: **http://localhost:8000**

O servico `fitmap-seed` popula o MongoDB automaticamente (~2 min na primeira execucao). Para instrucoes detalhadas consulte [INSTALL.md](INSTALL.md).

---

## Arquitetura

```
Browser (Leaflet SPA)
    │  HTTP/JSON
    ▼
FastAPI  ─── 9 endpoints REST  (web/server.py)
    │  pymongo
    ▼
MongoDB 7  ─── indice 2dsphere + category + sports + city
    (coleção facilities — 3 390 documentos GeoJSON Point)

Servicos externos:
  Overpass API  ──  dados OSM (seed)
  Nominatim     ──  geocoding com cache local
  OSRM          ──  rotas car / foot / bike
  CartoDB       ──  tiles do mapa (dark theme)
```

### Pipelines MongoDB principais

```javascript
// Proximidade — $geoNear (raio com filtro de categoria)
db.facilities.aggregate([
  { $geoNear: { near: { type:"Point", coordinates:[lon,lat] },
      distanceField:"distancia_m", maxDistance:5000,
      spherical:true, query:{ category:"Ginasio" } } },
  { $limit: 50 }
])

// Selecao poligonal — $geoWithin + $facet
db.facilities.aggregate([
  { $match: { location: { $geoWithin: { $geometry: polygon } } } },
  { $facet: {
      items:   [{ $project:{...} }, { $limit:500 }],
      summary: [{ $group: { _id:"$category", count:{ $sum:1 } } }]
  }}
])

// KPIs globais — $facet paralelo
db.facilities.aggregate([
  { $facet: {
      totals:     [{ $count:"total" }],
      categories: [{ $group:{ _id:"$category", count:{ $sum:1 } } }, { $sort:{count:-1} }],
      topSports:  [{ $unwind:"$sports" }, { $group:{ _id:"$sports", count:{ $sum:1 } } }, { $sort:{count:-1} }, { $limit:10 }],
      topCities:  [{ $group:{ _id:"$address.city", count:{ $sum:1 } } }, { $sort:{count:-1} }, { $limit:12 }]
  }}
])
```

---

## Estrutura do Repositorio

```
TABD/
├── docker-compose.yml               # mongodb + seed + web
├── Dockerfile                       # imagem do servico seed
├── README.md                        # este ficheiro
├── INSTALL.md                       # guia de instalacao
├── Relatorio_FitMap.docx            # relatorio academico
│
├── web/                             # aplicacao web
│   ├── Dockerfile
│   ├── requirements.txt             # fastapi, uvicorn, pymongo
│   ├── server.py                    # API REST (9 endpoints)
│   └── static/
│       ├── index.html               # SPA — landing + mapa + paineis
│       ├── img/logo.svg             # logo SVG personalizado
│       ├── css/main.css             # tema dark (bg #0b0b0d, accent #ff5b3a)
│       └── js/app.js                # Leaflet, filtros, rota, poligono
│
├── 03_Implementacao/
│   ├── seed_osm.py                  # ETL: Overpass API → MongoDB
│   └── scrapers/
│       ├── wikidata.py              # SPARQL — instalacoes Wikidata
│       └── smoothcomp.py            # eventos desportivos (JSON-LD)
│
├── docs/
│   ├── generate_report.py           # gerador do relatorio Word
│   ├── insert_images.py             # insersor de screenshots no Word
│   ├── take_screenshots.py          # captura automatica via Playwright
│   └── screenshots/                 # 6 capturas do FitMap em producao
│
└── 01_Definicao/ · 02_Modelagem/ · 04_BI_Analysis/ · 05_Entrega/
    └── documentacao academica do projeto
```

---

## API REST

Documentacao interativa: **http://localhost:8000/docs**

| Endpoint | Operacao MongoDB | Descricao |
|---|---|---|
| `GET /api/overview` | `$facet` | KPIs globais (totais, categorias, modalidades, cidades) |
| `GET /api/facilities` | `$match` + `$project` | Lista com filtros opcionais |
| `GET /api/facilities/{osm_id}` | `find_one` | Detalhe de uma instalacao |
| `GET /api/geo/nearby` | `$geoNear` | Instalacoes por raio, ordenadas por distancia |
| `GET /api/geo/within` | `$geoWithin` | Instalacoes dentro de poligono |
| `GET /api/categories` | `$group` | Categorias disponiveis |
| `GET /api/sports` | `$unwind` + `$group` | Modalidades distintas |
| `GET /api/cities` | `$group` + `$sort` | Cidades com contagem |

---

## Stack Tecnologico

| Camada | Tecnologia | Versao |
|---|---|---|
| Base de dados | MongoDB | 7.0 |
| Indice espacial | 2dsphere (GeoJSON RFC 7946) | — |
| Backend | FastAPI + uvicorn | 0.110 |
| Driver | pymongo | 4.x |
| Frontend | Leaflet.js + Leaflet.draw + Routing Machine | 1.9 |
| Geocodificacao | Nominatim (OSM) com cache | — |
| Routing | OSRM (car / foot / bike) | endpoint publico |
| Dados | OpenStreetMap via Overpass API | 3 390 instalacoes |
| Orquestracao | Docker Compose v2 | — |
| Screenshots | Playwright (Chromium headless) | — |

---

## Dados e Schema

Dados recolhidos via **Overpass API** com tags OSM:
`leisure=fitness_centre`, `leisure=swimming_pool`, `leisure=sports_centre`, `club=martial_arts`, `sport=*`

Exemplo de documento na colecao `facilities`:

```json
{
  "osm_id": 948376543,
  "name": "Complexo Desportivo Municipal",
  "category": "Centro Desportivo",
  "sports": ["swimming", "fitness", "basketball"],
  "location": { "type": "Point", "coordinates": [-8.654, 40.641] },
  "address": { "city": "Aveiro", "street": "Rua do Municipio", "postcode": "3800-000" },
  "contact": { "phone": "+351 234 000 000", "website": "https://cm-aveiro.pt" },
  "opening_hours": "Mo-Fr 07:00-22:00; Sa 09:00-18:00",
  "amenities": { "wheelchair": "yes", "parking": "yes", "shower": "yes" }
}
```

**Indices criados:**

| Campo | Tipo | Utilizado por |
|---|---|---|
| `location` | `2dsphere` | `$geoNear`, `$geoWithin` |
| `category` | Asc. | filtros por tipo |
| `sports` | Multikey | filtros por modalidade |
| `address.city` | Asc. | filtros por cidade |

---

## Equipa

Projeto desenvolvido no ambito da UC **Tecnologias e Aplicacoes de Bases de Dados**, Universidade de Aveiro, ano letivo 2025/2026.
