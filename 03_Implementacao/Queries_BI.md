# Queries Geoespaciais e Pipelines MongoDB: FitMap

**UC:** Tecnologias e Aplicacoes de Bases de Dados (TABD) | **Ano letivo:** 2025/2026

---

## 1. `$geoNear` — Pesquisa por Proximidade

Endpoint: `GET /api/geo/nearby?lat=...&lon=...&radius_km=5&category=Ginasio`

```javascript
db.facilities.aggregate([
  { $geoNear: {
      near:          { type: "Point", coordinates: [-9.1393, 38.7223] },
      distanceField: "distancia_m",
      maxDistance:   5000,
      spherical:     true,
      key:           "location",
      query:         { category: "Ginasio" }
  }},
  { $limit: 50 },
  { $project: {
      _id: 0, osm_id: 1, name: 1, category: 1,
      lat:    { $arrayElemAt: ["$location.coordinates", 1] },
      lon:    { $arrayElemAt: ["$location.coordinates", 0] },
      distKm: { $round: [{ $divide: ["$distancia_m", 1000] }, 2] }
  }}
])
```

**Notas:**
- `spherical: true` — distancia geodesica (essencial para coordenadas geograficas)
- `query` permite sobrepor filtros adicionais ao `$geoNear`
- `$arrayElemAt` extrai lat/lon do array GeoJSON para o cliente

---

## 2. `$geoWithin` + `$facet` — Selecao Poligonal

Endpoint: `GET /api/geo/within?coords=[[lon1,lat1],[lon2,lat2],...]`

```javascript
db.facilities.aggregate([
  { $match: {
      location: {
        $geoWithin: {
          $geometry: {
            type: "Polygon",
            coordinates: [[[lon1,lat1],[lon2,lat2],[lon3,lat3],[lon1,lat1]]]
          }
        }
      }
  }},
  { $facet: {
      items:   [{ $project: { osm_id:1, name:1, category:1, lat:1, lon:1 } }, { $limit: 500 }],
      summary: [{ $group: { _id: "$category", count: { $sum: 1 } } }, { $sort: { count: -1 } }],
      totals:  [{ $count: "total" }]
  }}
])
```

**Notas:**
- O poligono GeoJSON deve ser **fechado** (primeiro == ultimo ponto)
- `$facet` calcula 3 perspetivas em simultane numa unica passagem

---

## 3. `$facet` + `$unwind` — KPIs Globais Paralelos

Endpoint: `GET /api/overview`

```javascript
db.facilities.aggregate([
  { $facet: {
      totals: [{ $count: "total" }],
      categories: [
        { $group: { _id: "$category", count: { $sum: 1 } } },
        { $sort:  { count: -1 } }
      ],
      topSports: [
        { $unwind: "$sports" },
        { $group:  { _id: "$sports", count: { $sum: 1 } } },
        { $sort:   { count: -1 } },
        { $limit:  20 }
      ],
      topCities: [
        { $match:  { "address.city": { $ne: "" } } },
        { $group:  { _id: "$address.city", count: { $sum: 1 } } },
        { $sort:   { count: -1 } },
        { $limit:  12 }
      ]
  }}
])
```

**Nota sobre `$unwind`:** Como `sports` e um array, `$unwind` virtualiza cada elemento como documento separado antes do `$group`. Sem este passo, a contagem seria por array inteiro e nao por modalidade individual.

---

## 4. `$group` — Modalidades por Categoria

Endpoint: `GET /api/sports?category=Ginasio`

```javascript
db.facilities.aggregate([
  { $match: { category: "Ginasio" } },
  { $unwind: "$sports" },
  { $group:  { _id: "$sports", count: { $sum: 1 } } },
  { $sort:   { count: -1 } },
  { $project: { _id: 0, sport: "$_id", count: 1 } }
])
```

---

## 5. Eventos Proximos de uma Instalacao

Endpoint: `GET /api/events/by-facility/{osm_id}`

```javascript
// Obter coordenadas da instalacao
const fac = db.facilities.findOne({ osm_id: 123456789 })

// Pesquisar eventos proximos (raio 5 km)
db.events.aggregate([
  { $geoNear: {
      near:          fac.location,
      distanceField: "dist_m",
      maxDistance:   5000,
      spherical:     true
  }},
  { $match: { start_date: { $gte: new Date() } } },
  { $sort:  { start_date: 1 } },
  { $limit: 10 }
])
```

---

## 6. Performance Observada

| Query | Operacao dominante | Latencia tipica |
|---|---|---|
| `/api/overview` | `$facet` (5 sub-pipelines) | ~70 ms |
| `/api/geo/nearby` (raio 3 km) | `$geoNear` | ~45 ms |
| `/api/geo/nearby` (raio 50 km) | `$geoNear` | ~80 ms |
| `/api/geo/within` (Lisboa) | `$geoWithin` + `$facet` | ~65 ms |
| `/api/sports` | `$unwind` + `$group` | ~45 ms |
