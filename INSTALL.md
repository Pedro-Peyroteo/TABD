# Guia de Instalação e Execução: FitMap

**Unidade Curricular:** Tecnologias e Aplicações de Bases de Dados (TABD) | **Ano Letivo:** 2025/2026

Este guia detalha como executar o **FitMap**, uma plataforma WebSIG composta por **MongoDB** (com índice geoespacial `2dsphere`), uma API **FastAPI** e um frontend **Leaflet**. O caminho recomendado é via **Docker Compose**.

---

## Pré-requisitos

- **Docker Desktop** com Docker Compose v2 — caminho recomendado, arranca todo o ecossistema.
- Para execução manual (sem Docker): **Python 3.12+** e um **MongoDB 7** acessível em `localhost:27017`.

---

## 1. Execução com Docker Compose (recomendado)

Na raiz do repositório (`TABD/`):

```bash
docker compose up --build
```

O Compose constrói e arranca três serviços por defeito:

| Serviço | Imagem / Build | Porta | Função |
| :--- | :--- | :--- | :--- |
| `mongodb` | `mongo:7` | `27017` | Base de dados, com volume persistente `mongodb_data` |
| `seed` | `Dockerfile` (raiz) | — | Executa `seed_osm.py` e depois `seed_events.py`, populando `facilities` e `events` |
| `web` | `web/Dockerfile` | `8000` | API FastAPI (`uvicorn server:app`) + serviço do frontend |

Quando o seed terminar, abrir a aplicação em:

```
http://localhost:8000
```

A documentação interativa da API fica em `http://localhost:8000/docs`.

### 1.1 Mongo Express (perfil `tools`)

Para inspecionar a base de dados numa interface web:

```bash
docker compose --profile tools up --build
```

O Mongo Express fica disponível em `http://localhost:8081` (base `FitMap`, coleções `facilities` e `events`).

> **Nota sobre perfis:** este projeto define apenas o perfil `tools`. Um perfil `simulation` **não existe** nesta versão (pertencia ao projeto legado GlobalShop). Comandos como `docker compose --profile simulation ... up` não dão erro, mas o perfil é simplesmente ignorado. O comando correto para o ecossistema completo é:
>
> ```bash
> docker compose --profile tools up --build
> ```

### 1.2 Repetir apenas o seed

Após alterar dados de origem ou limpar a base:

```bash
docker compose run --rm seed
```

### 1.3 Verificação rápida no MongoDB

```bash
docker compose exec mongodb mongosh --quiet --eval "db.getSiblingDB('FitMap').facilities.countDocuments()"
docker compose exec mongodb mongosh --quiet --eval "db.getSiblingDB('FitMap').facilities.getIndexes()"
```

### 1.4 Reset da demo

```bash
# Parar e remover containers, mantendo os dados
docker compose down

# Apagar também o volume MongoDB e recomeçar do zero
docker compose down -v
docker compose up --build
```

---

## 2. Execução Manual (sem Docker)

Útil para desenvolvimento. Requer um MongoDB a correr localmente.

### 2.1 Instalar dependências

```bash
pip install -r web/requirements.txt          # fastapi, uvicorn, pymongo (backend)
pip install -r requirements.txt              # dependências dos seeds (requests, pymongo, ...)
```

### 2.2 Popular a base de dados

A partir da pasta `03_Implementacao/`:

```bash
python seed_osm.py        # instalações a partir do OpenStreetMap (usa cache osm_cache.json)
python seed_events.py     # eventos geocodificados (usa cache geocode_cache.json)
```

### 2.3 Arrancar a API + frontend

A partir da pasta `web/`:

```bash
uvicorn server:app --reload --port 8000
```

Abrir `http://localhost:8000`.

---

## 3. Variáveis de Ambiente

Lidas tanto pelo backend (`web/server.py`) como pelos seeds. Os valores padrão no Docker estão definidos em `docker-compose.yml`.

| Variável | Padrão | Uso |
| :--- | :--- | :--- |
| `MONGO_URI` | `mongodb://localhost:27017` | URI de ligação. No Docker: `mongodb://mongodb:27017`. |
| `MONGO_DB` | `FitMap` | Nome da base de dados. |
| `MONGO_COLLECTION` | `facilities` | Coleção de instalações. |
| `EVENTS_COLLECTION` | `events` | Coleção de eventos. |
| `OSM_USE_CACHE` | `1` | Se `1`, `seed_osm.py` usa `osm_cache.json` em vez de consultar a Overpass API. |

---

## 4. Resolução de Problemas

| Problema | Causa Provável | Solução |
| :--- | :--- | :--- |
| `network <id> not found` ao fazer `up` | Container órfão de uma execução anterior (ex. um `mongo-express` do perfil `tools`) ainda referencia uma rede do Compose já removida | Ver secção **4.1** abaixo |
| Página abre mas sem instalações no mapa | O serviço `seed` ainda não terminou, ou falhou | Aguardar o fim do seed; ver `docker compose logs seed` |
| `$geoNear`/`$geoWithin` devolve erro | Índice `2dsphere` em falta | Correr o seed; o backend também cria o índice no arranque |
| `web` não liga ao MongoDB | MongoDB ainda a arrancar | O `web` depende do `seed`, que depende do `mongodb` saudável; aguardar e repetir |
| Geocoding lento no `seed_events.py` | Limite de 1 pedido/seg do Nominatim | Comportamento esperado; resultados ficam em cache (`geocode_cache.json`) |

### 4.1 Erro de rede do Docker (`network ... not found`)

**Sintoma:**

```
Error response from daemon: network <id> not found
```

**Causa:** um container deixado por uma execução anterior (frequentemente o `mongo-express` do perfil `tools`) continua ligado a uma rede do Compose que já não existe, impedindo a recriação do stack.

**Solução:**

```bash
# 1. Remover containers já não definidos no compose atual (passo-chave)
docker compose down --remove-orphans

# 2. Limpar redes não utilizadas
docker network prune -f

# 3. Se ainda restar um container com o mesmo nome:
docker rm <nome-do-container>

# 4. Voltar a arrancar
docker compose --profile tools up --build
```

O passo determinante é `docker compose down --remove-orphans`, que remove containers que já não constam do ficheiro Compose atual.

---

## 5. Testes Automatizados

```bash
pytest
```

---

## 6. Estrutura do Repositório

```
TABD/
├── docker-compose.yml               # mongodb + seed + web (+ mongo-express no perfil "tools")
├── Dockerfile                       # Imagem usada pelo serviço de seed
├── INSTALL.md                       # Este guia
├── README.md                        # Visão geral do projeto
├── web/
│   ├── Dockerfile                   # Imagem FastAPI/uvicorn
│   ├── requirements.txt             # fastapi, uvicorn, pymongo
│   ├── server.py                    # API REST + serviço da SPA
│   └── static/                      # Frontend Leaflet (index.html, js/app.js, css/main.css)
├── 03_Implementacao/
│   ├── seed_osm.py                  # Instalações do OpenStreetMap
│   ├── seed_events.py               # Eventos geocodificados
│   └── scrapers/                    # Scrapers de eventos
├── 01_Definicao/ · 02_Modelagem/ · 04_BI_Analysis/ · 05_Entrega/   # Documentação académica
└── tests/                           # Testes pytest
```
