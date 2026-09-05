# Scénario de test réel — Epic 4 (gating) + RAG via Swagger UI

Ce document est un scénario **à exécuter réellement**, pas une checklist abstraite. Chaque étape donne l'endpoint exact, le corps JSON à coller dans Swagger (`http://localhost:8000/docs`), et ce qu'il faut observer pour valider l'étape avant de passer à la suivante. Compter environ 20-30 minutes, la majeure partie étant le temps d'inférence du LLM local (Ollama).

## 0. Prérequis — à vérifier avant de commencer

| Service | Commande de vérification | Résultat attendu |
|---|---|---|
| Docker (db + api) | `docker compose ps` (depuis `dev/`) | `dev-db-1` et `dev-api-1` en `Up`/`healthy` |
| API | `curl http://localhost:8000/health` | `{"status":"ok"}` |
| Ollama | `curl http://localhost:11434/api/tags` | le modèle `llama3.1:8b` apparaît dans la liste |
| Swagger UI | ouvrir `http://localhost:8000/docs` | les tags `rag`, `agent`, `gating` sont visibles |

Si l'API vient d'être (re)démarrée, laisser 5-10 secondes avant le premier appel (le port peut répondre par intermittence juste après un `docker compose up`).

`.env` doit contenir, pour ce scénario :
```
GATING_POLICY={"send_email": "require_validation"}   # ou absent : c'est déjà la valeur par défaut
EMAIL_API_KEY=<ta clé Mailtrap>
MAILTRAP_INBOX_ID=<ton inbox Mailtrap>
```

---

## Phase A — Alimenter la base de connaissances (RAG)

But : injecter un volume de contexte réaliste et **thématiquement varié**, pour que les phases suivantes puissent vérifier que la recherche retrouve le bon fragment et pas n'importe lequel.

Dans Swagger : `POST /rag/ingest` → **Try it out** → coller le corps → **Execute**. Répéter trois fois avec les trois corps ci-dessous (un appel = un document).

### A.1 — Document 1 : incident de paiement

```json
{
  "source": "incident-paiement-2026-08-28",
  "content": "Le 28 aout 2026, le service de paiement a commence a rejeter toutes les transactions dont le montant depassait 10 000 euros, avec le code d'erreur PAY-4032 'Overflow numeric field'. L'incident a ete detecte a 14h32 par l'alerte Datadog sur le taux d'erreur 500 du service payment-api, qui est passe de 0,1% a 38% en quinze minutes. L'analyse des logs a montre que la colonne amount_cents de la table transactions est definie comme DECIMAL(9,2). L'investigation a revele que le vrai probleme venait du service de conversion de devises amont, qui multipliait le montant par 100 deux fois de suite pour les transactions declarees en euros et converties depuis une devise etrangere. Le correctif deploye a 16h10 a consiste a corriger la double conversion dans currency-service version 2.4.7. Le service a ete restaure a 16h15. Nombre total de transactions impactees : 214, pour un montant cumule de 1,8 million d'euros bloques, sans aucune perte financiere. Proprietaire de l'incident : equipe Paiements, astreinte tenue par Amelie Dubois. Un post-mortem est prevu le 3 septembre 2026."
}
```

**Vérifier** : réponse `200`, `status: "complete"`, `chunks_created: 1`.

> **Correction par rapport à une version précédente de ce document** : `chunk_text()` (`app/rag/ingestion.py`) découpe sur `text.split()` — un compte de **mots**, pas de vrais tokens BPE. Ce document fait 173 mots, sous le seuil `RAG_CHUNK_MAX_TOKENS=200` : **1 seul chunk est le résultat correct**, pas un bug. Pour observer un vrai découpage multi-chunks, baisser temporairement `RAG_CHUNK_MAX_TOKENS` (ex. `50`) dans `.env`, redémarrer l'api, ré-ingérer ce même document (`POST /rag/ingest` avec le même `source` fait un upsert) : `chunks_created` doit alors valoir 4 ou 5. Remettre `200` ensuite pour ne pas fausser la suite du scénario.

### A.2 — Document 2 : politique de remboursement

```json
{
  "source": "politique-remboursement",
  "content": "La politique de remboursement du service client autorise un remboursement integral sans justification dans les 14 jours suivant l'achat, conformement au droit de retractation. Entre 15 et 30 jours, un remboursement partiel de 80 pourcent est possible si le produit n'a pas ete utilise, sur validation d'un responsable d'equipe. Au-dela de 30 jours, seul un avoir peut etre propose, et uniquement en cas de defaut avere du produit. Les remboursements superieurs a 500 euros necessitent une double validation : celle de l'agent support et celle d'un manager, avant tout envoi de confirmation au client. Le canal officiel de confirmation d'un remboursement est un email envoye depuis l'adresse remboursements@ai-agent-poc.local. Le delai de traitement bancaire apres validation est de 3 a 5 jours ouvres. Toute demande liee a une fraude suspectee doit etre escaladee immediatement a l'equipe Securite, sans attendre la validation manager standard."
}
```

