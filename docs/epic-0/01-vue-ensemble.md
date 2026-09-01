# Epic 0 — Vue d'ensemble

## Pourquoi commencer par là

Le backlog est explicite sur l'ordre d'exécution :

> Sprint 1 — Socle technique (Epic 0) : rien d'autre n'avance sans ça.

Avant d'écrire la moindre ligne de RAG, de connecteur ou d'agent, il fallait un squelette d'application qui :
- se lance en une commande,
- charge sa configuration depuis l'environnement (jamais de secret en dur),
- persiste des données via des migrations versionnées,
- journalise de façon exploitable,
- renvoie des erreurs cohérentes,
- et peut être testé automatiquement.

C'est tout l'objet de l'Epic 0 (US-001 à US-008). Chaque epic suivant (RAG, connecteurs, agent, gating, audit) viendra se brancher sur ce socle sans le remodeler.

## Où vit le code

Le backlog décrit une racine `ai-agent-poc/`. Dans ce dépôt, cette racine est **`dev/`** — c'est là que se trouvent `pyproject.toml`, `app/`, `tests/`, `alembic/`, `docker-compose.yml`. Tous les chemins de cette documentation sont relatifs à `dev/` sauf mention contraire.

Deux dossiers vides (`dev/FastAPI`, `dev/routers`) préexistaient avant l'implémentation et ne correspondaient à aucune structure du backlog — ils ont été supprimés pour repartir sur l'arborescence exacte décrite dans le backlog.

## Arborescence mise en place

```
dev/
├── app/
│   ├── __init__.py                # fix event loop Windows (voir 09-docker-ci-cd.md)
│   ├── main.py                    # point d'entrée FastAPI
│   ├── config.py                  # Settings (pydantic-settings)
│   │
│   ├── core/                      # transverse, zéro logique métier
│   │   ├── database.py            # engine async, Base declarative, get_db()
│   │   ├── logging.py             # JSON formatter + middleware request-id
│   │   └── exceptions.py          # exceptions custom + handlers FastAPI
│   │
│   ├── rag/                       # MODULE — vide, Epic 1
│   ├── connectors/                # MODULE — vide, Epic 2
│   │   ├── github/
│   │   └── mock/
│   ├── agent/                     # MODULE — vide, Epic 3
│   │   └── tools/
│   ├── gating/                    # MODULE — vide, Epic 4
│   ├── audit/                     # MODULE — vide, Epic 5
│   │
│   └── api/
│       └── router.py              # agrégateur, vide pour l'instant
│
├── alembic/
│   ├── env.py                     # branché sur app.config + app.core.database
│   └── versions/
│       └── 88a87d7eae19_initial_schema.py   # migration vide (rien à créer encore)
│
├── tests/
│   ├── conftest.py                # fixtures db_session + client
│   ├── test_health.py
│   └── {rag,connectors,agent,gating}/       # vides, prêts pour les epics suivants
│
├── docker-compose.yml              # postgres+pgvector, api
├── Dockerfile
├── pyproject.toml                  # deps + config ruff/pytest
├── .env.example
├── .gitignore
└── README.md

.github/
└── workflows/
    └── ci.yml                      # à la racine du dépôt git (pas dans dev/)
```

Chaque dossier de module métier (`rag`, `connectors`, `agent`, `gating`, `audit`) contient uniquement un `__init__.py` pour l'instant : c'est un dossier vide au sens de l'US-001, prêt à recevoir ses fichiers (`models.py`, `router.py`, etc.) quand son epic sera implémenté.

## Statut des user stories

| US | Titre | Statut |
|----|-------|--------|
| US-001 | Initialiser la structure du projet FastAPI | ✅ |
| US-002 | Centraliser la configuration | ✅ |
| US-003 | Mettre en place Docker Compose | ✅ |
| US-004 | Mettre en place les migrations de base de données | ✅ |
| US-005 | Mettre en place le logging structuré | ✅ |
| US-006 | Centraliser la gestion des erreurs | ✅ |
| US-007 | Mettre en place la structure de tests | ✅ |
| US-008 | Pipeline de vérification basique (lint + CI) | ✅ |

Chaque US est détaillée dans le fichier correspondant de ce dossier.

## Démarrage rapide

```bash
cd dev
cp .env.example .env
docker compose up -d
docker compose exec api uv run alembic upgrade head
curl http://localhost:8000/health
# {"status":"ok"}
```

En local sans conteneuriser l'API (utile pour le développement avec rechargement automatique) :

```bash
cd dev
uv sync
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Tests et lint :

```bash
docker compose exec api uv run pytest
uv run ruff check .
```

Le détail de chaque commande et de ce qu'elle déclenche est expliqué dans les fichiers suivants de ce dossier.
