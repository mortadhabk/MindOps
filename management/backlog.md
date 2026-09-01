# Backlog — Agent IA modulaire (POC réutilisable)

## Vision du projet

Construire un socle agentique unique et réutilisable — RAG + connecteur + orchestration + politique de confiance configurable — plutôt que 4 architectures séparées. Le niveau d'autonomie (suggestion seule → validation humaine → exécution automatique) devient un paramètre de configuration, pas une réécriture. Le premier connecteur branché est GitHub Issues (API publique, gratuite, bien documentée) pour prouver le pattern sans dépendre d'un accès entreprise ; n'importe quel autre outil (ticketing, incidents) se branche ensuite en n'écrivant qu'un nouveau connecteur, sans toucher au reste.

## Architecture retenue

Monolithe modulaire en architecture hexagonale (ports & adapters). Chaque module métier est un dossier isolé avec ses propres modèles, schémas et router ; les dépendances entre modules ne vont que dans un sens, jamais en retour, ce qui garantit qu'on peut remplacer ou tester un module sans toucher aux autres.

Règle de dépendance (à respecter strictement) :

```
connectors  →  (indépendant, ne dépend de rien d'autre)
rag         →  (indépendant, ne dépend de rien d'autre)
gating      →  audit
agent       →  rag, gating, audit
api         →  agrège tous les routers, ne contient aucune logique métier
core        →  transverse, aucun module métier n'y touche mais tous peuvent l'utiliser
```