### A.3 — Document 3 : FAQ support niveau 1

```json
{
  "source": "faq-support-niveau-1",
  "content": "Que faire si un client signale ne pas avoir recu son email de confirmation de commande ? Verifier d'abord dans l'interface d'administration que l'email a bien ete envoye. Si le statut est 'bounced', demander au client de verifier l'orthographe de son adresse email. Si le statut est 'delivered' mais que le client ne le trouve pas, l'inviter a verifier ses courriers indesirables. Le client demande a changer l'adresse email associee a son compte : cette action necessite une verification d'identite avant toute modification, car c'est un vecteur classique de prise de controle de compte. Ne jamais effectuer ce changement sur simple demande par email non verifiee."
}
```

**Vérifier après les 3 appels** : `GET /rag/search?q=paiement&top_k=10` doit renvoyer des résultats provenant des trois `source` différentes si la question est assez générique, ou uniquement du bon document si la question est précise (voir Phase B).

---

## Phase B — Recherche sémantique directe (sans l'agent)

But : vérifier que le retrieval seul retrouve le bon fragment, **avant** d'ajouter la couche agent par-dessus — isole les bugs de RAG de ceux d'orchestration.

`GET /rag/search` dans Swagger, avec ces trois requêtes successives (paramètres `q` et `top_k`) :

| Requête (`q`) | `top_k` | Résultat attendu en 1ère position |
|---|---|---|
| `Pourquoi le paiement a echoue le 28 aout` | 3 | fragment de `incident-paiement-2026-08-28` |
| `Quel est le delai pour un remboursement complet` | 3 | fragment de `politique-remboursement` |
| `Le client n'a pas recu son email de confirmation` | 3 | fragment de `faq-support-niveau-1` |

**Vérifier** : le champ `score` du 1er résultat est nettement plus élevé que celui des autres, et `document_id` correspond bien au bon document (comparer avec l'`id` renvoyé lors de l'ingestion en Phase A).

---

## Phase C — L'agent utilise le RAG (outil en lecture seule, pas de gating)

But : vérifier `search_knowledge` en conditions réelles, sans toucher au gating (contrôle négatif pour la Phase D).

`POST /agent/chat` :
```json
{
  "conversation_id": "test-rag-1",
  "message": "Resume ce qui s'est passe lors de l'incident de paiement du 28 aout, et donne la cause racine exacte."
}
```

Swagger n'affiche pas bien le flux SSE brut — préférer le terminal pour cette étape (garde le corps ci-dessus).

**PowerShell** (ne jamais utiliser `curl.exe -d '{...}'` ici — PowerShell casse les guillemets du JSON avant même que curl les reçoive ; `Invoke-RestMethod` contourne le problème) :
```powershell
$body = @{
    conversation_id = "test-rag-1"
    message = "Resume ce qui sest passe lors de lincident de paiement du 28 aout, et donne la cause racine exacte."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/agent/chat" -Method Post -ContentType "application/json" -Body $body
```

**Git Bash / WSL / macOS / Linux** :
```bash
curl -N -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"test-rag-1","message":"Resume ce qui sest passe lors de lincident de paiement du 28 aout, et donne la cause racine exacte."}'
```

