# ai-agent-poc

Socle agentique modulaire (RAG + connecteurs + orchestration + politique de confiance configurable) — POC réutilisable. Voir [`management/backlog.md`](../management/backlog.md) pour la vision, l'architecture et le backlog complet.

## Démarrage rapide

```bash
cp .env.example .env
cd frontend && npm install && npm run build && cd ..   # build de l'interface de démo (Epic 6)
docker compose up -d
docker compose exec api uv run alembic upgrade head
```

L'API est alors disponible sur http://localhost:8000, avec un contrôle de santé sur `GET /health`. Interface de démo (chat + gating + audit) sur http://localhost:8000/demo/ — voir la section [Interface de démo](#interface-de-démo-epic-6) plus bas.

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

## Interface de démo (Epic 6)

Une SPA React + TypeScript + Tailwind (`frontend/`), buildée avec Vite, réunit en un seul écran les trois modules développés jusqu'ici (US-601, US-602) :

- **Chat** : discute avec l'agent, réponse streamée token par token (même flux SSE que `POST /agent/chat`, consommé "à la main" via `fetch` + lecture du corps — `EventSource` ne supporte pas les requêtes `POST`).
- **File de validation** : liste les `ActionProposal` en attente (`GET /gating/pending`), avec un bouton Approuver/Rejeter par ligne (`POST /gating/{id}/decide`) — se rafraîchit automatiquement dès qu'un `event: pending_approval` arrive dans le chat.
- **Journal d'audit** : les événements les plus récents (`GET /audit/logs`), filtrables par type d'événement.

`frontend/vite.config.ts` écrit le build directement dans `app/static/` (déjà monté sur `/demo` par `app/main.py`, déjà bind-monté par `docker-compose.yml`) — `app/static/` est donc un **répertoire généré**, jamais commité (voir `.gitignore`). Il faut le construire au moins une fois avant de démarrer l'API :

```bash
cd frontend
npm install
npm run build   # écrit dans ../app/static — à refaire après chaque modification du front
```

Pour itérer sur le front avec rechargement à chaud (API déjà lancée sur :8000, via Docker ou en local) :

```bash
cd frontend
npm run dev   # http://localhost:5173, proxy /agent /gating /audit /health vers :8000
```

```
http://localhost:8000/demo/
```

## Studio de connecteurs (Epic 8)

Un second onglet dans `/demo` (« Studio ») ajoute une interface graphique pour brancher des sources de données sur l'Orchestrateur, sans écrire de code ni appeler l'API à la main — voir la proposition complète dans [`management/epic-8-studio-connecteurs.md`](../management/epic-8-studio-connecteurs.md).

- **Canvas** (React Flow, `@xyflow/react`) : un nœud « Orchestrateur » fixe, relié par des arêtes aux sources configurées.
- **Palette** : glisser un type de connecteur (Document, GitHub Issues, SharePoint) sur le canvas ouvre un formulaire de configuration **généré automatiquement** depuis le JSON Schema de `Connector.config_schema` — aucune duplication de la définition des champs entre back et front. Pour **Document**, le formulaire propose en plus un dépôt de fichier (texte brut, `.pdf`, `.docx`) ou un collage direct, avec extraction du texte côté serveur (`pypdf`, `python-docx` — voir `POST /connectors/document/extract-text`).
- Chaque nœud affiche son statut (`idle` / `syncing` / `success` / `error`), le nombre de documents synchronisés, et propose Synchroniser/Supprimer directement.
- Nouveaux endpoints : `GET /connectors/types`, `GET/POST /connectors/instances`, `PATCH`/`DELETE /connectors/instances/{id}`, `POST /connectors/instances/{id}/sync` (tâche de fond — la réponse revient immédiatement avec `status: "syncing"`, le Studio interroge ensuite par polling).
- **Sécurité** : aucun secret ne transite par le navigateur ni ne se stocke en base — `credential_alias` (ex. pour SharePoint) pointe vers des identifiants déjà présents côté serveur (`.env`), jamais saisis dans le formulaire.
- Le connecteur `sharepoint` est pour l'instant un **mock fidèle** (même `config_schema`, même contrat `Connector` que la future implémentation Microsoft Graph API) — voir la section 4.3 de la proposition pour la portée MVP/V2.

## Traçabilité (audit, Epic 5)

Le module `audit` journalise, dans la table persistante `audit_logs`, chaque appel LLM (`agent.llm_call`), proposition d'action (`agent.action_proposed`) et décision de validation (`gating.decision`) — c'est le point de passage obligé (`audit.service.write_log`) utilisé par `agent` et `gating`, jamais contourné.

```bash
curl http://localhost:8000/audit/logs
curl "http://localhost:8000/audit/logs?event_type=gating.decision"
```
