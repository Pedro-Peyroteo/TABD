# FitMap — Onde Treinar em Portugal

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD) | **Ano Letivo:** 2025/2026

**FitMap** é uma plataforma WebSIG funcional para descoberta de instalações desportivas em Portugal Continental. Agrega dados reais do OpenStreetMap (3 390 instalações) numa base de dados MongoDB com índices geoespaciais nativos, exposta através de uma API REST em FastAPI e visualizada num mapa interativo Leaflet.js.

---

## Motivação e Objetivos

O projeto demonstra a aplicação prática de bases de dados NoSQL com suporte espacial num cenário real:

- **Cobertura nacional** — ginásios, piscinas, campos de futebol, dojos, estúdios, centros desportivos e outras instalações em todo o território português
- **Dados reais** — recolhidos via Overpass API (OpenStreetMap) e enriquecidos com atributos de acessibilidade, contactos e horários
- **Consultas geoespaciais** — `$geoNear` para proximidade, `$geoWithin` para seleção por polígono desenhado pelo utilizador, `$facet` para agregações paralelas
- **Interoperabilidade** — integração com OSRM (rotas multimodal: carro/a pé/bicicleta) e Nominatim (geocodificação com cache local)

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (Leaflet.js SPA)                                   │
│  Landing → Mapa → Painel de detalhe → Área por polígono     │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP / JSON
┌────────────────────▼────────────────────────────────────────┐
│  FastAPI  (web/server.py)   — 9 endpoints REST              │
│  /api/overview  /api/facilities  /api/geo/nearby            │
│  /api/geo/within  /api/categories  /api/sports  /api/cities │
└────────────────────┬────────────────────────────────────────┘
                     │ pymongo
┌────────────────────▼────────────────────────────────────────┐
│  MongoDB 7  (fitmap DB, colecao facilities)                  │
│  Indices: 2dsphere · category · sports · city               │
└─────────────────────────────────────────────────────────────┘
```

### Pipelines MongoDB utilizados

| Pipeline | Operador principal | Finalidade |
|---|---|---|
| Visão geral | `$facet` | Contagens paralelas por categoria, cidade e modalidade |
| Proximidade | `$geoNear` | Instalações ordenadas por distância a um ponto |
| Área | `$geoWithin` + `$geometry` | Instalações dentro de polígono desenhado |
| Modalidades | `$unwind` + `$group` | Lista distinta de desportos com contagem |
| Cidades | `$group` + `$sort` | Cidades com maior concentração de instalações |

---

## Funcionalidades

- **Pesquisa combinada** por categoria, modalidade e cidade na landing page
- **Filtros dinâmicos** — modalidades disponíveis filtradas pela categoria selecionada (sem combinações ilógicas)
- **Mapa interativo** com marcadores agrupados por categoria (cor + ícone)
- **Seleção por polígono** desenhado diretamente no mapa (`$geoWithin`)
- **Geolocalização GPS** com expansão automática de raio (3 → 5 → 10 → 25 → 50 → 100 km) quando não há resultados próximos
- **Painel de detalhe** com modalidades, contactos, horários e acessibilidade
- **Cálculo de rota** multimodal (carro / a pé / bicicleta) via OSRM
- **KPIs em tempo real** — instalações visíveis, taxa de horários e de websites

---

## Estrutura do Repositório

```
TABD/
├── README.md                            # Este ficheiro
├── INSTALL.md                           # Guia de instalacao e execucao
├── docker-compose.yml                   # Orquestracao: MongoDB + seed + FastAPI
├── Relatorio_FitMap.docx                # Relatorio academico (gerado por docs/)
├── Template relatorio_projeto_IHC.docx  # Template Word fornecido pelo docente
│
├── web/                                 # Aplicacao web
│   ├── server.py                        # FastAPI — 9 endpoints REST
│   ├── requirements.txt                 # Dependencias Python do servidor
│   └── static/
│       ├── index.html                   # SPA (landing + mapa + paineis)
│       ├── css/main.css                 # Tema dark (--bg:#0b0b0d, --accent:#ff5b3a)
│       └── js/app.js                    # Logica Leaflet, filtros, rota, poligono
│
├── 03_Implementacao/
│   ├── seed_osm.py                      # ETL: Overpass API → normalizacao → MongoDB
│   └── scrapers/
│       ├── wikidata.py                  # SPARQL — instalacoes via Wikidata
│       ├── smoothcomp.py                # Eventos desportivos (JSON-LD, paralelo)
│       └── fpme.py                      # Federacao Portuguesa de Modalidades
│
└── docs/
    ├── generate_report.py               # Gerador do relatorio Word (python-docx)
    └── inspect_template.py              # Utilitario de inspecao do template
```

---

## Quickstart (Docker Compose)

```bash
# 1. Clonar o repositorio
git clone https://github.com/Pedro-Peyroteo/TABD.git
cd TABD

# 2. Construir e arrancar todos os servicos
docker compose up --build

# 3. Abrir no browser
http://localhost:8000
```

O servico `fitmap-seed` corre automaticamente, descarrega os dados do OpenStreetMap via Overpass API e popula o MongoDB. O processo demora 1–3 minutos na primeira execucao.

Para parar:
```bash
docker compose down
```

> Consulte `INSTALL.md` para instalacao manual (sem Docker) e opcoes avancadas de configuracao.

---

## Stack Tecnologico

| Camada | Tecnologia |
|---|---|
| Base de dados | MongoDB 7 — indice `2dsphere`, `$geoNear`, `$geoWithin`, `$facet` |
| Backend | FastAPI (Python 3.11) + pymongo + uvicorn |
| Frontend | Leaflet.js 1.9 + Leaflet.draw + Leaflet Routing Machine |
| Geocodificacao | Nominatim (OSM) com cache local |
| Rotas | OSRM (carro / a pe / bicicleta) — endpoint publico |
| Dados | OpenStreetMap via Overpass API (3 390 instalacoes) |
| Orquestracao | Docker Compose v2 |
| Relatorio | python-docx — geracao programatica do relatorio Word |

---

## Schema do Documento MongoDB

O script `03_Implementacao/seed_osm.py` normaliza cada instalacao para o seguinte schema:

```json
{
  "osm_id": 123456789,
  "name": "Ginasio Municipal de Aveiro",
  "category": "gym",
  "sports": ["fitness", "yoga"],
  "address": {
    "city": "Aveiro",
    "street": "Rua de Exemplo",
    "postcode": "3800-000"
  },
  "location": {
    "type": "Point",
    "coordinates": [-8.654, 40.641]
  },
  "contacts": {
    "phone": "+351 234 000 000",
    "website": "https://exemplo.pt",
    "email": "info@exemplo.pt"
  },
  "opening_hours": "Mo-Fr 07:00-22:00; Sa 09:00-18:00",
  "amenities": {
    "wheelchair": true,
    "parking": true,
    "shower": true
  },
  "source": "osm",
  "fetched_at": "2025-..."
}
```

---

## Equipa

Projeto desenvolvido no ambito da Unidade Curricular de **Tecnologias e Aplicacoes de Bases de Dados (TABD)**, Universidade de Aveiro, ano letivo 2025/2026.