**Vérifier** :
- La réponse (`event: delta`) mentionne la double conversion de devise dans `currency-service` (pas juste "le paiement a échoué") — preuve que le LLM a bien lu le fragment RAG, pas halluciné.
- Le flux se termine par `event: done`, **pas** `event: pending_approval` (`search_knowledge` n'est pas sensible).

---

## Phase D — Action sensible avec validation humaine (chemin `require_validation`, approuvée)

But : le scénario complet du gating — RAG + décision + interruption + validation + reprise + envoi réel.

> **Fiabilité du tool-calling local.** Diagnostiqué en marge de ce scénario : `llama3.1:8b` via Ollama n'invoque pas toujours l'outil de façon structurée — parfois il écrit le JSON de l'appel comme du texte brut dans sa réponse au lieu de déclencher réellement `search_knowledge`/`send_email` (le graphe se termine alors par `event: done`, pas `pending_approval`). **Vérifié : ce n'est pas un bug du gating** — quand le modèle émet correctement l'appel, `interrupt()`, la création de l'`ActionProposal` et la reprise fonctionnent à chaque fois. C'est une limite connue des petits modèles locaux sur des tâches à plusieurs étapes implicites (chercher, *puis* agir). Deux parades : demander la recherche et l'action **en deux messages séparés** (ci-dessous, plus fiable) ; ou simplement **relancer** le même message si le premier essai ne déclenche pas `pending_approval`.

### D.1 — Déclencher la proposition (en deux temps, plus fiable)

**Message 1** (force la recherche RAG explicitement) :
```powershell
$body1 = @{
    conversation_id = "test-gating-approve"
    message = "Cherche dans la base de connaissances ce qui sest passe lors de lincident de paiement du 28 aout 2026, et quelle en est la cause racine."
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/agent/chat" -Method Post -ContentType "application/json" -Body $body1
```
**Vérifier** : la réponse cite la double conversion de devise dans `currency-service` — pas un résumé vague. Si la réponse ne mentionne rien de précis, relancer ce même message avant de continuer (le tour 1 doit être ancré dans le RAG pour que le tour 2 le soit aussi).

**Message 2**, même `conversation_id` (l'historique du tour 1 sert de contexte) :
```powershell
$body2 = @{
    conversation_id = "test-gating-approve"
    message = "Redige maintenant un email a client-test@example.com qui resume cet incident et sa cause racine, puis envoie-le."
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/agent/chat" -Method Post -ContentType "application/json" -Body $body2
```

**Git Bash / WSL / macOS / Linux**, mêmes deux messages :
```bash
curl -N -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"test-gating-approve","message":"Cherche dans la base de connaissances ce qui sest passe lors de lincident de paiement du 28 aout 2026, et quelle en est la cause racine."}'

curl -N -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"test-gating-approve","message":"Redige maintenant un email a client-test@example.com qui resume cet incident et sa cause racine, puis envoie-le."}'
```

**Vérifier** (sur le message 2) : le flux se termine par `event: pending_approval` avec un `proposal_id`. Noter cet id. Si ce n'est pas le cas (l'agent répond directement en prose), relancer le message 2 — voir l'encadré ci-dessus.

*Patience* : le premier appel LLM après un redémarrage peut prendre 30-90 secondes (chargement du modèle en mémoire) — ce n'est pas un bug.

### D.2 — Consulter la file d'attente

`GET /gating/pending` dans Swagger.

**Vérifier** : un objet avec `action_type: "send_email"`, `status: "pending"`, et `parameters.body` qui contient bien un résumé de l'incident (preuve que le RAG a nourri le contenu de l'email, pas juste l'outil).

### D.3 — Approuver

`POST /gating/{proposal_id}/decide` (remplacer `{proposal_id}` par l'id noté en D.1) :
```json
{ "decision": "approve" }
```

**Vérifier** : réponse `200`, `status: "executed"`, `result` contient `"envoyé à client-test@example.com (capturé dans la sandbox Mailtrap, inbox ...)"`.

### D.4 — Confirmer côté Mailtrap

Ouvrir l'inbox Mailtrap (`https://mailtrap.io/inboxes` → ton inbox) : l'email doit y apparaître, avec le sujet et le corps rédigés par le LLM.

### D.5 — Confirmer que la conversation reprend proprement

`GET /gating/pending` à nouveau : la proposition approuvée en D.3 n'y est plus (elle est `executed`, pas `pending`).

---

## Phase E — Action sensible rejetée

But : vérifier que `reject` débloque bien le graphe **sans jamais** appeler Mailtrap — le test le plus important du module gating.

### E.1 — Déclencher une nouvelle proposition

**PowerShell** :
```powershell
$body = @{
    conversation_id = "test-gating-reject"
    message = "Envoie un email a autre-client@example.com pour lui dire que son remboursement de 800 euros est valide."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/agent/chat" -Method Post -ContentType "application/json" -Body $body
```

**Git Bash / WSL / macOS / Linux** :
```bash
curl -N -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"test-gating-reject","message":"Envoie un email a autre-client@example.com pour lui dire que son remboursement de 800 euros est valide."}'
```

**Vérifier** : `event: pending_approval` à nouveau. Noter le nouveau `proposal_id`. Si l'agent répond directement en prose sans interruption, relancer le même message avec un nouveau `conversation_id` (voir l'encadré fiabilité en Phase D) — ce message-ci ne dépend pas du RAG, donc pas besoin de le scinder en deux temps, juste de réessayer.

### E.2 — Rejeter

`POST /gating/{proposal_id}/decide` :
```json
{ "decision": "reject" }
```

**Vérifier** : `status: "rejected"` (jamais `"executed"`), `result: null`.

### E.3 — Confirmer l'absence d'envoi

Vérifier l'inbox Mailtrap : **aucun** nouvel email pour `autre-client@example.com`. C'est la preuve que `SendEmailTool.execute()` n'a jamais été appelé — seule la trace de la proposition existe en base.

---

## Phase F — Basculer la politique sans toucher au code (démonstration US-406)

But : la promesse centrale du projet — changer le niveau d'autonomie par configuration.

1. Dans `dev/.env`, ajouter ou modifier :
   ```
   GATING_POLICY={"send_email": "auto_execute"}
   ```
2. Redémarrer uniquement le conteneur api (aucun rebuild nécessaire, c'est une variable d'environnement) :
   ```bash
   docker compose up -d api
   ```
3. Rejouer exactement la requête de la Phase E.1 (nouveau `conversation_id`, ex. `test-gating-auto`).

**Vérifier** : le flux `POST /agent/chat` se termine directement par `event: done` — **pas** de `event: pending_approval`. `GET /gating/pending` ne montre rien de nouveau, mais l'email arrive bien dans Mailtrap immédiatement. La proposition existe en base avec `status: "executed"` dès sa création (vérifiable en Phase H).

Remettre `GATING_POLICY={"send_email": "require_validation"}` dans `.env` et redémarrer l'api avant de continuer, pour ne pas fausser la suite.

---

## Phase G — `suggest_only` (l'agent propose, n'exécute jamais)

1. `.env` : `GATING_POLICY={"send_email": "suggest_only"}`, puis `docker compose up -d api`.
2. Rejouer la même requête que E.1 avec un nouveau `conversation_id`.

**Vérifier** : la réponse finale de l'agent (`event: delta`) est une suggestion textuelle ("je vous propose d'envoyer un email...") — le flux se termine par `event: done`, sans jamais passer par `pending_approval`. `GET /gating/pending` reste vide : **aucune** `ActionProposal` n'a été créée pour cet appel (c'est le chemin le plus économe, voir module 03 du manuel de gating).

Remettre `GATING_POLICY={"send_email": "require_validation"}` en fin de test.

---

## Phase H — Vérification directe en base (optionnel, pour les curieux)

```bash
docker exec dev-db-1 psql -U postgres -d ai_agent_poc -c \
  "SELECT id, action_type, status, conversation_id, created_at, executed_at FROM action_proposals ORDER BY id DESC LIMIT 10;"
```

**Vérifier** : une ligne par scénario joué (D, E, F, G), avec le `status` cohérent avec ce qui a été observé via l'API (`executed`, `rejected`, `executed` pour l'auto_execute...), et **aucune ligne** pour le scénario `suggest_only` de la Phase G.

