# Desafio 2 — Mobiliário urbano de Aveiro

[Enunciado do desafio](https://drive.google.com/file/d/1uGm7ZGFruShQ0hCybPq0kPX97UCYGJWm/view)

Web app que identifica e localiza no mapa o mobiliário urbano de Aveiro (sinais de trânsito,
iluminação pública, contentores de lixo) a partir de imagens de street view (Mapillary,
KartaView) e de vídeos gravados na rua, dispensando o levantamento no terreno. A aplicação
reconhece cada elemento nas imagens, calcula as suas coordenadas e guarda-o num catálogo que
os técnicos podem validar, corrigir e exportar.

## Arquitetura

```
 Browser ──► dashboard (Laravel + Livewire, :8080)
                 │  HTTP
                 ▼
             api (FastAPI, :8000) ──► db (PostgreSQL + PostGIS, :5432)
                 │  HTTP
                 ▼
             ml (FastAPI + PyTorch, :8001)
```

| Pasta | Serviço | O que faz | Documentação |
|---|---|---|---|
| [`dashboard/`](dashboard/) | `dashboard` | Interface web: mapa, catálogo, upload de imagens/vídeos | — |
| [`api/`](api/) | `api` | Recebe uploads, fala com o ML, guarda e serve o catálogo | [api/README.md](api/README.md) |
| [`ml/`](ml/) | `ml` | Desfoca caras/matrículas, deteta e classifica elementos, calcula posições, deduplica | [ml/docs/](ml/docs/) |
| — | `db` | PostGIS (catálogo geográfico) | — |

## Instalação com Docker

### 1. Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ou Docker Engine + plugin
  Compose v2). Verificar com `docker compose version`.
- ~10 GB livres em disco (a imagem do ML inclui o PyTorch) e pelo menos 8 GB de RAM atribuídos
  ao Docker.
- Os pesos dos modelos em `ml/weights/`
  do modo mock.
- Opcional: um token da [Mapillary](https://www.mapillary.com/dashboard/developers) para
  importar imagens de street view.

### 2. Clonar o repositório

```bash
git clone <url-do-repositório> challenge2
cd challenge2
```

### 3. Pesos dos modelos (ML)

O serviço `ml` monta `ml/weights/` em modo só de leitura. Para correr com os modelos reais,
coloca lá estes ficheiros (pedir ao desenvolvedor):

```
ml/weights/
├── face.onnx               # desfocagem de caras
├── plate.onnx              # desfocagem de matrículas
├── rtdetr_balanced_best/   # detetor RT-DETR afinado
├── sign_cls.onnx           # classificador de sinais
├── waste_cls.onnx          # classificador de contentores
└── lighting_cls.onnx       # classificador de iluminação
```

**Sem pesos?** Usa o modo mock (passo 6): o ML desfoca as imagens e inventa deteções no formato
certo, por isso todo o fluxo funciona na mesma.

### 4. Variáveis de ambiente

**API e base de dados** — o `db` e a `api` leem o mesmo ficheiro:

```bash
cp api/.env.example api/.env
```

Os valores por omissão servem. O `docker-compose.yml` já substitui `POSTGRES_HOST`,
`ML_SERVICE_URL` e `SHARED_DIR` pelos endereços internos do Docker. Para correr a API sem base
de dados (catálogo em memória com 12 elementos de exemplo), põe `API_MOCK=true`.

**Dashboard:**

```bash
cp dashboard/.env.example dashboard/.env
```

Gera a `APP_KEY` do Laravel e cola-a no `dashboard/.env`:

```bash
docker compose build dashboard
docker compose run --rm --no-deps dashboard php artisan key:generate --show
```

Para o separador de importação da Mapillary, acrescenta ao `dashboard/.env`:

```env
MAPILLARY_ACCESS_TOKEN=
```

`API_URL`, `API_PUBLIC_URL` e `APP_URL` são definidos no `docker-compose.yml`; não é preciso
pô-los no `.env`.

### 5. Construir e arrancar

```bash
docker compose up --build
```

A primeira build demora alguns minutos (PyTorch, dependências PHP/Node). Depois de arrancar:

| URL | O quê |
|---|---|
| http://localhost:8080 | Dashboard |
| http://localhost:8000/docs | API — documentação interativa (Swagger) |
| http://localhost:8001/health | ML — health check |
| `localhost:5432` | PostgreSQL (utilizador/palavra-passe do `api/.env`) |

### 6. Opções úteis

As variáveis seguintes podem ser passadas na linha de comandos ou num ficheiro `.env` na raiz:

| Variável | Omissão | Efeito |
|---|---|---|
| `ML_MOCK` | `false` | `true` = ML falso, não precisa de pesos |
| `ML_DEVICE` | `auto` | `cpu`, `cuda:0` ou `auto` |
| `TORCH_VARIANT` | `cpu` | Build do PyTorch (ex.: `cu124` para CUDA) — requer rebuild |
| `POSTGRES_PORT` | `5432` | Porta do PostgreSQL no host (mudar se já tiveres um Postgres local) |

```bash
ML_MOCK=true docker compose up --build              # sem modelos
TORCH_VARIANT=cu124 docker compose build ml         # PyTorch com CUDA
```

### 7. Parar e limpar

```bash
docker compose down        # pára os contentores, mantém os dados
docker compose down -v     # apaga também a base de dados, as imagens partilhadas e a cache HF
```

Depois de alterar modelos da base de dados na API é preciso `docker compose down -v` (ver
[api/README.md](api/README.md#changing-models)).

## Problemas comuns

- **Porta ocupada** (`bind: address already in use`): outro serviço usa 5432, 8000, 8001 ou
  8080. Para o Postgres usa `POSTGRES_PORT=5433`; para as outras, altera o mapeamento em
  `docker-compose.yml`.
- **`env file ... not found`:** falta `api/.env` ou `dashboard/.env` (passo 4).
- **Dashboard com erro `No application encryption key`:** a `APP_KEY` está vazia (passo 4).
- **ML reinicia com `Face detector ONNX not found`:** faltam pesos em `ml/weights/` — adiciona-os
  ou arranca com `ML_MOCK=true`.
- **Upload de vídeo longo dá timeout:** os pedidos são síncronos; o ML tem até 900 s
  (`ML_VIDEO_TIMEOUT_S` no `api/.env`).

## Desenvolvimento local (sem Docker)

Cada serviço pode correr diretamente no host — ver [api/README.md](api/README.md) para a API e
o ML (`uv run ...`). Para o dashboard:

```bash
cd dashboard
composer install && npm install
php artisan key:generate && php artisan migrate
composer run dev     # ou: php artisan serve + npm run dev
```

Nesse caso define `API_URL=http://localhost:8000/api/v1/` no `dashboard/.env`.
