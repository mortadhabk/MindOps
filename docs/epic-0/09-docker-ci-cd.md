# Docker, Docker Compose et CI (US-003, US-008)

## Fichier : `docker-compose.yml`

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ai_agent_poc
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/ai_agent_poc
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./app:/code/app
      - ./tests:/code/tests

volumes:
  pgdata:
```

### Choix expliqués

- **`pgvector/pgvector:pg16`** au lieu de l'image `postgres:16` officielle : image Postgres 16 avec l'extension `pgvector` déjà compilée dedans. Nécessaire pour le RAG (Epic 1), mise en place dès maintenant pour ne pas avoir à changer d'image plus tard.
- **`healthcheck` sur `db`** + **`depends_on: condition: service_healthy`** sur `api` : `depends_on` seul garantit seulement que le conteneur `db` a *démarré*, pas que Postgres *accepte déjà des connexions*. Sans le healthcheck, l'API pourrait démarrer et tenter de se connecter avant que Postgres soit prêt. `pg_isready` est la commande standard pour ce healthcheck.
- **`DATABASE_URL` recalculée pour `api`** (`@db:5432` au lieu de `@localhost:5432`) : à l'intérieur du réseau Docker Compose, les services se joignent par leur **nom de service** (`db`), pas par `localhost`. C'est une valeur différente de celle de `.env`/`.env.example` (pensée pour un usage depuis l'hôte), d'où la surcharge explicite dans `environment:`.
- **`volumes: ./app:/code/app` et `./tests:/code/tests`** : montage du code source en direct dans le conteneur, pour que les modifications sur l'hôte soient visibles sans reconstruire l'image — pratique de développement, pas destiné à la production (voir US-703, Epic 7).
- **`volumes: pgdata`** (volume nommé) : les données Postgres survivent à un `docker compose down` (mais pas à `docker compose down -v`).

## Fichier : `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /code

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- **`python:3.12-slim`** : cible stable et bien supportée par tout l'écosystème (`asyncpg`, `sqlalchemy`) — indépendante de la version de Python installée sur la machine hôte (ici Python 3.14 en local, voir [10-choix-bibliotheques.md](10-choix-bibliotheques.md)).
- **`COPY pyproject.toml uv.lock ./` puis `uv sync --no-dev` avant `COPY app`** : ordre pensé pour le cache Docker — tant que les dépendances ne changent pas, cette étape (la plus lente) reste en cache même si le code applicatif change à chaque build.
- **`--no-dev`** : `ruff`, `pytest`, `pytest-asyncio`, `httpx` (groupe `dev`) ne sont pas nécessaires pour *faire tourner* l'API — seulement pour la développer/tester. Une image d'exécution plus légère.
- **`CMD [..., "uv", "run", "--no-sync", ...]`** : voir l'incident ci-dessous — sans `--no-sync`, `uv run` re-synchronise l'environnement (et réinstalle donc les dépendances `dev`) à chaque démarrage du conteneur.

Ce Dockerfile est volontairement simple (US-003 : "faire tourner l'environnement complet en une commande"). Une image de production optimisée (multi-stage, pas de reload, utilisateur non-root) est explicitement prévue plus tard par le backlog (US-703, Epic 7).

## Incident : connexion refusée depuis Windows vers Docker Desktop

En travaillant sur l'US-004 (migrations Alembic) sur cette machine, `uv run alembic upgrade head` échouait de façon répétée et déterministe :

```
asyncpg.exceptions.ConnectionDoesNotExistError: connection was closed in the middle of operation
```

### Démarche de diagnostic

1. **Écarté : un bug dans notre code.** Le même échec se reproduit avec un script `asyncpg.connect(...)` minimal, sans Alembic ni SQLAlchemy.
2. **Écarté : la politique de boucle d'événements Windows (`ProactorEventLoop`).** C'est un problème connu d'`asyncpg` sur Windows ; on a forcé `WindowsSelectorEventLoopPolicy` (voir plus bas, `app/__init__.py`) — l'erreur a changé de forme (`WinError 10054`, reset de connexion) mais persistait.
3. **Écarté : un problème réseau bas niveau.** `Test-NetConnection -ComputerName localhost -Port 5432` réussit : le port répond, le handshake TCP fonctionne.
4. **Écarté : un problème de protocole PostgreSQL.** Un script Python en socket brut, rejouant le protocole PostgreSQL à la main (négociation SSL, paquet de démarrage), obtient bien une réponse d'authentification (`SCRAM-SHA-256`) — la conversation applicative démarre correctement.
5. **Confirmé : un autre driver échoue pareil.** `psycopg2` (synchrone, sans rapport avec `asyncio`) échoue également en tentant de se connecter au même port.

### Conclusion