---

## Annexe — Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| `curl` ou Swagger renvoie une connexion vide/coupée juste après un `docker compose up` | Le port forwarding Windows↔Docker Desktop met parfois quelques secondes à se stabiliser | Réessayer après 3-5 secondes ; si persistant, `docker compose restart api` |
| `POST /agent/chat` ne répond rien pendant longtemps | Premier appel Ollama après redémarrage = chargement du modèle en mémoire | Attendre jusqu'à 90 secondes ; les appels suivants sont rapides |
| `event: pending_approval` n'arrive jamais, l'agent répond directement | (1) La politique effective n'est pas `require_validation` pour `send_email` — vérifier `.env`. (2) Plus probable : `llama3.1:8b` a écrit l'appel d'outil comme du texte (`{"name": "send_email", ...}` visible dans la réponse) au lieu de l'invoquer réellement — limite connue de fiabilité du tool-calling avec ce modèle local, **pas un bug du gating** (vérifié en isolant `orchestrator.build_graph()` : quand le modèle émet l'appel correctement, `interrupt()` se déclenche à chaque fois) | Pour (1), corriger `.env` et redémarrer l'api. Pour (2), relancer le même message (nouveau `conversation_id`), ou scinder en deux messages "cherche" puis "agis" (voir Phase D) |
| `POST /gating/{id}/decide` renvoie `404` | Le `proposal_id` a déjà été tranché (relire la réponse de l'étape précédente) ou n'existe pas | `GET /gating/pending` pour retrouver un id valide |
| Le mail n'apparaît pas dans Mailtrap malgré `status: executed` | Mauvais `MAILTRAP_INBOX_ID`, ou clé API d'un autre workspace | Vérifier `.env`, comparer l'`inbox` mentionné dans `result` avec l'URL de l'inbox Mailtrap ouverte |
