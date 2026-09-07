# Proposition — Epic 10 : Connecteur Jira (tickets + commentaires + pièces jointes)

**Statut** : validé — développement livré (phases 10.1 à 10.5).

## Résumé exécutif

Aujourd'hui, la base de connaissances RAG s'alimente via `document` (dépôt manuel), `github` (issues) et `sharepoint` (fichiers d'un dossier, Epic 8-3bis). Ce document propose un **connecteur Jira** : récupération de tous les tickets d'un ou plusieurs projets, avec leur description, leurs commentaires, et le texte extrait de leurs pièces jointes PDF — le tout de façon **incrémentale** (ne re-télécharge que ce qui a changé) et **réutilisable** (le mécanisme de sync incrémentale généralisé profite aussi aux connecteurs existants).

Décisions actées suite à vos réponses :
1. **Les deux déploiements Jira sont supportés** : Jira Cloud (`*.atlassian.net`, API v3, auth email + API token) et Jira Server/Data Center interne (API v2, auth Personal Access Token) — un seul connecteur, un champ `deployment_type` choisit le bon comportement.
2. **Texte + PDF au MVP, OCR des images en V2** — livre vite une base solide, l'OCR (dépendance Tesseract plus lourde) vient ensuite si le besoin se confirme.
3. **Synchronisation incrémentale** (`updated >= dernière sync`) — rapide à l'usage répété, et le mécanisme est conçu pour être générique (pas Jira-only).

Ce n'est pas une réécriture : le pipeline RAG, l'interface `Connector` (Epic 2/8) et le Studio (Epic 8) sont réutilisés tels quels — Jira devient un quatrième type de nœud dans la palette, sans rien changer côté canvas.

---

## 1. Constat — état actuel

| Aujourd'hui | Limite |
|---|---|
| Aucun connecteur Jira | Les tickets (bugs, incidents, décisions documentées en commentaires) ne sont pas exploitables par l'agent |
| Tous les connecteurs existants font une synchronisation **complète** à chaque fois (`fetch_items()` sans notion de "depuis quand") | Pour un projet Jira volumineux (des milliers de tickets), une resynchronisation périodique complète est lente et coûteuse (téléchargement, embeddings) |
| `Connector.fetch_items(**instance.config)` ne reçoit que la config utilisateur, jamais `last_synced_at` | Même en ajoutant du code de filtrage côté connecteur, rien ne le lui transmet aujourd'hui |
| `document/extraction.py` sait extraire du texte de PDF/DOCX, mais rien ne télécharge de pièces jointes authentifiées depuis une source externe | Le connecteur SharePoint (8-3bis) le fait pour des fichiers ; Jira a le même besoin pour les pièces jointes d'un ticket |

## 2. Architecture technique

### 2.1 Authentification — les deux déploiements

| | Jira Cloud | Jira Server / Data Center |
|---|---|---|
| API | REST v3 (`/rest/api/3/...`) | REST v2 (`/rest/api/2/...`) |
| Auth | Basic Auth : `email:api_token` (généré sur `id.atlassian.com/manage-profile/security/api-tokens`) | `Authorization: Bearer {personal_access_token}` (généré sur `{base_url}/secure/ViewProfile.jspa` → *Personal Access Tokens*) |
| Format de `description` | **ADF** (Atlassian Document Format — arbre JSON structuré, pas du texte brut) | Texte brut ou wiki markup selon configuration du renderer, jamais ADF |
| Pagination recherche | `nextPageToken` (nouvelle API de recherche, `/rest/api/3/search/jql`) | `startAt` / `maxResults` / `total` (classique) |

Un champ `deployment_type: "cloud" | "server"` dans la config choisit explicitement le comportement — pas de détection automatique (fragile, et une mauvaise détection casserait silencieusement l'auth). Comme pour SharePoint, **aucun secret ne transite par le navigateur** : `credential_alias` pointe vers des identifiants pré-configurés côté serveur.

```bash
# .env
JIRA_CLOUD_EMAIL=vous@entreprise.com
JIRA_CLOUD_API_TOKEN=...
JIRA_SERVER_TOKEN=...
```

### 2.2 Format ADF (Jira Cloud) → texte brut

La description et les commentaires Jira Cloud sont un arbre JSON (paragraphes, listes, blocs de code, mentions, liens...), pas une chaîne. Nouveau module `app/connectors/jira/adf.py` : parcours récursif simple qui concatène le texte des nœuds `text`, insère des sauts de ligne aux frontières de paragraphe/liste/titre, et rend `code`/`codeBlock` lisiblement (utile : messages d'erreur collés dans un ticket). Pas de dépendance externe — l'ADF est un JSON standard, un parcours maison de ~40 lignes suffit (mêmes proportions que `document/extraction.py`).

Jira Server ne produit pas d'ADF : sa description est déjà une chaîne, utilisée telle quelle.

### 2.3 Récupération des tickets, commentaires, pièces jointes

```python
class JiraConnector(Connector):
    name = "jira"
    supports_incremental_sync = True  # voir 2.5

    async def fetch_items(
        self, *, base_url, deployment_type, project_key, credential_alias="default",
        since: datetime | None = None,  # injecté par instance_service, jamais dans le formulaire
    ) -> list[JiraIssueItem]: ...
```

Pour chaque projet (`project_key`), construit une JQL : `project = {project_key}` ou, si `since` est fourni, `project = {project_key} AND updated >= "{since:%Y-%m-%d %H:%M}"`, triée `ORDER BY updated ASC` (garantit qu'une sync interrompue en cours de route reprendra sans trou au prochain `since`).

Pour chaque ticket trouvé :
1. **Champs** : clé, résumé, description (convertie via `adf.py` si Cloud), statut, type, labels, assigné — pour un contexte riche dans le document final.
2. **Commentaires** : `GET /issue/{key}/comment`, paginé, chaque corps converti comme la description.
3. **Pièces jointes** : `issue.fields.attachment[]` — chaque fichier `.pdf`/`.docx`/texte est téléchargé (`GET` authentifié sur son `content` URL) et passé à `app/connectors/document/extraction.py` (**déjà écrit**, réutilisé tel quel, comme pour SharePoint). Un fichier image ou d'un format non supporté est listé par son nom dans le document (traçabilité : "pièce jointe non traitée : capture.png") mais son contenu n'est pas extrait — c'est exactement la portée V1/V2 actée pour les images.

Un ticket = **un document RAG** (`source = "jira:{deployment_type}:{base_url}/{key}"`), contenu = résumé + description + commentaires + texte des pièces jointes concaténés. Choix cohérent avec SharePoint (un fichier = un document) et GitHub (une issue = un document) : le ticket est l'unité de sens, pas chacun de ses commentaires isolément.

### 2.4 Pagination et rate limiting

- Recherche : boucle sur `nextPageToken` (Cloud) / `startAt` (Server) jusqu'à épuisement, taille de page 100 (max autorisé par Jira).
- Commentaires/pièces jointes : peu nombreux par ticket en pratique, pas de pagination supplémentaire nécessaire au-delà de celle native de l'API commentaires.
- Rate limit (Cloud renvoie `429` + `Retry-After`) : un retry unique après le délai indiqué, sinon l'erreur remonte dans `last_result.errors` de l'instance (même politique que GitHub aujourd'hui — pas de retry silencieux à l'infini).

### 2.5 Synchronisation incrémentale — mécanisme généralisé

Nouveau sur `Connector` (`app/connectors/base.py`) :

```python
class Connector(ABC):
    ...
    supports_incremental_sync: ClassVar[bool] = False  # défaut : inchangé pour github/sharepoint/document
```

Dans `instance_service.run_sync()` :

```python
kwargs = dict(instance.config)
if connector.supports_incremental_sync and instance.last_synced_at is not None:
    kwargs["since"] = instance.last_synced_at
items = await connector.fetch_items(**kwargs)
```

`since` n'est **jamais** un champ du `config_schema` (donc jamais dans le formulaire du Studio) — c'est une valeur que seul `instance_service` connaît (`ConnectorInstance.last_synced_at`, déjà stocké aujourd'hui) et injecte automatiquement. Un connecteur qui ne déclare pas `supports_incremental_sync = True` continue de fonctionner exactement comme avant (GitHub, SharePoint, Document ne changent pas de comportement). Le jour où GitHub voudra la même optimisation (`GET /issues?since=...` existe déjà côté API GitHub), il suffira d'ajouter le flag + le paramètre `since` à sa méthode — zéro changement dans `instance_service` ou le Studio.

**Un ticket resynchronisé après modification** est simplement ré-ingéré : `ingest_document()` fait déjà un upsert par `source` (comportement existant, voir `rag.ingestion`), donc son contenu RAG se met à jour sans doublon.

### 2.6 Config exposée dans le formulaire du Studio

```python
class JiraConnectorConfig(BaseModel):
    base_url: str = Field(examples=["https://monentreprise.atlassian.net"])
    deployment_type: Literal["cloud", "server"] = Field(default="cloud")
    project_key: str = Field(examples=["SUPPORT"])
    credential_alias: str = Field(default="default")
```

Génère automatiquement le formulaire (comme tous les connecteurs Epic 8) — aucun code frontend spécifique à écrire.

## 3. Sécurité des secrets

Identique à GitHub/SharePoint : `credential_alias` résolu côté serveur uniquement, jamais de token dans le navigateur ni en base non chiffrée. Les 3 variables (`JIRA_CLOUD_EMAIL`, `JIRA_CLOUD_API_TOKEN`, `JIRA_SERVER_TOKEN`) rejoignent `SHAREPOINT_*`/`GITHUB_TOKEN` dans `.env`.

## 4. Nouvelles dépendances

Aucune. `httpx` (requêtes), `pypdf`/`python-docx` (extraction, déjà présents pour SharePoint/Document) suffisent. Le parseur ADF est un module maison sans dépendance. L'OCR (V2, hors scope validé) nécessiterait `pytesseract` + le binaire `tesseract-ocr` dans le `Dockerfile` — évalué séparément si le besoin se confirme après le MVP.

## 5. Découpage en phases

| Phase | Contenu | Effort | Statut |
|---|---|---|---|
| **10.1** | `Connector.supports_incremental_sync` + câblage `instance_service` (générique, zéro régression sur les connecteurs existants) | S | ✅ Fait |
| **10.2** | `app/connectors/jira/adf.py` — conversion ADF → texte, testé isolément avec des arbres JSON représentatifs | S | ✅ Fait |
| **10.3** | `app/connectors/jira/client.py` — client HTTP (auth Cloud/Server, recherche paginée JQL, commentaires, téléchargement pièces jointes), erreurs mappées vers `ConnectorError`/`ConnectorConfigError` | M | ✅ Fait |
| **10.4** | `app/connectors/jira/connector.py` + `schemas.py` — assemble un `JiraIssueItem` par ticket, réutilise `document/extraction.py` pour les PDF/DOCX joints | M | ✅ Fait |
| **10.5** | Tests (client mocké `httpx.MockTransport`, ADF, incrémental) + `.env.example` + doc | S | ✅ Fait (23 tests) |
| **10.6** (V2, hors scope MVP) | OCR des images jointes (`pytesseract`) | M | ⏳ À faire si besoin confirmé |

**10.1 → 10.5 dans l'ordre** : chaque phase testable indépendamment, comme SharePoint/Epic 8.

## 6. Ce qui ne change pas

Chat, gating, audit, RAG, Studio (canvas/formulaire dynamique) restent identiques — Jira devient un type de connecteur de plus dans `registry.py`, exactement comme GitHub et SharePoint aujourd'hui.

---

**Prochaine étape** : votre feu vert sur cette proposition (notamment la portée 2.3 « un ticket = un document » et le mécanisme incrémental généralisé en 2.5), puis développement phase par phase.