`agent` orchestre les autres modules (il appelle `rag` pour chercher du contexte, passe par `gating` avant d'exécuter une action) mais aucun module ne dépend de `agent` en retour — c'est ce qui permet de tester `rag` ou `gating` isolément, sans jamais démarrer l'orchestrateur.

## Structure du projet

```
ai-agent-poc/
├── app/
│   ├── main.py                        # point d'entrée, montage des routers
│   ├── config.py                      # Settings centralisées (pydantic-settings)
│   │
│   ├── core/                          # transverse, zéro logique métier
│   │   ├── logging.py                 # logging structuré
│   │   ├── exceptions.py              # exceptions custom + handlers FastAPI
│   │   ├── security.py                # auth API key, dépendances de sécurité
│   │   └── database.py                # engine SQLAlchemy, session, get_db()
│   │
│   ├── rag/                           # MODULE — moteur de connaissance
│   │   ├── models.py                  # Document, Chunk (SQLAlchemy)
│   │   ├── schemas.py                 # DocumentIn/Out (Pydantic)
│   │   ├── ingestion.py               # chunking + génération d'embeddings
│   │   ├── retriever.py               # recherche sémantique top-k
│   │   ├── vector_store.py            # abstraction pgvector, remplaçable
│   │   └── router.py                  # /rag/ingest, /rag/search
│   │
│   ├── connectors/                    # MODULE — intégrations externes
│   │   ├── base.py                    # interface abstraite Connector (port)
│   │   ├── registry.py                # registre des connecteurs disponibles
│   │   ├── github/
│   │   │   ├── connector.py           # implémentation GitHub Issues (adapter)
│   │   │   └── schemas.py
│   │   ├── mock/
│   │   │   └── connector.py           # connecteur factice pour les tests
│   │   └── router.py                  # /connectors/{name}/sync
│   │
│   ├── agent/                         # MODULE — orchestration agentique
│   │   ├── orchestrator.py            # boucle agentique (function calling)
│   │   ├── llm_client.py              # wrapper autour de l'API LLM
│   │   ├── memory.py                  # historique de conversation
│   │   ├── tools/
│   │   │   ├── base.py                # interface Tool (nom, schema, execute)
│   │   │   ├── search_knowledge.py    # tool → appelle rag.retriever
│   │   │   └── send_email.py          # tool → passe par gating avant d'agir
│   │   ├── schemas.py                 # ChatRequest/ChatResponse
│   │   └── router.py                  # /agent/chat (streaming SSE)
│   │
│   ├── gating/                        # MODULE — politique de confiance
│   │   ├── models.py                  # ActionProposal (SQLAlchemy)
│   │   ├── schemas.py
│   │   ├── policy.py                  # règles suggest_only/require_validation/auto
│   │   ├── queue_service.py           # gestion de la file de validation
│   │   └── router.py                  # /gating/pending, /gating/{id}/decide
│   │
│   ├── audit/                         # MODULE — traçabilité
│   │   ├── models.py                  # AuditLog (SQLAlchemy)
│   │   ├── service.py                 # write_log(), utilisé par tous les modules
│   │   └── router.py                  # /audit/logs
│   │
│   └── api/
│       └── router.py                  # agrège tous les routers de module
│
├── alembic/                           # migrations de base de données
├── tests/
│   ├── conftest.py                    # fixtures partagées (DB de test, mocks)
│   ├── rag/
│   ├── connectors/
│   ├── agent/
│   └── gating/
│
├── docker-compose.yml                 # postgres+pgvector, api
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

## Stack technique

FastAPI (async) + Pydantic v2 pour les schémas et la validation. SQLAlchemy (mode async) + Alembic pour la persistance et les migrations. PostgreSQL avec l'extension pgvector pour la base vectorielle — un seul service à faire tourner en local, pas de dépendance à un fournisseur externe pour le POC. Le SDK Claude Agent (ou LangGraph si tu veux rester agnostique du LLM) pour l'orchestration. Resend ou SendGrid pour l'action d'envoi d'email. pytest + httpx pour les tests. Docker Compose pour lancer l'environnement complet en une commande.

## Légende des priorités

**P0** — indispensable : sans ça, le POC ne démontre rien de bout en bout.
**P1** — important : c'est ce qui démontre les bonnes pratiques (gating, audit, isolation des modules) plutôt qu'un simple script.
**P2** — bonus : industrialisation, à faire seulement si le cœur fonctionne déjà bien.

Effort : **S** (quelques heures), **M** (une demi-journée à une journée), **L** (plusieurs jours).

## Ordre d'exécution suggéré

Sprint 1 — Socle technique (Epic 0) : rien d'autre n'avance sans ça.
Sprint 2 — Moteur RAG isolé (Epic 1) : validable seul, sans agent ni connecteur, via un endpoint de recherche direct.
Sprint 3 — Connecteur GitHub + orchestrateur agentique (Epics 2 et 3) : le chat fonctionne de bout en bout en lecture seule.
Sprint 4 — Gating + audit (Epics 4 et 5) : l'agent peut désormais proposer et exécuter une action, de façon tracée et contrôlée.
Sprint 5 — Démo et polish (Epic 6), puis bonus (Epic 7) si le temps le permet.

---

## Epic 0 — Socle technique et infrastructure

### US-001 — Initialiser la structure du projet FastAPI
**Priorité** : P0 · **Effort** : S

En tant que développeur, je veux une arborescence de projet modulaire déjà en place, afin de pouvoir ajouter chaque module métier sans réorganiser le code plus tard.

Critères d'acceptation :
- L'arborescence décrite dans la section "Structure du projet" existe, avec des dossiers vides (`__init__.py`) pour chaque module.
- `app/main.py` démarre une application FastAPI vide qui répond sur `/health`.
- Le projet se lance avec une seule commande (`uvicorn app.main:app --reload`).
- `pyproject.toml` déclare les dépendances de base (fastapi, uvicorn, pydantic-settings).

### US-002 — Centraliser la configuration
**Priorité** : P0 · **Effort** : S

En tant que développeur, je veux une configuration centralisée via variables d'environnement, afin de ne jamais coder en dur une clé API ou une URL de base de données.

Critères d'acceptation :
- `app/config.py` définit une classe `Settings` (pydantic-settings) chargée depuis `.env`.
- `.env.example` liste toutes les variables nécessaires (URL DB, clé API LLM, clé API GitHub, clé API email) sans valeurs réelles.
- Aucun secret n'est commité dans le dépôt (`.env` dans `.gitignore`).

### US-003 — Mettre en place Docker Compose
**Priorité** : P0 · **Effort** : M

En tant que développeur, je veux lancer toute la stack (API + base de données) en une commande, afin de ne pas avoir à installer Postgres/pgvector manuellement.

Critères d'acceptation :
- `docker-compose.yml` démarre un service Postgres avec l'extension pgvector activée.
- `docker-compose up` rend l'API et la base disponibles et connectées entre elles.
- Un `README.md` explique la commande de démarrage en une ligne.

### US-004 — Mettre en place les migrations de base de données
**Priorité** : P0 · **Effort** : S

En tant que développeur, je veux gérer le schéma de la base de données par migrations versionnées, afin de pouvoir faire évoluer les modèles sans casser les données existantes.

Critères d'acceptation :
- Alembic est configuré et connecté aux modèles SQLAlchemy de chaque module.
- Une migration initiale crée les tables de base (vide au départ, complétée au fur et à mesure des epics suivants).
- `alembic upgrade head` fonctionne sans erreur après `docker-compose up`.

### US-005 — Mettre en place le logging structuré
**Priorité** : P0 · **Effort** : S

En tant que développeur, je veux des logs structurés (format JSON, niveau configurable), afin de pouvoir déboguer le comportement de l'agent sans ajouter des `print()` partout.

Critères d'acceptation :
- `app/core/logging.py` configure un logger structuré, utilisé de façon identique dans tous les modules.
- Chaque requête HTTP est loguée avec un identifiant de corrélation (request ID).
- Le niveau de log est configurable via `.env`.

### US-006 — Centraliser la gestion des erreurs
**Priorité** : P0 · **Effort** : S

En tant qu'utilisateur de l'API, je veux recevoir des erreurs claires et cohérentes, afin de comprendre ce qui a échoué sans lire les logs serveur.

Critères d'acceptation :
- `app/core/exceptions.py` définit des exceptions métier custom (ex : `DocumentNotFoundError`, `ConnectorError`).
- Un exception handler FastAPI global traduit chaque exception métier en réponse HTTP cohérente (code + message structuré).
- Aucune stack trace brute n'est renvoyée au client en dehors du mode debug.

### US-007 — Mettre en place la structure de tests
**Priorité** : P0 · **Effort** : S

En tant que développeur, je veux une structure de tests prête à l'emploi avec une base de données de test isolée, afin de pouvoir tester chaque module indépendamment dès qu'il est écrit.

Critères d'acceptation :
- `tests/conftest.py` fournit une fixture de base de données de test (transaction annulée après chaque test) et un client HTTP async.
- Un test trivial sur `/health` passe.
- La commande `pytest` fonctionne depuis la racine du projet.

### US-008 — Mettre en place un pipeline de vérification basique
**Priorité** : P1 · **Effort** : S

En tant que développeur, je veux que le linting et les tests tournent automatiquement, afin d'éviter de casser un module en modifiant un autre.

Critères d'acceptation :
- Un outil de lint/format (ruff) est configuré avec une règle de style unique pour tout le projet.
- Un script ou une CI basique (GitHub Actions) lance lint + tests à chaque push.

---

## Epic 1 — Moteur RAG (moteur de connaissance)

### US-101 — Modéliser les documents et leurs fragments
**Priorité** : P0 · **Effort** : S

En tant que développeur, je veux un modèle de données pour les documents ingérés et leurs fragments (chunks), afin de stocker le contenu source et ses embeddings de façon traçable.

Critères d'acceptation :
- `rag/models.py` définit `Document` (source, métadonnées, date d'ingestion) et `Chunk` (texte, embedding, référence au document parent).
- La table `Chunk` utilise le type `vector` de pgvector pour la colonne embedding.
- Une migration Alembic crée ces tables.

### US-102 — Découper un document en fragments exploitables
**Priorité** : P0 · **Effort** : M

En tant que système, je veux découper un document long en fragments de taille raisonnable, afin que chaque fragment reste pertinent et récupérable individuellement.

Critères d'acceptation :
- `rag/ingestion.py` expose une fonction `chunk_text(text, max_tokens, overlap)` pure (testable sans dépendance externe).
- Le découpage respecte une taille max configurable et un chevauchement entre fragments consécutifs.
- Testé unitairement sur un texte long avec des cas limites (texte plus court que la taille max, texte vide).

### US-103 — Générer et stocker les embeddings
**Priorité** : P0 · **Effort** : M

En tant que système, je veux générer un embedding pour chaque fragment et le stocker en base, afin de pouvoir faire une recherche sémantique dessus.

Critères d'acceptation :
- `rag/ingestion.py` appelle le modèle d'embedding choisi et associe le vecteur résultant à chaque `Chunk`.
- L'appel au modèle d'embedding est isolé dans une fonction facilement remplaçable (changer de fournisseur ne touche qu'un seul point).
- En cas d'échec de l'appel, le document reste marqué comme "ingestion partielle" plutôt que de planter silencieusement.

### US-104 — Rechercher les fragments les plus pertinents
**Priorité** : P0 · **Effort** : M

En tant que système, je veux récupérer les k fragments les plus proches sémantiquement d'une question donnée, afin de fournir du contexte pertinent au LLM.

Critères d'acceptation :
- `rag/retriever.py` expose `search(query: str, top_k: int) -> list[Chunk]`.
- La recherche utilise la similarité cosinus via pgvector.
- Testé avec un jeu de données fictif où la pertinence attendue est connue à l'avance.

### US-105 — Exposer l'ingestion via l'API
**Priorité** : P0 · **Effort** : S

En tant qu'utilisateur, je veux pouvoir ingérer un document manuellement via l'API, afin de peupler la base de connaissances sans passer par un connecteur.

Critères d'acceptation :
- `POST /rag/ingest` accepte un texte ou un fichier et déclenche chunking + embedding + stockage.
- La réponse renvoie l'identifiant du document créé et le nombre de fragments générés.

### US-106 — Exposer la recherche brute via l'API
**Priorité** : P0 · **Effort** : S

En tant que développeur, je veux un endpoint de recherche RAG isolé (sans agent ni LLM de génération), afin de valider le moteur de récupération indépendamment du reste.

Critères d'acceptation :
- `GET /rag/search?q=...` renvoie les fragments les plus pertinents avec leur score de similarité.
- Fonctionne sans que les modules `agent` ou `connectors` soient développés.

### US-107 — Tester le moteur RAG de bout en bout
**Priorité** : P1 · **Effort** : S

En tant que développeur, je veux une suite de tests d'intégration sur le module RAG, afin de détecter une régression avant qu'elle n'atteigne l'agent.

Critères d'acceptation :
- Un test ingère un document fictif puis vérifie qu'une recherche pertinente le retrouve.
- Un test vérifie qu'une recherche non pertinente ne retourne rien au-delà d'un seuil de similarité configurable.

---

## Epic 2 — Couche connecteur

### US-201 — Définir l'interface abstraite des connecteurs
**Priorité** : P0 · **Effort** : S

En tant que développeur, je veux une interface commune que tout connecteur doit implémenter, afin de pouvoir brancher un nouvel outil externe sans modifier le reste du système.

Critères d'acceptation :
- `connectors/base.py` définit une classe abstraite `Connector` avec au minimum `fetch_items()` et `to_document(item) -> DocumentIn`.
- Aucun autre module n'importe directement une implémentation concrète (`github/`, `mock/`) — seulement `connectors/base.py` et `connectors/registry.py`.

### US-202 — Implémenter le connecteur GitHub Issues
**Priorité** : P0 · **Effort** : M

En tant qu'utilisateur, je veux synchroniser les issues d'un dépôt GitHub comme base de connaissances, afin d'avoir une source de données réelle et gratuite pour démontrer le pattern.

Critères d'acceptation :
- `connectors/github/connector.py` implémente `Connector` en appelant l'API GitHub Issues (lecture seule).
- Chaque issue (titre + corps + commentaires résolus) est transformée en `DocumentIn` prêt à être ingéré par le module `rag`.
- Gère la pagination et les limites de taux de l'API GitHub sans planter.

### US-203 — Synchroniser un connecteur vers la base de connaissances
**Priorité** : P0 · **Effort** : S

En tant qu'utilisateur, je veux déclencher la synchronisation d'un connecteur vers le moteur RAG via un seul appel, afin de peupler ma base de connaissances sans étape manuelle.

Critères d'acceptation :
- `POST /connectors/{name}/sync` récupère les items via le connecteur nommé, les convertit et les envoie au pipeline d'ingestion RAG (réutilise US-102/US-103, ne les réimplémente pas).
- La réponse indique le nombre de documents synchronisés et les éventuelles erreurs partielles.

### US-204 — Implémenter un connecteur factice pour les tests
**Priorité** : P1 · **Effort** : S

En tant que développeur, je veux un connecteur "mock" qui ne dépend d'aucun service externe, afin de tester le pipeline connecteur → RAG sans appel réseau réel.

Critères d'acceptation :
- `connectors/mock/connector.py` retourne des données fictives fixes.
- Utilisé dans les tests d'intégration de US-203 à la place du connecteur GitHub.

### US-205 — Documenter l'ajout d'un nouveau connecteur
**Priorité** : P1 · **Effort** : S

En tant que futur développeur (ou moi-même dans 3 mois), je veux un guide clair pour ajouter un connecteur, afin de ne pas devoir relire tout le code existant pour brancher un nouvel outil.

Critères d'acceptation :
- Une section du `README.md` explique, avec le connecteur GitHub comme exemple, les 3 étapes pour ajouter un connecteur (implémenter l'interface, l'enregistrer dans `registry.py`, tester avec le mock en modèle).

---

## Epic 3 — Orchestrateur agentique

### US-301 — Définir les outils exposés au LLM
**Priorité** : P0 · **Effort** : M

En tant que développeur, je veux que chaque outil disponible pour l'agent soit défini par un schéma Pydantic unique, afin que ce même schéma serve à la fois de validation et de définition d'outil pour le function calling.

Critères d'acceptation :
- `agent/tools/base.py` définit une interface `Tool` avec un nom, un schéma Pydantic de paramètres, et une méthode `execute()`.
- Chaque tool concret (`search_knowledge.py`, `send_email.py`) hérite de cette interface.

### US-302 — Implémenter la boucle agentique
**Priorité** : P0 · **Effort** : L

En tant qu'utilisateur, je veux que l'agent puisse décider d'appeler un outil ou de répondre directement, afin d'obtenir une réponse qui s'appuie sur mes données quand c'est pertinent.

Critères d'acceptation :
- `agent/orchestrator.py` implémente la boucle : envoi au LLM → si appel d'outil demandé, exécution puis renvoi du résultat au LLM → jusqu'à réponse finale.
- Le nombre d'itérations est plafonné (pas de boucle infinie possible).
- Chaque appel d'outil passe par le module `gating` avant exécution si l'outil est marqué comme "sensible" (voir Epic 4) — les tools en lecture seule comme `search_knowledge` s'exécutent directement.

### US-303 — Brancher la recherche de connaissances comme premier outil
**Priorité** : P0 · **Effort** : S

En tant qu'utilisateur, je veux que l'agent puisse chercher dans la base de connaissances avant de répondre, afin que ses réponses soient sourcées plutôt qu'inventées.

Critères d'acceptation :
- `agent/tools/search_knowledge.py` appelle `rag.retriever.search()` (réutilise Epic 1, ne le réimplémente pas).
- La réponse finale de l'agent cite les fragments utilisés.

### US-304 — Exposer le chat avec streaming
**Priorité** : P0 · **Effort** : M

En tant qu'utilisateur, je veux voir la réponse de l'agent s'afficher progressivement, afin de ne pas attendre en silence pendant plusieurs secondes.

Critères d'acceptation :
- `POST /agent/chat` renvoie la réponse en streaming (Server-Sent Events).
- Testable simplement via `curl` ou un client HTTP qui supporte le streaming.

### US-305 — Gérer l'historique de conversation
**Priorité** : P1 · **Effort** : S

En tant qu'utilisateur, je veux que l'agent se souvienne des échanges précédents dans une même conversation, afin de ne pas devoir répéter le contexte à chaque message.

Critères d'acceptation :
- `agent/memory.py` stocke l'historique par identifiant de conversation (en mémoire pour le POC, remplaçable par une table plus tard).
- L'historique est injecté dans le prompt envoyé au LLM à chaque tour.

### US-306 — Tester l'orchestrateur avec un LLM simulé
**Priorité** : P1 · **Effort** : M

En tant que développeur, je veux tester la boucle agentique sans appeler le vrai LLM à chaque test, afin de garder une suite de tests rapide et gratuite.

Critères d'acceptation :
- `agent/llm_client.py` est une interface remplaçable par un mock dans les tests.
- Un test vérifie que l'agent appelle bien `search_knowledge` quand le LLM simulé le demande, et renvoie la réponse simulée finale.

---

## Epic 4 — Module de gating (politique de confiance)

### US-401 — Modéliser une action proposée
**Priorité** : P1 · **Effort** : S

En tant que développeur, je veux un modèle de données représentant une action que l'agent souhaite exécuter, avec son statut, afin de pouvoir la tracer de la proposition jusqu'à l'exécution ou le rejet.

Critères d'acceptation :
- `gating/models.py` définit `ActionProposal` (type d'action, paramètres, statut : `pending`/`approved`/`rejected`/`executed`, timestamps).
- Une migration Alembic crée la table.

### US-402 — Implémenter la politique de confiance configurable
**Priorité** : P1 · **Effort** : M

En tant qu'utilisateur du système, je veux choisir, par type d'action, si elle nécessite une validation humaine ou peut s'exécuter automatiquement, afin d'ajuster le niveau d'autonomie sans changer le code.

Critères d'acceptation :
- `gating/policy.py` expose une fonction `evaluate(action_type, confidence) -> Decision` où `Decision` est `suggest_only`, `require_validation` ou `auto_execute`.
- La politique par défaut de chaque type d'action est configurable via `.env` ou une table de configuration.
- Testé avec les 3 décisions possibles.

### US-403 — Gérer la file de validation
**Priorité** : P1 · **Effort** : M

En tant qu'utilisateur, je veux consulter les actions en attente de ma validation, afin de garder le contrôle sur ce que l'agent s'apprête à faire.

Critères d'acceptation :
- `GET /gating/pending` liste les `ActionProposal` au statut `pending`.
- `POST /gating/{id}/decide` accepte une décision (`approve`/`reject`) et met à jour le statut.
- Toute décision est immédiatement enregistrée dans le module `audit`.

### US-404 — Implémenter l'action "envoyer un email"
**Priorité** : P1 · **Effort** : M

En tant qu'utilisateur, je veux que l'agent puisse envoyer un email récapitulatif, afin de prouver le pattern complet diagnostic → action gérée par la politique de confiance.

Critères d'acceptation :
- `agent/tools/send_email.py` crée une `ActionProposal` plutôt que d'envoyer l'email directement.
- Selon la décision de `gating.policy`, l'email part immédiatement (`auto_execute`) ou attend une validation (`require_validation`).
- L'envoi réel passe par Resend ou SendGrid, isolé dans une fonction facilement remplaçable.

### US-405 — Exécuter une action validée
**Priorité** : P1 · **Effort** : S

En tant que système, je veux exécuter automatiquement une action dès qu'elle est approuvée, afin que la validation humaine ne soit pas suivie d'une étape manuelle supplémentaire.

Critères d'acceptation :
- Approuver une `ActionProposal` déclenche son exécution effective (appel du tool concerné).
- Le statut passe à `executed` avec le résultat (succès/échec) enregistré.

### US-406 — Basculer le niveau d'autonomie sans changer le code
**Priorité** : P1 · **Effort** : S

En tant qu'utilisateur du système, je veux pouvoir passer une action de "toujours en validation" à "automatique" en changeant une configuration, afin de démontrer que le curseur de confiance ne nécessite aucune réécriture.

Critères d'acceptation :
- Changer la politique d'un type d'action dans la configuration change son comportement observable au prochain appel, sans redéploiement de code.
- Documenté dans le `README.md` comme démonstration clé du projet.

---

## Epic 5 — Audit et journalisation

### US-501 — Modéliser le journal d'audit
**Priorité** : P1 · **Effort** : S

En tant que développeur, je veux un modèle d'audit générique (qui/quoi/quand/résultat), afin que tous les modules puissent l'utiliser sans dupliquer de logique de journalisation.

Critères d'acceptation :
- `audit/models.py` définit `AuditLog` (type d'événement, source, payload, résultat, timestamp).
- Une migration Alembic crée la table.

### US-502 — Journaliser les événements clés
**Priorité** : P1 · **Effort** : S

En tant qu'utilisateur du système, je veux que chaque appel LLM, proposition d'action et décision de validation soit tracé, afin de pouvoir comprendre a posteriori ce que l'agent a fait et pourquoi.

Critères d'acceptation :
- `audit/service.py` expose `write_log(event_type, payload)`, appelée depuis `agent`, `gating`.
- Aucun module n'écrit directement en base d'audit sans passer par ce service.

### US-503 — Consulter l'historique d'audit
**Priorité** : P2 · **Effort** : S

En tant qu'utilisateur, je veux consulter le journal d'audit via l'API, afin de vérifier le comportement de l'agent sans accéder directement à la base de données.

Critères d'acceptation :
- `GET /audit/logs` liste les événements avec filtres simples (par type, par date).

---

## Epic 6 — Démonstration

### US-601 — Interface de démo minimaliste
**Priorité** : P1 · **Effort** : M

En tant que porteur du projet, je veux une interface simple pour discuter avec l'agent sans passer par `curl`, afin de pouvoir faire une démonstration live.

Critères d'acceptation :
- Une page (Streamlit ou HTML/JS minimal) permet d'envoyer un message et de voir la réponse streamer.
- Ne nécessite aucune étape d'installation supplémentaire lourde (reste dans le même `docker-compose`).

### US-602 — Tableau de la file de validation
**Priorité** : P2 · **Effort** : S

En tant que porteur du projet, je veux visualiser les actions en attente de validation et pouvoir les approuver en un clic, afin de rendre le module de gating démontrable visuellement plutôt que seulement via l'API.

Critères d'acceptation :
- Une vue simple liste les `ActionProposal` en attente avec un bouton approuver/rejeter.

---

## Epic 7 — Industrialisation (bonus)

### US-701 — Authentification par clé API
**Priorité** : P2 · **Effort** : S

En tant que porteur du projet, je veux protéger l'API par une clé simple, afin de pouvoir la déployer sans qu'elle soit ouverte à tous.

Critères d'acceptation :
- `core/security.py` vérifie une clé API dans l'en-tête des requêtes sur les endpoints sensibles.

### US-702 — Limiter le débit des requêtes
**Priorité** : P2 · **Effort** : S

En tant que porteur du projet, je veux limiter le nombre d'appels par minute, afin d'éviter une facture LLM incontrôlée en cas de démo publique.

Critères d'acceptation :
- Un middleware de rate limiting est actif sur `/agent/chat`.

### US-703 — Préparer le déploiement
**Priorité** : P2 · **Effort** : M

En tant que porteur du projet, je veux un `Dockerfile` de production et une documentation de déploiement, afin de pouvoir héberger le POC en dehors de ma machine.

Critères d'acceptation :
- `Dockerfile` construit une image de production optimisée (pas de reload, dépendances de dev exclues).
- Le `README.md` documente une méthode de déploiement simple (ex : Render, Fly.io).

### US-704 — Ajouter un second connecteur pour prouver la portabilité
**Priorité** : P2 · **Effort** : M

En tant que porteur du projet, je veux brancher un deuxième connecteur (ex : Jira ou Zendesk en mode sandbox), afin de démontrer concrètement que la couche connecteur est réutilisable sans toucher au reste du système.

Critères d'acceptation :
- Le nouveau connecteur implémente `Connector` (US-201) sans modifier `rag`, `agent` ou `gating`.
- Le temps de développement de ce second connecteur est mesuré et documenté — c'est la preuve chiffrée de la réutilisabilité de l'architecture.
