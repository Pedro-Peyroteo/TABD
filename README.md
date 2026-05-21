# FitMap — Onde Treinar em Portugal

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD) | **Ano Letivo:** 2025/2026

FitMap é uma **plataforma WebSIG** (Sistema de Informação Geográfica na Web) para descoberta de instalações desportivas em Portugal — ginásios, piscinas, centros desportivos, dojos, estúdios e muito mais — agregadas a partir de **dados abertos** do OpenStreetMap e pesquisáveis por proximidade, modalidade ou cidade. Inclui ainda uma camada de **eventos desportivos** geolocalizados.

O projeto demonstra o uso de **MongoDB como base de dados espacial nativa** (índice `2dsphere` sobre GeoJSON) servida por uma API **FastAPI** e consumida por um frontend **Leaflet** de página única.

> Nota: o repositório contém também um projeto anterior — o dashboard *GlobalShop* em Streamlit (`app_bi.py`, `globalshop_bi/`). A configuração de execução atual (`docker-compose.yml`) constrói e arranca apenas o FitMap; o GlobalShop é considerado legado.

---

## Arquitetura

```
OpenStreetMap / Overpass ─┐
Nominatim (geocoding)    ─┼─►  Seeds (Python)  ─►  MongoDB  ─►  FastAPI  ─►  Leaflet SPA
Scrapers (eventos)       ─┘     seed_osm.py        FitMap        web/         web/static/
                                seed_events.py    (2dsphere)    server.py    index.html
```

| Camada | Tecnologia | Papel |
| :--- | :--- | :--- |
| Base de dados | MongoDB 7 | Documentos com índice geoespacial `2dsphere` |
| Dados espaciais | GeoJSON (RFC 7946) + `2dsphere` | `$geoNear`, `$geoWithin`, `$facet`, `$unwind` |
| Backend | FastAPI + uvicorn | API REST `/api/*` e serviço da SPA |
| Driver | pymongo | Ligação ao MongoDB (cliente partilhado) |
| Frontend | Leaflet + Leaflet.draw + Routing Machine | Mapa interativo, desenho de polígonos, rotas |
| Origem de dados | OpenStreetMap, Nominatim, Wikidata, federações | Instalações e eventos |

O MongoDB armazena duas coleções:

- **`facilities`** — instalações desportivas: `osm_id`, `name`, `category`, `sports[]`, `address.{city,street,housenumber,postcode}`, `contact.{phone,website,email}`, `opening_hours`, `amenities`, `operator` e `location` (GeoJSON `Point`, coordenadas `[lon, lat]`).
- **`events`** — eventos desportivos: `title`, `sport`, `category`, `start_date`/`end_date`, `venue_name`, `city`, `source`, `location` (GeoJSON `Point`) e `near_facility` (instalação OSM mais próxima, ligada por `$geoNear`).

---

## Início Rápido (Docker)

```bash
docker compose up --build
```

Isto constrói e arranca três serviços: `mongodb`, `seed` (carrega instalações e eventos) e `web`. Quando o seed terminar, abrir:

```
http://localhost:8000
```

Para incluir o **Mongo Express** (inspeção visual da base de dados em `http://localhost:8081`):

```bash
docker compose --profile tools up --build
```

> Se obtiver um erro `network ... not found` ao arrancar, ver a secção de resolução de problemas no [INSTALL.md](INSTALL.md) — normalmente resolve-se com `docker compose down --remove-orphans`.

O guia completo de instalação (incluindo execução manual sem Docker e variáveis de ambiente) está em **[INSTALL.md](INSTALL.md)**.

---

## Funcionalidades

- **Mapa interativo** de todas as instalações, com cores por categoria e legenda.
- **Filtros** por categoria, modalidade e cidade, combináveis entre si.
- **Pesquisa por raio** (`$geoNear`): clique direito no mapa ou "Minha localização" — expande automaticamente o raio até encontrar resultados.
- **Seleção poligonal** (`$geoWithin`): desenhe uma área e veja as instalações lá contidas, com resumo por categoria.
- **Rotas** até uma instalação (carro / a pé / bicicleta) via OSRM.
- **Eventos desportivos** geolocalizados, com ligação à instalação mais próxima.
- **Botão "Início"** no cabeçalho para regressar ao ecrã inicial a partir do mapa.

---

## API (FastAPI)

Documentação interativa automática em `http://localhost:8000/docs`.

| Endpoint | Operador MongoDB | Descrição |
| :--- | :--- | :--- |
| `GET /api/overview` | `$facet` | KPIs globais (total, categorias, modalidades, cidades) numa só query |
| `GET /api/facilities` | `$match` + `$project` | Lista de instalações com filtros |
| `GET /api/facilities/{osm_id}` | `find_one` | Detalhe completo de uma instalação |
| `GET /api/geo/nearby` | `$geoNear` | Instalações dentro de um raio, ordenadas por distância |
| `GET /api/geo/within` | `$geoWithin` | Instalações dentro de um polígono desenhado |
| `GET /api/categories` · `/api/sports` · `/api/cities` | `$group` / `$unwind` | Listagens auxiliares para filtros |
| `GET /api/events` | `$match` + `$sort` | Eventos (futuros por defeito) |
| `GET /api/events/overview` | `$facet` | Estatísticas de eventos |
| `GET /api/events/near` | `$geoNear` | Eventos próximos de um ponto |
| `GET /api/events/by-facility/{osm_id}` | `$geoNear` | Eventos ligados/próximos de uma instalação |

---

## Estrutura do Repositório

```
TABD/
├── docker-compose.yml               # mongodb + seed + web (+ mongo-express no perfil "tools")
├── Dockerfile                       # Imagem usada pelo serviço de seed
├── INSTALL.md                       # Guia completo de instalação e execução
├── README.md                        # Este ficheiro
├── web/                             # Aplicação FitMap
│   ├── Dockerfile                   # Imagem FastAPI/uvicorn
│   ├── requirements.txt             # fastapi, uvicorn, pymongo
│   ├── server.py                    # API REST + serviço da SPA
│   └── static/                      # Frontend Leaflet (index.html, js/app.js, css/main.css)
├── 03_Implementacao/
│   ├── seed_osm.py                  # Carrega instalações do OpenStreetMap (cache: osm_cache.json)
│   ├── seed_events.py               # Carrega e geocodifica eventos (cache: geocode_cache.json)
│   └── scrapers/                    # Scrapers de eventos (wikidata, fpme, smoothcomp)
├── 01_Definicao/ · 02_Modelagem/ · 04_BI_Analysis/ · 05_Entrega/   # Documentação académica
└── tests/                           # Testes pytest
```

---

## Demonstração de Queries Geoespaciais

```javascript
// Instalações num raio de 5 km de um ponto (Lisboa), ordenadas por distância
db.facilities.aggregate([
  { $geoNear: {
      near: { type: "Point", coordinates: [-9.1393, 38.7223] },
      distanceField: "distancia_m",
      maxDistance: 5000,
      spherical: true,
      key: "location"
  }},
  { $limit: 10 }
])
```

O índice `2dsphere` sobre `location` é o que habilita `$geoNear` e `$geoWithin`. Os seeds criam-no automaticamente e o backend garante-o no arranque.
