# Analise e Visualizacao: FitMap

**UC:** Tecnologias e Aplicacoes de Bases de Dados (TABD) | **Ano letivo:** 2025/2026

---

## 1. KPIs da Plataforma

Os indicadores sao calculados em tempo real pelo endpoint `/api/overview` via pipeline `$facet`.

| KPI | Valor atual | Como calculado |
|---|---|---|
| Total de instalacoes | 3 390 | `$count` |
| Categorias distintas | 9 | `$group` por `category` |
| Cidades com instalacoes | 234+ | `$group` por `address.city` |
| Instalacoes com horario | ~10 % | `$match` `opening_hours != ""` |
| Instalacoes com website | ~15 % | `$match` `contact.website != ""` |
| Modalidades distintas | ~40 | `$unwind` + `$group` por `sports` |

---

## 2. Distribuicao por Categoria

| Categoria | Instalacoes | % |
|---|---|---|
| Centro Desportivo | 1 453 | 42,9 % |
| Piscina | 806 | 23,8 % |
| Ginasio | 707 | 20,9 % |
| Escalada | 253 | 7,5 % |
| Outro | 90 | 2,7 % |
| Estudio de Danca | 53 | 1,6 % |
| Artes Marciais | 22 | 0,6 % |
| Yoga / Pilates | 5 | 0,1 % |
| Boxe / Kickboxing | 1 | <0,1 % |

---

## 3. Top Cidades

| Cidade | Instalacoes |
|---|---|
| Lisboa | 69 |
| Coimbra | 20 |
| Porto | 17 |
| Montijo | 12 |
| Funchal | 11 |
| Vila Real | 9 |
| Aveiro | 8 |

---

## 4. Visualizacoes no Frontend

| Componente | Dados | Operacao MongoDB |
|---|---|---|
| KPI bar (header) | Vis., horarios, websites | `/api/overview` → `$facet` |
| Sidebar categorias | Contagem por tipo | `/api/overview` → `$facet` |
| Sidebar modalidades | Lista por frequencia | `/api/sports` → `$unwind` + `$group` |
| Lista de cidades | Ordenada por contagem | `/api/cities` → `$group` + `$sort` |
| Marcadores no mapa | Lat/lon + categoria | `/api/facilities` → `$match` + `$project` |
| Painel raio | 50 resultados por distancia | `/api/geo/nearby` → `$geoNear` |
| Painel area | Lista + breakdown | `/api/geo/within` → `$geoWithin` + `$facet` |

---

## 5. Diferenciais da Plataforma

- **Dados reais OSM** — nao sinteticos, auditaveis, actualizaveis
- **Cobertura nacional** — 234+ municipios, incluindo interior
- **Auto-expansao de raio** — 3→5→10→25→50→100 km sem intervencao do utilizador
- **Selecao poligonal** — unica na categoria; usa `$geoWithin` sobre geometria desenhada
- **Routing integrado** — carro / a pe / bicicleta via OSRM, sem sair da plataforma
- **Eventos geolocalizados** — ligados a instalacoes por `$geoNear` inter-colecao
