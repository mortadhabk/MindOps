# Connecter DBeaver à la base Postgres du projet (Docker local)

Le conteneur `dev-db-1` (image `pgvector/pgvector:pg16`, définie dans `dev/docker-compose.yml`) expose son port sur la machine hôte — DBeaver s'y connecte exactement comme à un Postgres installé nativement, sans rien configurer côté Docker.

> **Pourquoi le port est 5442 et pas 5432.** Sur cette machine, un Postgres natif Windows (`postgres.exe`, hors Docker — probablement installé par un autre outil) écoute déjà sur `0.0.0.0:5432`, en même temps que le port-forward de Docker Desktop qui écoute lui en IPv6 (`::`) sur ce même port 5432. Selon la façon dont `localhost` se résout, une connexion pouvait atterrir sur l'un ou sur l'autre — ce qui explique les coupures et erreurs aléatoires rencontrées plus tôt (y compris hors DBeaver, avec `curl`/`asyncpg`/`Invoke-RestMethod`). `dev/docker-compose.yml` expose donc désormais le conteneur sur le port hôte **5442** (le conteneur écoute toujours en interne sur 5432, seul le port vu depuis Windows change) — `dev/.env` a été mis à jour en conséquence. Ne pas revenir à 5432 sans lever ce conflit.

## Prérequis

```bash
cd dev
docker compose up -d db
```

Vérifier que le conteneur tourne :
```bash
docker compose ps
# dev-db-1 doit être "Up" / "healthy"
```

## Paramètres de connexion

Ces valeurs viennent de `dev/docker-compose.yml` (service `db`) et de `dev/.env` (`DATABASE_URL`) — ne pas les modifier, elles doivent rester identiques entre l'API et DBeaver.

