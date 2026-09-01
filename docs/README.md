# Documentation — ai-agent-poc

Documentation technique du projet, en complément du [backlog](../management/backlog.md) qui définit la vision, l'architecture cible et les user stories.

Le code vit sous [`dev/`](../dev), qui est la racine réelle du projet Python (là où se trouvent `pyproject.toml`, `app/`, `tests/`, etc.). Le backlog nomme cette racine `ai-agent-poc/` — dans ce dépôt, c'est `dev/`.

## Sommaire

### Epic 0 — Socle technique et infrastructure

Documentation complète de ce qui a été mis en place pour le Sprint 1 (US-001 à US-008) :

1. [Vue d'ensemble](epic-0/01-vue-ensemble.md) — objectifs, arborescence, statut des user stories, démarrage rapide
2. [Architecture hexagonale](epic-0/02-architecture-hexagonale.md) — règle de dépendance entre modules, agrégation des routers
3. [Configuration](epic-0/03-configuration.md) — `Settings`, variables d'environnement
4. [Base de données et migrations](epic-0/04-base-de-donnees-migrations.md) — SQLAlchemy async, Alembic, pgvector
5. [Logging et observabilité](epic-0/05-logging-observabilite.md) — logs JSON, request ID
6. [Gestion des erreurs](epic-0/06-gestion-erreurs.md) — exceptions métier, handlers FastAPI
7. [API et point d'entrée](epic-0/07-api-main.md) — `main.py`, agrégateur de routers
8. [Tests](epic-0/08-tests.md) — fixtures, client HTTP async
9. [Docker et CI/CD](epic-0/09-docker-ci-cd.md) — Compose, Dockerfile, GitHub Actions, incident réseau Windows
10. [Choix des bibliothèques](epic-0/10-choix-bibliotheques.md) — pourquoi chaque dépendance
11. [Prochaines étapes](epic-0/11-prochaines-etapes.md) — Epics 1 à 7, décisions en attente

### Epic 1 — Moteur RAG

US-101 à US-107 implémentées (`app/rag/`). Avant/pendant la lecture du code :

0. [Comprendre le RAG avant de coder](epic-1/00-guide-debutant-rag.md) ([PDF](epic-1/guide-debutant-rag.pdf)) — RAG, exemples réels (ChatGPT, Copilot, Perplexity, Glean...), embeddings, chunking, calcul de similarité cosinus pas à pas, pgvector, glossaire, mapping user story → fichier
1. [Modèle d'embedding local — MiniLM](epic-1/01-modele-local-minilm.md) ([PDF](epic-1/modele-local-minilm.pdf)) — LLM vs modèle d'embedding, toutes les classes Python (`EmbeddingProvider`, `LocalMiniLMEmbeddingProvider`, fabrique, fake de test), **mise à jour post-implémentation** : correction du modèle (anglophone → multilingue) après test sur du vrai français
2. [Modèles et ingestion](epic-1/02-modeles-et-ingestion.md) — `Document`/`Chunk` (US-101), `chunk_text` et son choix de découper par mots plutôt que par vrais tokens (US-102), pipeline d'ingestion et statut `partial` (US-103)
3. [Recherche et API](epic-1/03-recherche-et-api.md) — `vector_store.py`, `retriever.search` et le seuil de similarité (US-104), schémas Pydantic, `POST /rag/ingest` / `GET /rag/search` (US-105, US-106)
4. [Tests](epic-1/04-tests.md) — `FakeEmbeddingProvider`, un bug corrigé dans la fixture `db_session` de l'Epic 0 (les `commit()` n'étaient pas annulés), tous les tests écrits (US-107)

### Epics suivants

Pas encore documentés — ce dossier sera complété au fur et à mesure de l'avancement du backlog (Epic 2 : connecteurs, Epic 3 : agent, etc.).
