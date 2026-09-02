# ai-agent-poc

Socle agentique modulaire (RAG + connecteurs + orchestration + politique de confiance configurable) — POC réutilisable. Voir [`management/backlog.md`](../management/backlog.md) pour la vision, l'architecture et le backlog complet.

## Démarrage rapide

```bash
cp .env.example .env
docker compose up -d
docker compose exec api uv run alembic upgrade head
```

L'API est alors disponible sur http://localhost:8000, avec un contrôle de santé sur `GET /health`.

## Développement local (sans Docker pour l'API)

```bash
uv sync
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Tests

```bash
docker compose exec api uv run pytest
```

(ou en local : `uv run pytest`, une fois la base de données démarrée et migrée).

## Lint

```bash
uv run ruff check .
```

## Architecture

Monolithe modulaire en architecture hexagonale (ports & adapters) : chaque module métier (`rag`, `connectors`, `agent`, `gating`, `audit`) est isolé, avec une règle de dépendance à sens unique :

```
connectors  →  (indépendant)
rag         →  (indépendant)
gating      →  audit
agent       →  rag, gating, audit
api         →  agrège tous les routers, aucune logique métier
core        →  transverse (config, logging, exceptions, database)
```

## Ajouter un connecteur

Trois étapes, illustrées par le connecteur GitHub Issues (`app/connectors/github/`) :

1. **Implémenter l'interface** `Connector` (`app/connectors/base.py`) : `fetch_items(**params)` récupère les items bruts depuis la source externe, `to_document(item)` les convertit en `DocumentIn` (réutilisé tel quel par le pipeline d'ingestion du module `rag`).
2. **Enregistrer** le connecteur dans `app/connectors/registry.py` (dictionnaire nom → instance). Aucun autre module n'importe une implémentation concrète (`github/`, `mock/`) directement — uniquement `connectors/base.py` et `connectors/registry.py`.
3. **Tester** en s'inspirant de `app/connectors/mock/` (aucun appel réseau, données fixes) pour valider le pipeline connecteur → RAG, puis un test dédié qui mock les appels HTTP du connecteur réel (voir `tests/connectors/test_github_connector.py`).

Synchronisation : `POST /connectors/{name}/sync` avec un corps JSON portant les paramètres propres au connecteur (ex : `{"owner": "acme", "repo": "demo"}` pour GitHub).

## Autonomie configurable (gating)

À compléter à l'implémentation du module `gating` (Epic 4) : basculer la politique de confiance d'un type d'action (`suggest_only` / `require_validation` / `auto_execute`) sans changement de code.