| Paramètre | Valeur |
|---|---|
| **Type de driver** | PostgreSQL |
| **Host** | `localhost` (ou `127.0.0.1`) |
| **Port** | `5442` (pas 5432 — voir l'encadré ci-dessus) |
| **Database** | `ai_agent_poc` |
| **Username** | `postgres` |
| **Password** | `postgres` |
| **SSL** | désactivé (le conteneur ne sert pas de certificat — laisser le mode par défaut "Prefer" ou le passer explicitement à "Disable" si la connexion échoue sur la négociation SSL) |

## Étapes dans DBeaver

1. **Base de données → Nouvelle connexion** (ou icône prise électrique dans la barre d'outils).
2. Choisir **PostgreSQL** dans la liste, **Suivant**.
3. Onglet **Main** :
   - Host : `localhost`
   - Port : `5442`
   - Database : `ai_agent_poc`
   - Username : `postgres`
   - Password : `postgres` → cocher **Save password**
4. **Test Connection** en bas de la fenêtre. Si DBeaver n'a pas encore le driver PostgreSQL (pgjdbc) téléchargé, il propose de le télécharger automatiquement — accepter.
5. **Terminer**. La connexion apparaît dans l'arborescence à gauche : `ai_agent_poc` → `Databases` → `ai_agent_poc` → `Schemas` → `public` → `Tables`.

Si le test de connexion échoue immédiatement (refusée), le conteneur `db` n'est probablement pas démarré — revoir la section Prérequis. Si une erreur signale que la base `ai_agent_poc` n'existe pas alors que le conteneur tourne bien, la connexion a probablement atterri sur le Postgres natif Windows plutôt que sur Docker (voir l'encadré en tête de document) — vérifier que le port utilisé est bien `5442`, pas `5432`.

## Tables utiles pour le débogage

| Table | Module / Epic | Colonnes clés | À quoi ça sert |
|---|---|---|---|
| `documents` | `rag` (Epic 1) | `id`, `source`, `status` (`complete`/`partial`), `created_at` | Un document ingéré via `POST /rag/ingest`. `source` est unique (upsert). |
| `chunks` | `rag` (Epic 1) | `id`, `document_id`, `text`, `embedding` (vecteur `pgvector`, dim 384) | Les fragments découpés + leur embedding — c'est ce que `GET /rag/search` compare par similarité cosinus. |
| `action_proposals` | `gating` (Epic 4) | `id`, `action_type`, `status` (`pending`/`approved`/`rejected`/`executed`), `parameters` (JSON), `conversation_id`, `tool_call_id`, `result`, `created_at`, `decided_at`, `executed_at` | Chaque action sensible proposée par l'agent (ex. `send_email`), de sa création à son issue. |

**Ce qui n'est pas en base** : l'historique de conversation LangGraph (checkpointer) vit en mémoire du processus `api` (`MemorySaver`, voir `app/agent/memory.py`) — il disparaît à chaque redémarrage du conteneur et n'apparaîtra jamais dans DBeaver. Seules les `ActionProposal` (qui, elles, sont persistées explicitement) sont visibles ici.

## Requêtes de débogage prêtes à l'emploi

Ouvrir un éditeur SQL sur la connexion (clic droit sur `ai_agent_poc` → **SQL Editor** → **New SQL script**).

**Voir toutes les propositions d'action, les plus récentes en premier** :
```sql
SELECT id, action_type, status, conversation_id, tool_call_id,
       parameters, result, created_at, decided_at, executed_at
FROM action_proposals
ORDER BY id DESC
LIMIT 20;
```

**Repérer une proposition restée bloquée en `pending`** (typiquement un test manuel jamais décidé — pollue `GET /gating/pending` et les tests qui comptent les lignes `pending`) :
```sql
SELECT id, action_type, conversation_id, created_at
FROM action_proposals
WHERE status = 'pending'
ORDER BY created_at;
```

**Nettoyer une proposition de test oubliée** (comme celle rencontrée pendant nos tests, `id 47` sur `diag-1`) :
```sql
UPDATE action_proposals SET status = 'rejected', decided_at = now() WHERE id = 47;
-- ou, si c'est vraiment une ligne de test jetable, la supprimer :
-- DELETE FROM action_proposals WHERE id = 47;
```

**Documents ingérés et nombre de fragments par document** :
```sql
SELECT d.id, d.source, d.status, count(c.id) AS nb_chunks
FROM documents d
LEFT JOIN chunks c ON c.document_id = d.id
GROUP BY d.id, d.source, d.status
ORDER BY d.id DESC;
```

**Voir le texte brut des fragments d'un document précis** (remplacer `'incident-paiement-2026-08-28'`) :
```sql
SELECT c.id, c.text
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.source = 'incident-paiement-2026-08-28'
ORDER BY c.id;
```

**Reproduire manuellement une recherche par similarité** (pgvector, opérateur `<=>` = distance cosinus, exactement ce qu'utilise `app/rag/vector_store.py` via `.cosine_distance()` ; nécessite de coller un vecteur d'embedding déjà en base, par exemple pour comparer deux fragments proches — peu pratique à la main pour une vraie requête texte libre, qui doit être vectorisée côté Python via `EmbeddingProvider`) :
```sql
SELECT id, text, 1 - (embedding <=> (SELECT embedding FROM chunks WHERE id = 1)) AS similarity
FROM chunks
ORDER BY similarity DESC
LIMIT 5;
```
`similarity` (et non la distance brute) est ce que compare `RAG_SIMILARITY_THRESHOLD` dans `.env` (`app/rag/retriever.py`) pour filtrer les résultats de `GET /rag/search`.

## Dépannage

| Symptôme | Cause | Action |
|---|---|---|
| `Connection refused` immédiat | `dev-db-1` n'est pas démarré | `docker compose up -d db`, attendre `healthy` |
| `FATAL: la base de données « ai_agent_poc » n'existe pas` alors que le conteneur tourne | La connexion a atteint le Postgres natif Windows sur le port 5432, pas le conteneur Docker (conflit de port, voir l'encadré en tête de document) | Utiliser le port `5442`, pas `5432` |
| `password authentication failed` | Mêmes causes que ci-dessus (mauvais serveur atteint), ou mauvais identifiants | Vérifier le port (`5442`) avant de suspecter les identifiants |
| Erreur liée à SSL/certificat | Le conteneur ne sert pas de certificat SSL | Mettre le mode SSL de la connexion DBeaver sur `Disable` (onglet **SSL** de la connexion) |
| Connexion établie puis coupée juste après un `docker compose up`/`restart` | Le port-forward Docker Desktop met parfois quelques secondes à se stabiliser après un (re)démarrage | Réessayer après 3-5 secondes |
| Les tables `gating`/`rag` n'apparaissent pas dans l'arborescence | Migrations non appliquées | Depuis `dev/` : `docker compose run --rm api uv run alembic upgrade head` |
| Pour vérifier quel processus tient réellement le port 5432 sur la machine | — | PowerShell : `Get-NetTCPConnection -LocalPort 5432 -State Listen \| ForEach-Object { Get-Process -Id $_.OwningProcess }` — si `postgres.exe` apparaît en plus de `com.docker.backend`, le conflit est confirmé |
