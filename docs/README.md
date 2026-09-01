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

Le code n'existe pas encore. Avant de commencer à développer :

- [Comprendre le RAG avant de coder](epic-1/00-guide-debutant-rag.md) ([version PDF imprimable](epic-1/guide-debutant-rag.pdf)) — RAG, exemples réels (ChatGPT, Copilot, Perplexity, Glean...), embeddings, chunking, calcul de similarité cosinus pas à pas, pgvector, glossaire, mapping user story → fichier
- [Modèle d'embedding local — MiniLM](epic-1/01-modele-local-minilm.md) ([version PDF imprimable](epic-1/modele-local-minilm.pdf)) — décision retenue (modèle local), LLM vs modèle d'embedding, toutes les classes Python détaillées (`EmbeddingProvider`, `LocalMiniLMEmbeddingProvider`, fabrique, fake de test), diagrammes de classes/séquence, impact Docker

### Epics suivants

Pas encore documentés — ce dossier sera complété au fur et à mesure de l'avancement du backlog (Epic 2 : connecteurs, Epic 3 : agent, etc.).
