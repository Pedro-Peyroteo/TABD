# Guia de Instalacao e Execucao: FitMap

**Unidade Curricular:** Tecnologias e Aplicacoes de Bases de Dados (TABD) | **Ano Letivo:** 2025/2026

Este guia detalha todos os passos necessarios para executar a plataforma **FitMap** — um WebSIG de instalacoes desportivas em Portugal, composto por uma base de dados **MongoDB 7** com suporte a dados espaciais (indice `2dsphere`) e uma aplicacao web **FastAPI + Leaflet.js**.

---

## Pre-requisitos

### Opcao A — Docker (recomendado)

- **Docker Desktop** com Docker Compose v2 instalado e em execucao
- Ligacao a internet (Overpass API / OSM para recolha de dados no primeiro arranque)
- Porta **8000** disponivel no host (aplicacao web)
- Porta **27017** disponivel no host (MongoDB)

### Opcao B — Instalacao manual

- **Python 3.11+** instalado e no PATH do sistema
- **MongoDB Community Server 7.0+** instalado e em execucao na porta `27017`
- Ligacao a internet para a recolha de dados via Overpass API

---

## Opcao A: Docker Compose (recomendado)

### 1. Clonar o repositorio

```bash
git clone https://github.com/Pedro-Peyroteo/TABD.git
cd TABD
```

### 2. Construir e arrancar todos os servicos

```bash
docker compose up --build
```

Este comando inicia tres servicos em sequencia:

| Servico | Imagem | Funcao |
|---|---|---|
| `fitmap-mongodb` | `mongo:7` | Base de dados MongoDB na porta 27017 |
| `fitmap-seed` | Python 3.11 | ETL: descarrega dados OSM e popula MongoDB |
| `fitmap-web` | Python 3.11 | FastAPI + Leaflet na porta 8000 |

O `fitmap-seed` aguarda o MongoDB estar pronto e executa `03_Implementacao/seed_osm.py`, que:
1. Consulta a Overpass API para todas as instalacoes desportivas em Portugal
2. Normaliza e insere os documentos na colecao `facilities`
3. Cria os indices: `2dsphere` (location), `category`, `sports`, `city`

**Duracao da seed:** 1–3 minutos (dependendo da ligacao a internet).

### 3. Aceder a aplicacao

Abrir no browser:
```
http://localhost:8000
```

### 4. Parar os servicos

```bash
docker compose down
```

Para remover tambem os volumes de dados (apaga o MongoDB):
```bash
docker compose down -v
```

### 5. Opcao: MongoDB Express (interface visual)

Para arrancar o MongoDB Express (interface web para explorar a base de dados):

```bash
docker compose --profile tools up
```

Aceder em: `http://localhost:8081`

---

## Opcao B: Instalacao Manual

### 1. Clonar o repositorio

```bash
git clone https://github.com/Pedro-Peyroteo/TABD.git
cd TABD
```

### 2. Instalar dependencias Python

```bash
cd web
pip install -r requirements.txt
cd ..
```

O `requirements.txt` instala: `fastapi`, `uvicorn`, `pymongo`, `httpx`, `python-dotenv`.

### 3. Garantir MongoDB em execucao

Verificar que o MongoDB esta activo na porta padrao:

```bash
# Linux / macOS
mongosh --eval "db.runCommand({ ping: 1 })"

# Windows (PowerShell)
mongosh --eval "db.runCommand({ ping: 1 })"
```

Se necessario, iniciar o servico:
```bash
# Linux (systemd)
sudo systemctl start mongod

# macOS (Homebrew)
brew services start mongodb-community

# Windows
net start MongoDB
```

### 4. Executar a seed (recolha de dados OSM)

```bash
cd 03_Implementacao
pip install requests pymongo
python seed_osm.py
cd ..
```

O script demora 1–3 minutos. No final, apresenta o numero de instalacoes inseridas e os indices criados.

### 5. Arrancar o servidor FastAPI

```bash
cd web
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Aceder em: `http://localhost:8000`

---

## Variaveis de Ambiente

| Variavel | Valor padrao | Descricao |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | URI de ligacao ao MongoDB |
| `MONGO_DB` | `fitmap` | Nome da base de dados |
| `MONGO_COLLECTION` | `facilities` | Nome da colecao principal |
| `PORT` | `8000` | Porta do servidor FastAPI |

Para personalizar, criar um ficheiro `.env` na pasta `web/`:

```env
MONGO_URI=mongodb://fitmap-mongodb:27017
MONGO_DB=fitmap
MONGO_COLLECTION=facilities
PORT=8000
```

---

## Endpoints da API REST

| Metodo | Endpoint | Descricao |
|---|---|---|
| `GET` | `/api/overview` | Estatisticas gerais (`$facet`) |
| `GET` | `/api/facilities` | Lista de instalacoes com filtros opcionais |
| `GET` | `/api/facilities/{osm_id}` | Detalhe de uma instalacao |
| `GET` | `/api/geo/nearby` | Instalacoes proximas de um ponto (`$geoNear`) |
| `POST` | `/api/geo/within` | Instalacoes dentro de um poligono (`$geoWithin`) |
| `GET` | `/api/categories` | Lista de categorias disponiveis |
| `GET` | `/api/sports` | Modalidades disponiveis (com filtro por categoria) |
| `GET` | `/api/cities` | Cidades com contagem de instalacoes |

Documentacao interativa disponivel em: `http://localhost:8000/docs`

---

## Verificacao pos-instalacao

Apos o arranque, verificar:

1. **Landing page** carrega com estatisticas (total de instalacoes, cidades, modalidades)
2. **Mapa** apresenta marcadores coloridos por categoria em todo o territorio nacional
3. **Filtros** de categoria, modalidade e cidade funcionam e limitam os resultados
4. **Pesquisa por proximidade** — clicar com o botao direito no mapa ou usar "Minha localizacao"
5. **Selecao por poligono** — usar o botao "Desenhar area" e clicar para definir vertices
6. **Painel de detalhe** — clicar num marcador mostra modalidades, contactos e horarios
7. **Calculo de rota** — clicar "Calcular rota" no painel de detalhe e selecionar modo de transporte

---

## Resolucao de Problemas

### A seed demora muito ou falha

A Overpass API pode estar temporariamente indisponivel. Aguardar alguns minutos e tentar novamente:
```bash
docker compose restart fitmap-seed
```

### Porta 8000 ou 27017 em uso

Editar `docker-compose.yml` e alterar o mapeamento de portas:
```yaml
ports:
  - "8001:8000"   # alterar 8001 para outra porta livre
```

### MongoDB nao arranca (instalacao manual)

Verificar se o directorio de dados existe:
```bash
# Linux / macOS
sudo mkdir -p /var/lib/mongodb
sudo chown -R mongodb:mongodb /var/lib/mongodb
```

### Nenhum resultado no mapa

Confirmar que a seed foi concluida com sucesso. Verificar no MongoDB:
```bash
mongosh fitmap --eval "db.facilities.countDocuments()"
```
Deve retornar um valor proximos de 3390.
