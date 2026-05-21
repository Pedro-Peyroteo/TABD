# Modelagem de Dados: FitMap

**UC:** Tecnologias e Aplicacoes de Bases de Dados (TABD) | **Ano letivo:** 2025/2026

---

## 1. Colecao Principal: `facilities`

Cada documento representa uma instalacao desportiva georreferenciada. O schema e flexivel mas consistente — campos ausentes na fonte OSM sao string vazia.

```json
{
  "osm_id":   948376543,
  "osm_type": "node",
  "name":     "Complexo Desportivo Municipal de Aveiro",
  "category": "Centro Desportivo",
  "sports":   ["swimming", "fitness", "basketball"],
  "location": { "type": "Point", "coordinates": [-8.6541, 40.6413] },
  "address":  { "street": "Rua do Municipio", "city": "Aveiro", "postcode": "3800-000" },
  "contact":  { "phone": "+351 234 000 000", "website": "https://cm-aveiro.pt", "email": "" },
  "opening_hours": "Mo-Fr 07:00-22:00; Sa 09:00-18:00",
  "amenities": { "wheelchair": "yes", "parking": "yes", "shower": "yes", "indoor": "yes" },
  "fee": "no",
  "operator": "Camara Municipal de Aveiro"
}
```

---

## 2. Campo `location` — GeoJSON Point

```json
{ "type": "Point", "coordinates": [longitude, latitude] }
```

> **Ordem obrigatoria:** GeoJSON RFC 7946 usa `[lon, lat]` — ao contrario da convencao habitual.

---

## 3. Indices

| Indice | Tipo | Operacoes beneficiadas |
|---|---|---|
| `location` | `2dsphere` | `$geoNear`, `$geoWithin`, `$nearSphere` |
| `category` | Asc. simples | filtros por tipo de instalacao |
| `sports` | Asc. multikey | filtros por modalidade (campo array) |
| `address.city` | Asc. simples | filtros e agrupamentos por cidade |

O indice **multikey** sobre `sports` indexa cada elemento do array individualmente, permitindo `{ sports: "climbing" }` mesmo que `climbing` seja apenas uma de varias modalidades.

---

## 4. Colecao `events`

```json
{
  "title": "ADCC Iberian Open Lisboa 2026",
  "sport": "jiu-jitsu",
  "start_date": "2026-05-30T09:00:00",
  "venue_name": "Complexo Desportivo do Casal Vistoso",
  "city": "Lisboa",
  "source": "smoothcomp",
  "location": { "type": "Point", "coordinates": [-9.1215, 38.7311] },
  "near_facility": 123456789
}
```

---

## 5. Decisoes de Design

| Decisao | Alternativa | Justificacao |
|---|---|---|
| `sports` como array embedded | Colecao separada | Elimina JOIN; `$unwind` + `$group` e suficiente |
| `amenities` como subdocumento | Campos planos | Agrupa logicamente atributos de acessibilidade |
| `opening_hours` como string | Estrutura parsed | Preserva formato OSM original |
| String vazia para campos ausentes | `null` | Simplifica validacao no frontend |
| `[lon, lat]` | `[lat, lon]` | Obrigatorio pelo GeoJSON RFC 7946 |
