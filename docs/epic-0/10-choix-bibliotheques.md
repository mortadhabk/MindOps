# Choix des bibliothèques

## Gestion de projet et dépendances : `uv`

| | |
|---|---|
| Rôle | Gestionnaire de paquets, d'environnement virtuel et d'exécution Python |
| Alternative écartée | `pip` + `venv` manuel, ou `poetry` |

`uv` a été choisi parce qu'il unifie en un seul outil ce que `pip`/`venv`/`poetry` couvrent séparément : création du `.venv`, résolution et verrouillage des dépendances (`uv.lock`), installation, et exécution (`uv run ...`) — avec des temps de résolution/installation nettement plus rapides. Un seul outil à documenter pour toute l'équipe, et le fichier `uv.lock` garantit des builds reproductibles (y compris dans `Dockerfile` et la CI).

`pyproject.toml` déclare `[tool.uv] package = false` : ce projet est une **application**, pas une bibliothèque destinée à être importée ailleurs — `uv` gère alors uniquement l'environnement et les dépendances, sans essayer de construire/installer le code de `app/` comme un paquet Python distribuable.

## Framework web : `FastAPI` + `uvicorn`

| | |
|---|---|
| Rôle | Serveur HTTP async, routing, validation des requêtes/réponses |
| Alternative écartée | Flask (pas async-natif), Django (trop lourd pour ce périmètre) |

Choix explicite du backlog. `FastAPI` est construit sur Starlette (ASGI) et Pydantic : validation automatique des schémas d'entrée/sortie, documentation OpenAPI générée sans effort, et un modèle async qui correspond au reste de la stack (SQLAlchemy async, appels LLM/API externes non bloquants pour l'agent). `uvicorn` est le serveur ASGI de référence pour faire tourner une application FastAPI.

## Validation et configuration : `Pydantic v2` + `pydantic-settings`

| | |
|---|---|
| Rôle | Schémas de données (requêtes/réponses API, futurs `DocumentIn`/`ChatRequest`...) et configuration typée depuis l'environnement |
| Alternative écartée | `dataclasses` + validation manuelle, `python-decouple` pour la config |

Pydantic v2 est déjà une dépendance de FastAPI — le choisir aussi pour la configuration (`pydantic-settings`) évite d'introduire un deuxième système de validation. Détails d'usage dans [03-configuration.md](03-configuration.md).

## Base de données : `SQLAlchemy 2.0 (async)` + `asyncpg` + `Alembic`

| | |
|---|---|
| Rôle | ORM async (SQLAlchemy), driver PostgreSQL (asyncpg), migrations versionnées (Alembic) |
| Alternative écartée | Requêtes SQL brutes, `psycopg2` (synchrone), Django ORM (couplé à Django) |

- **SQLAlchemy 2.0** est l'ORM Python le plus mature, avec un mode async de première classe (`AsyncSession`, `async_sessionmaker`) qui s'intègre naturellement à FastAPI/uvicorn.
- **`asyncpg`** est le driver PostgreSQL asynchrone le plus rapide de l'écosystème Python — c'est le choix standard pour SQLAlchemy async + Postgres.
- **Alembic** est l'outil de migration officiellement associé à SQLAlchemy, avec un template async dédié (utilisé ici, voir [04-base-de-donnees-migrations.md](04-base-de-donnees-migrations.md)) qui évite d'écrire à la main la mécanique de migration sur un engine asynchrone.

## Base vectorielle : `pgvector` (extension Postgres + paquet Python)

| | |
|---|---|
| Rôle | Stockage et recherche par similarité d'embeddings (Epic 1 — RAG) |
| Alternative écartée | Pinecone, Weaviate, Qdrant, Milvus (services vectoriels dédiés) |

Choix explicite et assumé du backlog : *"un seul service à faire tourner en local, pas de dépendance à un fournisseur externe pour le POC"*. Plutôt qu'une base vectorielle séparée à opérer, `pgvector` ajoute un type `vector` et des opérateurs de similarité directement dans Postgres — la même base qui stocke déjà le reste des données de l'application. Mis en place dès l'Epic 0 (image `pgvector/pgvector:pg16`, extension activable) bien qu'aucune table ne l'utilise encore.

## Tests : `pytest` + `pytest-asyncio` + `httpx`

| | |
|---|---|
| Rôle | Framework de test, support des tests `async def`, client HTTP pour tester l'API |
| Alternative écartée | `unittest` (plus verbeux), `requests` (synchrone, pas adapté à une app async) |

`pytest` est le standard de facto en Python. `pytest-asyncio` (en mode `auto`, voir [08-tests.md](08-tests.md)) permet d'écrire des tests `async def` sans cérémonie. `httpx.AsyncClient` avec `ASGITransport` permet de tester l'application FastAPI en mémoire, sans serveur réseau réel — rapide et fiable en CI.

## Qualité de code : `ruff`

| | |
|---|---|
| Rôle | Lint + tri des imports (remplace flake8, isort, et une partie de pyupgrade) |
| Alternative écartée | flake8 + isort + black séparément |

Un seul outil, écrit en Rust (donc très rapide), qui couvre le lint (`E`, `F`), le tri des imports (`I`), la modernisation de syntaxe (`UP`) et les bonnes pratiques courantes (`B`, bugbear) avec une seule section de configuration dans `pyproject.toml`. Réduit la surface de configuration et le nombre d'outils à maintenir en CI.

## Conteneurisation : `Docker` + `Docker Compose`

| | |
|---|---|
| Rôle | Environnement reproductible (Postgres+pgvector, API), démarrage en une commande |
| Alternative écartée | Installation manuelle de Postgres sur chaque machine de dev |

Exigence explicite du backlog (US-003) : quiconque clone le projet doit pouvoir lancer `docker compose up` et obtenir un environnement complet, sans installer Postgres/pgvector à la main. Détails dans [09-docker-ci-cd.md](09-docker-ci-cd.md), y compris une limitation réseau spécifique à Docker Desktop for Windows rencontrée pendant l'implémentation.

## Tableau récapitulatif

| Bibliothèque | Rôle | Epic qui en dépend |
|---|---|---|
| `fastapi`, `uvicorn` | Serveur HTTP async | Toutes |
| `pydantic-settings` | Configuration typée | Epic 0 |
| `sqlalchemy[asyncio]`, `asyncpg` | ORM + driver Postgres async | Epic 0 (infra), 1, 4, 5 |
| `alembic` | Migrations versionnées | Epic 0 (infra), 1, 4, 5 |
| `pgvector` | Recherche vectorielle | Epic 1 |
| `pytest`, `pytest-asyncio`, `httpx` | Tests | Toutes |
| `ruff` | Lint | Toutes |
| `uv` | Gestion de paquets/environnement | Toutes |

Les bibliothèques propres à chaque epic futur (client LLM pour l'Epic 3, client HTTP GitHub pour l'Epic 2, client d'envoi d'email pour l'Epic 4) ne sont pas encore ajoutées à `pyproject.toml` — elles le seront au moment de leur implémentation, avec la même justification que ci-dessus. Voir [11-prochaines-etapes.md](11-prochaines-etapes.md).
