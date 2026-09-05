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

## Discuter avec l'agent (Epic 3)

L'orchestrateur agentique est construit avec **LangGraph** (boucle LLM ↔ outils comme un graphe d'états) et **Ollama** en local par défaut (`LLM_PROVIDER=ollama`, `LLM_MODEL=llama3.1:8b` dans `.env` — nécessite `ollama pull llama3.1:8b` et Ollama lancé sur la machine hôte).

```bash
curl -N -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "demo-1", "message": "Pourquoi le paiement echoue ?"}'
```

La réponse est streamée en Server-Sent Events (`event: start`, `event: delta` répétés, `event: done`). L'historique de conversation est conservé en mémoire pour la durée de vie du processus, indexé par `conversation_id` (remplaçable par un checkpointer Postgres sans toucher à `agent/orchestrator.py`). Le seul outil branché pour l'instant est `search_knowledge` (réutilise `rag/retriever.py`, Epic 1) ; `send_email` viendra avec le gating (Epic 4).

## Autonomie configurable (gating, Epic 4)

Le module `gating` ajoute un deuxième outil, `send_email` — le premier qui **agit** dans le monde plutôt que de seulement lire la base de connaissances. Son niveau d'autonomie se règle par type d'action via `GATING_POLICY` (`.env`), sans toucher au code :

```bash
# .env
GATING_POLICY={"send_email": "require_validation"}   # défaut : un humain valide avant l'envoi
GATING_POLICY={"send_email": "auto_execute"}          # démo : envoi immédiat, sans validation
GATING_POLICY={"send_email": "suggest_only"}          # l'agent propose sans jamais agir
```

Avec `require_validation` (défaut), le flux `POST /agent/chat` se termine par `event: pending_approval` (au lieu de `event: done`) dès que l'agent propose d'envoyer un email — le graphe LangGraph est interrompu via `interrupt()`, son état persisté par le checkpointer, en attente d'une décision :

```bash
curl http://localhost:8000/gating/pending

curl -X POST http://localhost:8000/gating/1/decide \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve"}'
```

`approve` reprend le graphe interrompu (`Command(resume=...)`) et exécute réellement l'envoi ; `reject` le reprend sans jamais exécuter l'action — dans les deux cas l'agent termine sa réponse. Changer `GATING_POLICY` en `auto_execute` et relancer l'API fait disparaître l'interruption sans aucune modification de `agent/orchestrator.py` ni `gating/` : c'est la démonstration chiffrée que le curseur de confiance est un paramètre de configuration, pas une réécriture (US-406).

Voir [`management/gating-field-manual.pdf`](../management/gating-field-manual.pdf) pour l'architecture détaillée (diagrammes de classes, de séquence et d'activité).

## Traçabilité (audit, Epic 5)

Le module `audit` journalise, dans la table persistante `audit_logs`, chaque appel LLM (`agent.llm_call`), proposition d'action (`agent.action_proposed`) et décision de validation (`gating.decision`) — c'est le point de passage obligé (`audit.service.write_log`) utilisé par `agent` et `gating`, jamais contourné.

```bash
curl http://localhost:8000/audit/logs
curl "http://localhost:8000/audit/logs?event_type=gating.decision"
```