Le problème n'est ni dans le code applicatif, ni dans SQLAlchemy/Alembic/asyncpg, ni dans la configuration Postgres — c'est une instabilité du **port-forwarding de Docker Desktop entre Windows et le conteneur** sur cette machine (le trajet `localhost:5432` (hôte) → conteneur `db`), qui coupe la connexion après les tout premiers échanges applicatifs, de façon reproductible avec plusieurs clients différents.

### Solution adoptée

Faire tourner tout ce qui doit parler à Postgres **à l'intérieur du réseau Docker Compose**, pas depuis l'hôte Windows :

```bash
docker compose exec api uv run alembic upgrade head
docker compose exec api uv run pytest
```

Le trajet `conteneur api` → `conteneur db` passe par le réseau interne Docker (`dev_default`), jamais par le port-forwarding Windows — et fonctionne de façon fiable. Le endpoint HTTP `/health`, lui, continue de fonctionner normalement via `localhost:8000` depuis l'hôte : le problème est spécifique au protocole PostgreSQL (probablement lié au motif d'échange de paquets pendant l'authentification SCRAM), pas à toutes les connexions TCP en général.

**Cette limitation est spécifique à cette machine/cet environnement Docker Desktop**, pas au projet : la CI GitHub Actions ([ci.yml](#fichier--githubworkflowsciyml), ci-dessous) fait tourner Postgres comme service natif à côté du runner Linux, sans passer par Docker Desktop for Windows — elle n'est donc pas concernée.

### Le fix conservé malgré tout : `app/__init__.py`

```python
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

Même si ce n'était pas la cause racine du problème ci-dessus, `asyncpg` a un historique documenté d'incompatibilités avec `ProactorEventLoop` (la boucle par défaut d'`asyncio` sur Windows) — la remplacer par `SelectorEventLoop` reste une bonne pratique standard pour tout projet `asyncpg` + Windows, sans coût pour Linux/macOS (`sys.platform == "win32"` protège les autres plateformes). Conservé par prudence.

## Fichier : `.github/workflows/ci.yml` (US-008)

> Placé à la racine du dépôt Git (`MindOps/.github/workflows/`), **pas** dans `dev/` — GitHub Actions ne découvre les workflows qu'à la racine du dépôt, quel que soit l'endroit où vit le code applicatif.

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  lint-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dev
    services:
      db:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: ai_agent_poc
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent_poc
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Install dependencies
        run: uv sync
      - name: Lint
        run: uv run ruff check .
      - name: Enable pgvector extension
        run: |
          sudo apt-get update && sudo apt-get install -y postgresql-client
          PGPASSWORD=postgres psql -h localhost -U postgres -d ai_agent_poc -c "CREATE EXTENSION IF NOT EXISTS vector;"
      - name: Run migrations
        run: uv run alembic upgrade head
      - name: Test
        run: uv run pytest
```

- **`defaults.run.working-directory: dev`** : toutes les commandes (`uv sync`, `ruff check`, ...) s'exécutent dans `dev/`, puisque c'est là que vit `pyproject.toml`.
- **`services.db`** : GitHub Actions démarre Postgres+pgvector comme conteneur de service à côté du job, accessible sur `localhost:5432` depuis le runner (mécanisme natif GitHub Actions, sans rapport avec Docker Desktop for Windows).
- **Ordre des étapes** : lint avant tout (rapide, échoue vite si le code n'est pas propre), puis activation de `pgvector` (nécessaire une fois par base fraîche), puis migrations, puis tests — chaque étape suppose que la précédente a réussi.

## Topologie Docker Compose

```mermaid
graph TB
    subgraph Host["Machine hôte (Windows)"]
        Dev["Développeur<br/>uv run ruff / pytest<br/>(hors DB)"]
        Browser["curl / navigateur"]
    end

    subgraph Compose["Réseau Docker Compose (dev_default)"]
        API["conteneur api<br/>uvicorn :8000"]
        DB["conteneur db<br/>pgvector/pgvector:pg16<br/>:5432"]
        VOL[("volume pgdata")]
    end

    Browser -->|"localhost:8000"| API
    API -->|"db:5432<br/>(réseau interne, fiable)"| DB
    DB --- VOL
    Dev -.->|"docker compose exec api ...<br/>(alembic, pytest)"| API
    Dev -.->|"localhost:5432<br/>(instable sur cette machine, voir incident)"| DB
```

## Commandes de référence

```bash
# Démarrer toute la stack
docker compose up -d

# Migrations et tests, à l'intérieur du réseau Docker (fiable)
docker compose exec api uv run alembic upgrade head
docker compose exec api uv run pytest

# Logs
docker compose logs -f api

# Arrêter (garde les données)
docker compose down

# Arrêter et supprimer les données
docker compose down -v
```
