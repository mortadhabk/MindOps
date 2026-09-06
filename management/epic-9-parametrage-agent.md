# Proposition — Epic 9 : Panneau de paramétrage de l'agent

**Statut** : ✅ livré (phases 9.1 à 9.4, toutes en une passe — voir section 5). Section 7 pour les décisions actées.

> **Addendum (post-livraison) — revirement assumé sur la section Agent/LLM.** Après livraison, l'utilisateur a explicitement demandé une politique **interface-first** pour le choix du modèle LLM : fournisseur, modèle **et clé API** saisis et modifiables directement dans l'onglet Paramètres, plutôt que la clé restant dans `.env` (le principe posé en section 3/7 ci-dessous, valable pour tout le reste — gating, RAG, connecteurs). Concession retenue : la clé est **chiffrée avant stockage** (`cryptography.Fernet`, clé maîtresse `SETTINGS_ENCRYPTION_KEY` dans `.env` — le seul secret qui reste server-side) et **jamais réaffichée en clair** une fois sauvegardée (masquée en `"••••••••"`, formulaire toujours vide au chargement, "vide = ne pas changer"). Voir section 3.2 (mise à jour) et le nouveau module `app/agent/providers/`.

## Résumé exécutif

Aujourd'hui, tout paramètre du système (politique de gating, seuils RAG, modèle LLM, niveau de log, …) vit dans `dev/.env` et n'est appliqué qu'au redémarrage du conteneur `api`. Ce document propose un **troisième onglet dans `/demo`** (« Paramètres », à côté d'Assistant et Studio) permettant de piloter, visualiser et faire évoluer **tous les réglages non-secrets** du système depuis l'interface, avec effet immédiat quand c'est possible, traçabilité de chaque changement (réutilise `audit`, Epic 5), et une distinction stricte entre ce qui est éditable et ce qui reste volontairement hors de portée du navigateur (secrets, paramètres d'infrastructure).

Architecture réutilisée du Studio (Epic 8) : chaque domaine (agent, RAG, gating, logs) déclare un **schéma Pydantic** de ses paramètres éditables, qui génère automatiquement le formulaire — exactement le mécanisme `config_schema` qui a déjà fait ses preuves pour les connecteurs. Ce n'est pas une nouvelle idée à valider, c'est une généralisation d'un pattern déjà en production.

---

## 1. Constat — état actuel

| Aujourd'hui | Limite |
|---|---|
| Tous les réglages sont dans `Settings` (`app/config.py`), chargés une fois depuis `.env`, via `get_settings()` mis en cache (`@lru_cache`) | Un changement dans `.env` n'a aucun effet tant que le conteneur n'est pas redémarré — même chose pour `GATING_POLICY`, pourtant présentée comme LA démonstration clé du projet (US-406) |
| `get_llm_client()` et `get_embedding_provider()` sont eux-mêmes mis en cache (`@lru_cache`) | Même après un rechargement des settings, le client LLM ou le modèle d'embedding déjà construits ne changeraient pas sans un mécanisme d'invalidation dédié |
| Aucune trace de qui a changé quoi, ni quand | Impossible de savoir a posteriori pourquoi le comportement de l'agent a changé un jour donné |
| Aucune UI — seul `.env` + redémarrage | Pas démontrable, pas accessible à un utilisateur non technique, contraire à l'esprit "curseur de confiance" déjà vendu comme argument du projet |

Point positif qui simplifie beaucoup ce chantier : **la plupart des modules relisent déjà `get_settings()` à chaque appel** (`gating.policy.evaluate()`, `rag.ingestion.ingest_document()`, `rag.retriever.search()`, `connectors.github.connector` pour le token, `agent.tools.send_email`) — aucun état de configuration n'est capturé une fois pour toutes dans ces modules. Seuls trois points concentrent tout le problème : `get_settings()` elle-même, `get_llm_client()`, `get_embedding_provider()`.

## 2. Vision produit

Un onglet **« Paramètres »**, organisé en sections par domaine (pas un formulaire géant) :

```
┌─────────────────────────────────────────────────┐
│  Assistant   Studio   Paramètres ●               │
├─────────────────────────────────────────────────┤
│  ┌─ Agent / LLM ──────────────┐  ┌─ Gating ────┐ │
│  │ Modèle : llama3.1:8b       │  │ send_email: │ │
│  │ URL Ollama : http://...    │  │ [require_val│ │
│  │              [Enregistrer] │  │ Confiance min│ │
│  └────────────────────────────┘  │ 0.8          │ │
│  ┌─ RAG ──────────────────────┐  │ [Enregistrer]│ │
│  │ Taille max chunk : 200     │  └──────────────┘ │
│  │ Chevauchement : 20         │  ┌─ Journalisation┐│
│  │ Seuil similarité : 0.2     │  │ Niveau : INFO  ││
│  │ ⚠️ n'affecte que les       │  │  [Enregistrer] ││
│  │   futures ingestions       │  └────────────────┘│
│  │              [Enregistrer] │                    │
│  └────────────────────────────┘                    │
└─────────────────────────────────────────────────┘
```

Chaque section :
- Affiche la **valeur actuellement effective** (override s'il y en a un, sinon la valeur par défaut de `.env`).
- Un bouton **« Réinitialiser à la valeur par défaut »** par section (supprime l'override, revient au `.env`).
- Un badge **« effet immédiat »** ou **« s'applique aux prochaines requêtes/ingestions »** selon le champ — pas de fausse promesse d'instantanéité là où ça ne s'applique pas (ex. RAG chunking).
- Chaque sauvegarde crée une entrée dans le journal d'audit existant (`gating.decision` a son équivalent : `settings.updated`).

## 3. Ce qui est éditable, ce qui ne l'est pas

Décision de sécurité de départ (même principe que Epic 8, section 5) : **aucun secret ne devient éditable depuis le navigateur.** Revue depuis, pour un seul cas — voir l'addendum en tête de document et la ligne « Éditable, secret chiffré » ci-dessous.

| Catégorie | Exemples | Traitement |
|---|---|---|
| **Éditable, effet immédiat** | `gating_policy`, `gating_min_confidence`, `rag_similarity_threshold`, `log_level` | Formulaire complet, sauvegarde applique tout de suite |
| **Éditable, effet différé (documenté dans l'UI)** | `rag_chunk_max_tokens`, `rag_chunk_overlap` (n'affectent que les *futures* ingestions) ; `llm_provider_kind`, `llm_model`, `base_url` (le client LLM en cache est invalidé à la sauvegarde, effet dès le *prochain* message, pas le tour en cours) | Formulaire complet + badge d'avertissement explicite |
| **Éditable, secret chiffré** (addendum) | `api_key` de la section Agent/LLM — seul champ secret exposé par `/settings/*`, décision produit explicite | Champ mot de passe, chiffré (`Fernet`) avant stockage, jamais renvoyé en clair (masqué, vide au chargement, "vide = ne pas changer") |
| **Visible mais non éditable** (redéploiement requis) | `embedding_provider`, `embedding_model` — changer le modèle rendrait les vecteurs déjà stockés incompatibles (dimension différente), nécessite une ré-ingestion complète | Affiché en lecture seule avec l'explication, pas de champ de saisie |
| **Jamais exposé** (reste `.env`-only) | `database_url`, `github_token`, `email_api_key`, `api_key` (auth API), `SETTINGS_ENCRYPTION_KEY` | Absent de l'API `/settings/*` — aucun endpoint ne les renvoie, même en lecture |

> Alias d'identifiants de connecteurs (`credential_alias`, Epic 8) : toujours hors de portée de `/settings/*` pour l'instant — ce panneau ne couvre que gating/RAG/agent/logging, pas les connecteurs.

## 4. Architecture technique

### 4.1 Déclaration des sections (généralisation du pattern `config_schema`)

Chaque module expose son propre schéma de paramètres éditables — pas de fichier central à modifier pour ajouter un nouveau réglage plus tard :

```python
# app/gating/settings.py
class GatingSettingsSchema(BaseModel):
    gating_policy: dict[str, str] = Field(description="Politique par type d'action")
    gating_min_confidence: float = Field(ge=0, le=1)

GATING_SETTINGS_SECTION = SettingsSection(
    key="gating",
    display_name="Gating (politique de confiance)",
    schema=GatingSettingsSchema,
    effect="immediate",
)
```

`app/core/settings_registry.py` (nouveau, même rôle que `connectors/registry.py`) agrège les sections déclarées par chaque module (`agent`, `rag`, `gating`, `core`) — `GET /settings/sections` les expose avec leur JSON Schema, exactement comme `GET /connectors/types`. **Le formulaire dynamique du Studio (`ConnectorConfigModal`) est extrait en composant partagé** (`DynamicSchemaForm`) et réutilisé tel quel ici — pas de nouveau code de rendu de formulaire.

### 4.2 Stockage des overrides

Nouvelle table `app_settings` :

```python
class AppSetting(Base):
    __tablename__ = "app_settings"
    section: Mapped[str] = mapped_column(primary_key=True)  # "gating", "rag", "llm", "logging"
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

Chargée intégralement en mémoire au démarrage (`core.settings_store`), tenue à jour à chaque écriture (write-through). **Pourquoi pas une lecture DB à chaque `get_settings()` ?** — `gating.policy.evaluate()` et consorts sont appelés à chaque tour de l'agent ; une lecture DB systématique ajouterait une latence inutile pour une donnée qui change rarement. Le cache mémoire est tenu cohérent par construction (un seul processus `uvicorn`, pas de replica pour ce POC — limite documentée, pas cachée).

### 4.3 Effets de bord à la sauvegarde

| Section sauvegardée | Effet de bord nécessaire |
|---|---|
| `gating`, `rag` (seuils), `logging` | Aucun — ces modules relisent déjà `get_settings()` à chaque appel (section 1) |
| `agent` (llm_model, ollama_base_url) | `get_llm_client.cache_clear()` — le prochain appel reconstruit le client avec les nouvelles valeurs |
| `logging` (log_level) | Rappeler `configure_logging(new_level)` — trivial, `core/logging.py` le permet déjà |

### 4.4 Nouveaux endpoints

| Endpoint | Rôle |
|---|---|
| `GET /settings/sections` | Liste les sections éditables avec leur schéma JSON et leur valeur *effective* actuelle |
| `PATCH /settings/{section}` | Valide contre le schéma, upsert dans `app_settings`, applique les effets de bord (4.3), journalise dans `audit` |
| `DELETE /settings/{section}` | Retire l'override — revient à la valeur `.env` par défaut |

### 4.5 Traçabilité

Chaque `PATCH`/`DELETE` appelle `audit.service.write_log("settings.updated", {"section": ..., "before": ..., "after": ...}, source="settings")` — visible immédiatement dans le journal d'audit déjà construit (Epic 5), sans nouveau mécanisme.

## 5. Découpage en phases (Epic 9)

| Phase | Contenu | Effort | Statut |
|---|---|---|---|
| **9.1** | Backend : `SettingsSection`/registry, table `app_settings`, endpoints, invalidation de cache, audit | M | ✅ Fait |
| **9.2** | Formulaire dynamique (`DynamicSchemaField`, dont un éditeur clé/valeur pour `gating_policy`) ; nouvel onglet Paramètres (front) | M | ✅ Fait |
| **9.3** | Sections `gating` et `rag` (les plus utiles immédiatement — le "curseur de confiance" enfin pilotable sans redémarrage) | S | ✅ Fait |
| **9.4** | Sections `agent` (LLM) et `logging` | S | ✅ Fait |
| **9.5** (bonus) | Historique des changements par section (au-delà du flux d'audit générique), export/import de configuration | M | À faire |

Livré en une seule passe plutôt que phase par phase : une fois le registre générique (9.1) en place, chaque section supplémentaire (9.3, 9.4) ne coûtait plus que ~30 lignes (schéma + getter fusionnant `.env`/override + enregistrement) — les livrer séparément aurait juste ajouté des allers-retours sans réduire le risque.

Note d'implémentation : plutôt qu'extraire `ConnectorConfigModal` en composant partagé (risque de régression sur le Studio, déjà en production), un nouveau composant `DynamicSchemaField` dédié au panneau Paramètres a été écrit — même *pattern* (JSON Schema → formulaire fait main), fichier séparé. Une factorisation ultérieure reste possible mais n'était pas nécessaire pour livrer.

## 6. Ce qui ne change pas

`.env` reste la source des valeurs par défaut et le seul endroit pour les secrets — rien ne casse pour un déploiement qui n'utilise jamais l'UI de paramétrage. Aucune migration de données existante nécessaire (table neuve, vide par défaut = comportement actuel inchangé tant que rien n'est sauvegardé depuis l'UI).

## 7. Décisions actées

1. **Alias d'identifiants de connecteurs** : affichés en lecture seule dans l'UI (liste des alias existants, jamais leurs valeurs).
2. **`embedding_provider`/`embedding_model`** : affichés en lecture seule avec avertissement, non éditables en V1 (casserait la compatibilité des vecteurs déjà stockés).
3. **Périmètre Phase 9.3** : `gating` + `rag` d'abord ; `agent`/`logging` en 9.4.
4. **Contrôle d'accès** : `/settings/*` n'est pas protégé pour l'instant (comme le reste de l'API, US-701/Epic 7 non implémentée) — limitation documentée explicitement dans le README, pas bloquante pour ce POC.
5. **Note** : la décision 1 (alias de connecteurs affichés en lecture seule) n'a finalement pas été implémentée — aucune section "connecteurs" n'existe dans `/settings/*`, seulement gating/rag/agent/logging (périmètre de la décision 3). À faire si le besoin se confirme.
6. **Addendum LLM/interface-first** : revirement explicite sur la clé API du modèle LLM (voir l'encadré en tête de document) — chiffrée en base plutôt que dans `.env`, seul cas de secret exposé par `/settings/*`.

---

**Prochaine étape** : démarrage phase par phase (9.1 d'abord, testable indépendamment du reste).
