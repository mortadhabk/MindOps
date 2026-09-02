# MANUEL DE TERRAIN DE L'ORCHESTRATEUR

<div align="center">

# MANUEL DE TERRAIN DE L'ORCHESTRATEUR

### Architecture, Mécanique Interne et Stratégie de Test de l'Agent MindOps

**EPIC 3 — TOOLS · MEMORY · LANGGRAPH · STREAMING**

*Édition de référence technique — impression noir & blanc haute-contraste*

</div>

---

**MINDOPS — DOCUMENTATION TECHNIQUE INTERNE**

| Champ | Valeur |
|---|---|
| **Document** | Orchestrator Field Manual — Édition Étendue (v2.0) |
| **Périmètre fonctionnel** | Epic 3 : orchestration agentique (`app/agent/`) |
| **Statut du code source** | Code non commité, branche de travail (`git status` — 9 fichiers nouveaux sous `app/agent/` et `tests/agent/`) |
| **Public visé** | Ingénieurs backend/IA, relecteurs de code, onboarding technique |
| **Modules** | 10 modules + glossaire alphabétique complet |
| **Niveau** | B3 technique — suppose Python async/await, notions FastAPI, notions LLM et function calling |
| **Stack couverte** | Python 3.12, Pydantic v2, FastAPI, SQLAlchemy async, LangChain, LangGraph, Ollama |
| **Fichiers de production couverts** | `agent/tools/base.py` · `agent/tools/search_knowledge.py` · `agent/llm_client.py` · `agent/memory.py` · `agent/orchestrator.py` · `agent/schemas.py` · `agent/router.py` |
| **Fichiers de test couverts** | `tests/agent/fakes.py` · `tests/agent/test_orchestrator.py` · `tests/agent/test_router.py` · `tests/conftest.py` |
| **Diagrammes** | 4 (vue d'ensemble, machine à états, séquence d'exécution complète, trace de récursion) |
| **Format d'impression** | Monochrome strict — hiérarchie par gras, encadrés, filets, tableaux |

> **NOTE DE LECTURE.** Ce manuel est conçu pour une impression en noir et blanc. La hiérarchie visuelle repose uniquement sur le contraste typographique — jamais la couleur : titres en gras/majuscules, encadrés à filet gauche pour les points d'attention, tableaux à bordures pour les données structurées, filets horizontaux (`---`) entre les sections majeures comme repères de saut de page. Chaque module se termine par un encadré **Vocabulaire** et par une ligne de pied de page. Le glossaire alphabétique complet est en fin de document. Lire les modules dans l'ordre : chacun s'appuie sur le précédent.

---

## TABLE DES MATIÈRES

| # | Module | Contenu clé |
|---|---|---|
| 01 | La Vue d'Ensemble | Architecture générale, patterns de conception, diagramme du graphe |
| 02 | Le Contrat d'Outil | `tools/base.py` — interface abstraite, `ABC`, `@abstractmethod` |
| 03 | Le Premier Outil Réel | `tools/search_knowledge.py` — intégration RAG, cycle de vie par requête |
| 04 | Parler au Modèle | `llm_client.py` — singleton, `@lru_cache`, `ChatOllama` |
| 05 | La Mémoire sans Écrire de Mémoire | `memory.py` — `MemorySaver`, checkpointer, `thread_id` |
| 06 | Le Cœur du Système *(EXPANSION MAJEURE)* | `orchestrator.py` — mathématique du reducer, `GraphRecursionError`, diagramme de séquence |
| 07 | La Porte HTTP *(EXPANSION MAJEURE)* | `schemas.py` & `router.py` — SSE, dependency injection, gestion d'exceptions |
| 08 | Une Question, du Début à la Fin *(EXPANSION MAJEURE)* | Trace complète d'exécution, cas limites, modes de défaillance |
| 09 | Tester un Agent sans LLM Réel *(EXPANSION MAJEURE)* | `ScriptedChatModel`, post-mortem du bug d'identité, 4 cas de test complets |
| 10 | Ce Qui Vient Ensuite — Epic 4 | `interrupt` LangGraph, gating, `send_email` |
| § | Glossaire Complet | A → Z |

---

## MODULE 01 : LA VUE D'ENSEMBLE

### 1.1 Objectif Fonctionnel

Epic 3 ajoute une seule capacité nouvelle à MindOps : un point d'entrée conversationnel, `POST /agent/chat`, où un utilisateur pose une question en langage naturel et reçoit une réponse produite par un LLM — en s'appuyant sur la base de connaissances RAG construite à l'Epic 1 lorsque des faits sont nécessaires. La pièce qui rend cela possible s'appelle l'**orchestrateur** : le composant qui décide, tour par tour, si le modèle doit répondre directement ou d'abord appeler un **outil** (`tool`) — un fragment de code que le modèle est autorisé à exécuter, comme « chercher dans la base de connaissances ».

### 1.2 Choix d'Architecture : Pourquoi LangGraph ?

Deux options existaient pour construire cette boucle : l'écrire à la main avec le SDK Anthropic/le client LLM brut (une boucle `for` classique), ou la déléguer à **LangGraph**, une librairie qui modélise une boucle de décision comme une **machine à états** (`State Graph`) — un petit nombre de **nœuds** (étapes) reliés par des **arêtes** (`edges`, des flèches « aller ici ensuite »).

Le document de cadrage interne (`cours-sdk-anthropic-vs-langgraph.md`) documente cet arbitrage en détail. Le calcul décisif : dès qu'un mécanisme de **persistance de conversation** et, plus tard, un mécanisme d'**interruption humaine** (gating, Epic 4) sont nécessaires, LangGraph fournit ces deux primitives nativement (`checkpointer`, `interrupt`) — alors qu'une boucle manuelle demanderait de les récrire à la main. Le graphe construit ici a exactement deux nœuds :

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│                         Message utilisateur arrive                       │
│                                    │                                      │
│                                    ▼                                      │
│                        ┌─────────────────────────┐                       │
│                        │   call_model             │                      │
│                        │   (interroger le LLM)    │                      │
│                        └─────────────────────────┘                       │
│                                    │                                      │
│                    ┌───────────────┴────────────────┐                    │
│      modèle demande un outil                modèle a fini               │
│                    │                                 │                   │
│                    ▼                                 ▼                   │
│        ┌─────────────────────────┐         ┌──────────────────┐         │
│        │   tools                 │         │   END             │         │
│        │   (exécuter l'outil,    │         │   (stream vers    │         │
│        │   ex : search_knowledge)│         │   l'utilisateur)  │         │
│        └─────────────────────────┘         └──────────────────┘         │
│                    │                                                      │
│                    │  boucle retour                                      │
│                    └───────────────► call_model                          │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

Le modèle reçoit une question ; s'il décide qu'il a besoin d'informations, il le signale (« appelle `search_knowledge` avec la requête X ») ; le code exécute cet outil et lui renvoie le résultat ; le modèle est réinterrogé, cette fois avec cette information supplémentaire ; ce cycle se répète jusqu'à ce que le modèle soit en mesure de donner une réponse réelle. Une limite de sécurité arrête la boucle si elle ne converge jamais (détaillé au Module 06).

### 1.3 Sept Fichiers, Sept Responsabilités

Chaque fichier a exactement un rôle — c'est un choix délibéré de conception, pas un hasard :

| Fichier | Rôle | Pattern de conception dominant |
|---|---|---|
| `agent/tools/base.py` | Définit ce qu'« être un outil » signifie, dans l'abstrait | **Interface / Port** (Ports & Adapters) |
| `agent/tools/search_knowledge.py` | Le premier outil réel : chercher dans la base RAG | **Adapter** — adapte `rag/retriever.py` au contrat `Tool` |
| `agent/llm_client.py` | Construit la connexion au modèle de langage (Ollama) | **Singleton** via `@lru_cache` |
| `agent/memory.py` | Se souvient des tours précédents d'une conversation | **Delegation** — délègue à LangGraph, n'implémente rien soi-même |
| `agent/orchestrator.py` | Le graphe lui-même — la boucle de décision | **State Machine / Graph** |
| `agent/schemas.py` | La forme d'une requête de chat entrante | **DTO** (Data Transfer Object) via Pydantic |
| `agent/router.py` | Le point d'entrée HTTP qui relie tout et streame la réponse | **Dependency Injection / Composition Root** |

### 1.4 Pourquoi Cette Décomposition Compte

Chaque fichier ne connaît que ce dont il a strictement besoin — jamais plus :

- `orchestrator.py` ne sait rien de FastAPI, de SQLAlchemy, ou de HTTP. Il reçoit un `BaseChatModel` (abstrait) et une liste de `Tool` (abstrait).
- `tools/search_knowledge.py` ne sait rien de LangGraph. Il reçoit juste une session DB et un fournisseur d'embeddings.
- `router.py` est le seul fichier qui connaît *tous* les autres — c'est le **composition root** : l'unique endroit où les objets concrets (`ChatOllama`, `SearchKnowledgeTool`, la session DB réelle) sont assemblés.

Cette discipline de dépendances est ce qui rend le Module 09 (tests sans LLM réel) possible sans aucune modification du code de production.

> **NOTE — TRADE-OFF ASSUMÉ.** Cette architecture ajoute un vocabulaire (`State`, `Node`, `Edge`, `Checkpointer`, `Reducer`) et une dépendance supplémentaire par rapport à une boucle `for` manuelle. Pour un seul outil en lecture seule et sans gating, ce coût dépasse presque le bénéfice immédiat. Le pari architectural est que ce coût sera remboursé dès l'Epic 4, quand `interrupt` remplacera une file d'attente de validation humaine écrite à la main. Voir Module 10.

---

### VOCABULAIRE — MODULE 01

| Terme | Définition |
|---|---|
| **orchestrateur** | La partie d'un programme qui contrôle l'ordre d'exécution des autres parties. Ici, elle décide « interroger le modèle » vs « exécuter un outil » vs « s'arrêter ». |
| **tool (outil)** | Une petite fonction que le modèle IA est autorisé à appeler, avec un nom et une description, pour que le modèle sache quand l'utiliser. |
| **node (nœud)** | Une étape dans un graphe — un travail unique, comme « appeler le modèle » ou « exécuter les outils ». |
| **edge (arête)** | Une flèche dans un graphe qui relie un nœud au suivant. |
| **Ports & Adapters** | Pattern architectural où le cœur métier définit un « port » (interface) que des « adaptateurs » concrets viennent implémenter, sans coupler le cœur aux détails techniques. |

---

**[ MindOps Field Manual — Module 01 | Page 5 ]**

---

## MODULE 02 : LE CONTRAT D'OUTIL

**Fichier : `app/agent/tools/base.py`**

### 2.1 Objectif Conceptuel & Architecture

Avant d'écrire un outil réel, il faut une règle que tout outil doit respecter — une **interface**. Une interface est une promesse : « toute classe qui prétend être un `Tool` doit posséder ces éléments », sans préjuger de la façon dont chaque outil fonctionne à l'intérieur. C'est le pattern **Abstract Factory / Strategy** appliqué au function calling : l'orchestrateur (Module 06) manipule des `Tool` de façon polymorphe, sans jamais connaître leur type concret.

### 2.2 Code Source Complet

```python
from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel


class Tool(ABC):
    """Port implémenté par chaque outil exposé au LLM via function calling."""

    name: ClassVar[str]
    description: ClassVar[str]
    args_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    async def execute(self, **kwargs: object) -> str:
        """Exécute l'outil et renvoie un résultat textuel à réinjecter au LLM."""
```

### 2.3 Analyse Ligne par Ligne

| Ligne | Extrait | Explication |
|---|---|---|
| 1 | `from abc import ABC, abstractmethod` | Importe le module standard `abc` (Abstract Base Classes) qui fournit les primitives d'abstraction de Python. |
| 2 | `from typing import ClassVar` | `ClassVar` est un marqueur de type qui indique que l'attribut appartient à la **classe**, pas à une instance particulière — chaque sous-classe le définit une seule fois. |
| 4 | `from pydantic import BaseModel` | Importe le modèle de base Pydantic v2, utilisé pour décrire et valider la forme des arguments d'un outil. |
| 7 | `class Tool(ABC):` | Hérite d'`ABC`. Cela empêche Python d'instancier `Tool()` directement — toute tentative lève `TypeError: Can't instantiate abstract class`. |
| 8 | `"""Port implémenté..."""` | Docstring de classe : documente l'intention architecturale (vocabulaire « port » de Ports & Adapters), pas seulement le comportement. |
| 10 | `name: ClassVar[str]` | Déclare, sans l'assigner, qu'une sous-classe doit fournir un attribut `name` de type `str` au niveau classe. |
| 11 | `description: ClassVar[str]` | Idem pour la description — ce texte est envoyé tel quel au LLM (voir 2.5). |
| 12 | `args_schema: ClassVar[type[BaseModel]]` | Notez le double niveau de type : `type[BaseModel]` signifie « une **classe** qui hérite de `BaseModel` », pas une instance. C'est le schéma lui-même qui est stocké, pas des données. |
| 14 | `@abstractmethod` | Décorateur qui marque la méthode suivante comme devant être réimplémentée par toute sous-classe concrète. |
| 15 | `async def execute(self, **kwargs: object) -> str:` | Méthode asynchrone (obligatoire, car les outils font typiquement de l'I/O — DB, API externe) ; `**kwargs: object` accepte des arguments nommés arbitraires, typés au sens le plus large possible puisque chaque outil définit sa propre signature réelle via `args_schema`. |
| 16 | `"""Exécute l'outil..."""` | Docstring de méthode — contrat explicite : entrée = arguments validés, sortie = texte prêt à être réinjecté dans l'historique de conversation. |

### 2.4 Pourquoi `ABC` et `@abstractmethod` Changent Réellement le Comportement

`ABC` (Abstract Base Class) est la façon dont Python dit : « on ne peut jamais créer un objet `Tool` nu — il faut écrire une sous-classe qui comble la pièce manquante. » La pièce manquante est marquée par `@abstractmethod` : toute sous-classe qui oublie d'écrire `execute()` plantera **immédiatement**, au moment où Python tente de l'instancier — pas plus tard, à 2h du matin, en production. C'est tout l'intérêt d'une méthode abstraite : elle transforme une erreur silencieuse en une erreur bruyante et précoce.

```python
>>> class BrokenTool(Tool):
...     name = "broken"
...     description = "oublie execute()"
...     args_schema = SomeSchema
...
>>> BrokenTool()
TypeError: Can't instantiate abstract class BrokenTool without an implementation
for abstract method 'execute'
```

### 2.5 Pourquoi une Interface du Tout ?

L'orchestrateur (Module 06) n'a jamais besoin de connaître quoi que ce soit de spécifique à un outil — ni `search_knowledge`, ni aucun outil futur. Il a seulement besoin de savoir que chaque outil possède un `name`, une `description`, un `args_schema`, et une méthode `execute()` qu'il peut `await`. C'est précisément ce qui permettra d'ajouter un deuxième, un troisième, ou un dixième outil plus tard **sans jamais toucher `orchestrator.py`** — ouvert à l'extension, fermé à la modification (principe Open/Closed).

`args_schema` remplit **deux rôles à la fois** avec une seule définition :

1. **Validation Python** : au moment de l'exécution, les arguments reçus (souvent générés par le LLM, donc non fiables a priori) peuvent être validés contre ce schéma Pydantic.
2. **Génération du schéma JSON envoyé au modèle** : `args_schema.model_json_schema()` (voir Module 06, `build_graph`) produit exactement la structure JSON Schema que le LLM lit pour comprendre quels arguments il doit fournir.

Une seule source de vérité — pas de duplication entre « ce que Python attend » et « ce que le modèle croit devoir envoyer ».

---

### VOCABULAIRE — MODULE 02

| Terme | Définition |
|---|---|
| **classe abstraite** | Une classe qui ne peut pas être instanciée directement — elle n'existe que pour être étendue par des sous-classes plus spécifiques. |
| **méthode abstraite** | Une méthode déclarée mais non écrite dans la classe abstraite ; chaque sous-classe est forcée de l'écrire. |
| **sous-classe** | Une nouvelle classe construite « au-dessus » d'une existante, héritant de sa forme et complétant les détails manquants. |
| **schéma (schema)** | Une description précise de la forme attendue d'une donnée (quels champs existent, quel type a chacun). |
| **valider (validate)** | Vérifier qu'une donnée correspond réellement à son schéma attendu avant de l'utiliser. |
| **ClassVar** | Annotation de type Python indiquant qu'un attribut est partagé au niveau de la classe, et non recréé par instance. |
| **Open/Closed Principle** | Principe de conception : le code doit être ouvert à l'extension (ajouter des outils) mais fermé à la modification (ne pas retoucher l'orchestrateur). |

---

**[ MindOps Field Manual — Module 02 | Page 8 ]**

---

## MODULE 03 : LE PREMIER OUTIL RÉEL

**Fichier : `app/agent/tools/search_knowledge.py`**

### 3.1 Objectif Conceptuel & Architecture

Cette classe est la première à réellement combler la promesse du Module 02. Elle enveloppe (pattern **Adapter**) la fonction de recherche RAG déjà construite à l'Epic 1 (`app/rag/retriever.py`) — l'orchestrateur ne réinvente pas la recherche sémantique, il la réutilise telle quelle.

Pour rappel, la fonction adaptée a la signature suivante (Epic 1, `rag/retriever.py`) :

```python
async def search(
    db: AsyncSession,
    query: str,
    provider: EmbeddingProvider,
    top_k: int = 5,
    similarity_threshold: float | None = None,
) -> list[tuple[Chunk, float]]:
    ...
```

### 3.2 Code Source Complet

```python
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import Tool
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.retriever import search as search_chunks


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(
        description="La question ou le sujet à rechercher dans la base de connaissances"
    )


class SearchKnowledgeTool(Tool):
    """Outil de lecture seule : cherche dans la base de connaissances RAG (Epic 1)."""

    name = "search_knowledge"
    description = (
        "Cherche dans la base de connaissances les fragments les plus pertinents pour répondre "
        "à une question factuelle. À utiliser avant de répondre sur un sujet du domaine."
    )
    args_schema = SearchKnowledgeArgs

    def __init__(self, db: AsyncSession, provider: EmbeddingProvider, top_k: int = 5):
        self._db = db
        self._provider = provider
        self._top_k = top_k

    async def execute(self, *, query: str) -> str:
        results = await search_chunks(self._db, query, self._provider, top_k=self._top_k)
        if not results:
            return "Aucun fragment pertinent trouvé dans la base de connaissances."
        return "\n\n".join(
            f"[source: document#{chunk.document_id}] {chunk.text}" for chunk, _score in results
        )
```

### 3.3 Analyse Ligne par Ligne

| Ligne | Extrait | Explication |
|---|---|---|
| 6 | `from app.rag.retriever import search as search_chunks` | Alias explicite : renomme `search` en `search_chunks` à l'import pour éviter toute ambiguïté avec `Tool.execute`, et pour que l'appel plus bas (`await search_chunks(...)`) se lise sans confusion avec une méthode locale. |
| 9-12 | `class SearchKnowledgeArgs(BaseModel): query: str = Field(description=...)` | Le `Field(description=...)` n'est pas décoratif : Pydantic v2 l'intègre dans `model_json_schema()`, donc cette phrase française finit littéralement dans le JSON Schema envoyé au LLM comme description du paramètre `query`. |
| 18 | `name = "search_knowledge"` | Redéfinit le `ClassVar` abstrait du Module 02 avec une valeur concrète — c'est cet identifiant exact que le LLM renverra dans `tool_calls[i]["name"]`, et que `call_tools` (Module 06) utilisera pour retrouver l'outil dans `tools_by_name`. |
| 19-22 | `description = (...)` | Chaîne envoyée telle quelle au modèle comme partie de la définition d'outil. **Ce n'est pas un commentaire pour humains** — c'est un prompt. |
| 23 | `args_schema = SearchKnowledgeArgs` | Relie la classe de schéma définie plus haut au contrat `Tool`. |
| 25 | `def __init__(self, db: AsyncSession, provider: EmbeddingProvider, top_k: int = 5):` | Le constructeur prend des **dépendances par injection de constructeur** — jamais construites en interne (pas de `AsyncSession()` ici), toujours reçues de l'extérieur. |
| 26-28 | `self._db = db` / `self._provider = provider` / `self._top_k = top_k` | Convention de nommage `_` (préfixe underscore) : signale que ces attributs sont un détail d'implémentation privé, pas une API publique de l'outil. |
| 30 | `async def execute(self, *, query: str) -> str:` | Le `*,` force `query` à être un argument **nommé uniquement** (keyword-only). C'est crucial : `call_tools` (Module 06) appelle `tool.execute(**call["args"])` — un dictionnaire déballé en arguments nommés — donc `execute` doit accepter des kwargs correspondant exactement aux clés JSON que le LLM a produites. |
| 31 | `results = await search_chunks(...)` | Délègue entièrement la recherche vectorielle à Epic 1 — zéro logique de similarité dupliquée ici. |
| 32-33 | `if not results: return "Aucun fragment pertinent..."` | Cas limite géré explicitement : une liste vide n'est **pas** une erreur, c'est un résultat valide qui doit être communiqué au LLM en texte clair pour qu'il ne hallucine pas une source inexistante. |
| 34-36 | `return "\n\n".join(f"[source: document#{chunk.document_id}] {chunk.text}" ...)` | Formatage en texte brut avec attribution de source inline — chaque fragment est préfixé par son origine, ce qui permet au system prompt (« Cite les sources utilisées », Module 06) d'être suivi par le modèle sans travail supplémentaire. |

### 3.4 Pourquoi une Instance par Requête, et Pas un Singleton ?

Contrairement à `llm_client.py` (Module 04), `SearchKnowledgeTool` n'est **pas** construit une fois pour toutes et réutilisé — le `__init__` prend une session de base de données et un fournisseur d'embeddings en arguments, et une nouvelle instance est créée à **chaque requête HTTP** (voir Module 07). La raison est un invariant strict de SQLAlchemy async : une session de base de données appartient à **une** requête HTTP entrante ; elle ne peut pas être partagée en toute sécurité entre deux utilisateurs qui discutent au même moment (risque de corruption d'état partagé, de fuite de transaction, ou de compétition sur un curseur asynchrone).

C'est ce qui distingue un objet à **état par requête** (`per-request state`) d'un objet sans état de ce type — ce dernier peut être construit une fois et réutilisé indéfiniment, ce qui est exactement ce que fait le Module 04 pour la connexion au modèle de langage.

> **NOTE — TRADE-OFF ASSUMÉ.** Reconstruire un objet `SearchKnowledgeTool` (et, en cascade, un graphe LangGraph entier via `build_graph`, Module 06) à chaque appel HTTP a un coût CPU marginal mais réel. Le choix explicite ici est : correction avant micro-optimisation. Tant que le volume de requêtes reste celui d'un POC, ce coût est négligeable face au risque de partage d'état incorrect entre requêtes concurrentes.

---

### VOCABULAIRE — MODULE 03

| Terme | Définition |
|---|---|
| **session (base de données)** | Une connexion temporaire à la base de données, ouverte pour la durée d'une requête, puis fermée. |
| **embedding** | Une liste de nombres qui représente le sens d'un texte, utilisée pour comparer la similarité entre deux textes. |
| **état par requête (per-request state)** | Une information qui doit être créée fraîche pour chaque requête entrante, et jamais réutilisée entre requêtes différentes. |
| **keyword-only argument** | Un paramètre de fonction qui ne peut être passé que par son nom (`query=...`), jamais par position, forcé par le `*` dans la signature. |
| **Adapter (pattern)** | Un composant qui traduit l'interface d'un système existant (ici `rag/retriever.py`) vers l'interface attendue par un autre système (ici `Tool`). |

---

**[ MindOps Field Manual — Module 03 | Page 11 ]**

---

## MODULE 04 : PARLER AU MODÈLE

**Fichier : `app/agent/llm_client.py`**

### 4.1 Objectif Conceptuel & Architecture

Ce fichier est délibérément minuscule. Son unique travail est de construire un objet — une instance `ChatOllama`, l'enveloppe standard de LangChain autour d'un modèle exécuté via Ollama en local. Le pattern de conception ici est le **Singleton**, mais implémenté sans classe singleton classique : via un décorateur de mémoïsation sur une fonction factory.

### 4.2 Code Source Complet

```python
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config import get_settings


@lru_cache
def get_llm_client() -> BaseChatModel:
    settings = get_settings()
    if settings.llm_provider != "ollama":
        raise ValueError(f"Fournisseur LLM non supporté : {settings.llm_provider}")
    return ChatOllama(model=settings.llm_model, base_url=settings.ollama_base_url, temperature=0)
```

### 4.3 Analyse Ligne par Ligne

| Ligne | Extrait | Explication |
|---|---|---|
| 1 | `from functools import lru_cache` | Importe le décorateur de mémoïsation de la bibliothèque standard. |
| 3 | `from langchain_core.language_models import BaseChatModel` | Le **type de retour annoncé** est la classe abstraite de LangChain — pas `ChatOllama` directement. C'est ce qui permet au Module 09 de substituer n'importe quel autre `BaseChatModel` (y compris `ScriptedChatModel`) sans violer le contrat de type. |
| 9 | `@lru_cache` | Sans arguments, équivaut à `@lru_cache(maxsize=128)` — mais comme cette fonction est appelée avec zéro argument à chaque fois, il n'existe qu'une seule entrée possible dans le cache : la mémoïsation dégénère exactement en un singleton. |
| 10 | `def get_llm_client() -> BaseChatModel:` | Fonction factory : le point d'entrée unique par lequel *tout* le reste du code doit obtenir un client LLM. |
| 11 | `settings = get_settings()` | Récupère la configuration globale (elle-même mise en cache via son propre `@lru_cache` dans `app/config.py`). |
| 12-13 | `if settings.llm_provider != "ollama": raise ValueError(...)` | Garde-fou explicite : échoue vite et fort (« fail fast ») si la configuration pointe vers un fournisseur non implémenté, plutôt que de laisser `ChatOllama` être construit avec des paramètres incohérents. |
| 14 | `return ChatOllama(model=settings.llm_model, base_url=settings.ollama_base_url, temperature=0)` | Construit l'objet réel une seule fois. `temperature=0` est un choix de produit, pas un détail technique — voir 4.4. |

### 4.4 Pourquoi `@lru_cache` Ici Précisément

La toute première fois que `get_llm_client()` est appelée, la fonction s'exécute réellement et construit l'objet `ChatOllama`. Chaque appel suivant renvoie **l'objet identique**, instantanément, sans jamais réexécuter le corps de la fonction. Cela compte car ouvrir une nouvelle configuration de connexion à chaque message de chat serait un gaspillage de ressources — contrairement à `SearchKnowledgeTool` (Module 03), un client LLM n'a **pas** d'état par requête : il ne détient aucune session de base de données, aucun état spécifique à un utilisateur.

`temperature=0` indique au modèle d'être aussi déterministe que possible — choisir le mot suivant le plus probable à chaque fois, plutôt que d'ajouter de l'aléatoire. Pour un agent qui doit décider de façon fiable « dois-je appeler un outil ou non », la prévisibilité vaut plus que la créativité.

### 4.5 Pourquoi Cacher Cela Derrière une Fonction du Tout ?

Rien dans `orchestrator.py` ni `router.py` n'importe `ChatOllama` directement. Ils demandent uniquement « le client LLM courant » à travers cette unique fonction — que le système d'injection de dépendances de FastAPI appelle pour nous (voir Module 07). Dans un test, il suffit de remplacer `get_llm_client` par un objet factice qui renvoie des réponses scriptées, et rien d'autre dans le code n'a besoin de changer. Cette unique couche d'indirection est ce qui rend le système entier testable sans modèle réel en cours d'exécution — c'est le fil conducteur qui aboutit au Module 09.

> **NOTE — PIÈGE POTENTIEL AVEC `@lru_cache`.** Parce que `get_llm_client()` est mis en cache sans argument, un changement de configuration (`llm_model`, `ollama_base_url`) en cours de vie du processus n'aura **aucun effet** tant que le processus n'est pas redémarré — le cache renvoie toujours l'instance construite avec les réglages lus au premier appel. C'est acceptable ici car `get_settings()` est elle-même mise en cache de façon identique (immutabilité de la configuration pour la durée du processus), donc les deux caches sont cohérents entre eux par construction.

---

### VOCABULAIRE — MODULE 04

| Terme | Définition |
|---|---|
| **décorateur (decorator)** | Un marqueur spécial (écrit avec `@`) placé au-dessus d'une fonction, qui change son comportement sans réécrire son corps. |
| **singleton** | Un objet qui n'est créé qu'une seule fois, puis réutilisé partout où il est nécessaire. |
| **déterministe** | Qui produit toujours la même sortie pour la même entrée — l'opposé de l'aléatoire. |
| **mémoïsation (memoization)** | Technique consistant à mettre en cache le résultat d'un appel de fonction pour des arguments donnés, afin d'éviter de le recalculer. |
| **fail fast** | Principe de conception : détecter et signaler une erreur le plus tôt possible dans le flux d'exécution, plutôt que de la laisser se propager silencieusement. |

---

**[ MindOps Field Manual — Module 04 | Page 13 ]**

---

## MODULE 05 : LA MÉMOIRE SANS ÉCRIRE DE MÉMOIRE

**Fichier : `app/agent/memory.py`**

### 5.1 Objectif Conceptuel & Architecture

Une première version de ce fichier aurait pu être un simple dictionnaire Python associant un identifiant de conversation à une liste de messages passés, écrit à la main. Ce n'est pas ce choix qui a été fait. LangGraph possède déjà un concept natif pour cela, appelé un **checkpointer** : à chaque fois que le graphe termine une étape, il sauvegarde automatiquement l'état complet (toute la liste de messages jusqu'ici) sous une clé appelée **thread ID**. Le pattern de conception est ici la **délégation totale** : ce fichier n'implémente aucune logique de persistance lui-même.

### 5.2 Code Source Complet

```python
from langgraph.checkpoint.memory import MemorySaver

# Historique de conversation en mémoire, indexé par thread_id (= conversation_id).
# Remplaçable par un checkpointer Postgres (langgraph-checkpoint-postgres) sans toucher
# à l'orchestrateur : c'est tout l'intérêt du checkpointer LangGraph.
checkpointer = MemorySaver()


def config_for(conversation_id: str) -> dict:
    return {"configurable": {"thread_id": conversation_id}}
```

### 5.3 Analyse Ligne par Ligne

| Ligne | Extrait | Explication |
|---|---|---|
| 1 | `from langgraph.checkpoint.memory import MemorySaver` | Importe l'implémentation la plus simple possible de l'interface `BaseCheckpointSaver` de LangGraph. |
| 3-5 | *(commentaire)* | Documente explicitement l'intention de remplacement futur — un commentaire qui décrit un choix d'architecture réversible, pas ce que fait le code (que le code montre déjà lui-même). |
| 6 | `checkpointer = MemorySaver()` | Instancié **une seule fois**, au niveau module — donc partagé (importé comme le même objet) par tout le processus, y compris entre requêtes HTTP différentes. C'est cette ligne, et non un mécanisme caché, qui fait persister l'historique entre deux appels à `POST /agent/chat` avec le même `conversation_id`. |
| 9-10 | `def config_for(conversation_id: str) -> dict: return {"configurable": {"thread_id": conversation_id}}` | Fonction utilitaire qui traduit le vocabulaire du domaine (`conversation_id`, tel que reçu du client HTTP) vers le vocabulaire attendu par l'API LangGraph (`thread_id`, dans un dictionnaire `configurable`). **Un seul concept, deux noms.** |

### 5.4 Ce que `MemorySaver` Fait Réellement

`MemorySaver` garde tout dans la mémoire du **processus lui-même** — elle disparaît si le serveur redémarre. C'est acceptable pour une preuve de concept. La décision de conception importante est que **rien d'autre dans la base de code n'a besoin de le savoir** : si cette ligne devient un jour `PostgresSaver(...)` pour que les conversations survivent à un redémarrage, aucun autre fichier ne change — ni `orchestrator.py` (qui reçoit un `BaseCheckpointSaver` générique en paramètre de `build_graph`), ni `router.py` (qui importe simplement `checkpointer` par son nom).

> **NOTE — POINT D'ATTENTION EN TEST.** Les tests d'`orchestrator.py` (Module 09) n'importent **jamais** ce `checkpointer` partagé — chaque test construit son propre `MemorySaver()` frais via `build_graph(llm, tools, MemorySaver())`. C'est un choix délibéré d'isolation : réutiliser l'objet module-level entre tests créerait une fuite d'état de conversation d'un test à l'autre, un `thread_id` de test pouvant accidentellement retrouver l'historique laissé par un test précédent.

---

### VOCABULAIRE — MODULE 05

| Terme | Définition |
|---|---|
| **checkpoint** | Un instantané sauvegardé de l'état d'un programme à un moment donné, qui peut être rechargé plus tard. |
| **thread (au sens LangGraph)** | Pas un « thread » d'exécution au sens informatique — ici, simplement « une conversation en cours », identifiée par un ID. |
| **persistance** | La capacité d'une donnée à survivre après l'arrêt du programme qui l'a créée. |
| **checkpointer** | Le composant LangGraph responsable de sauvegarder et recharger l'état d'un graphe entre les invocations. |

---

**[ MindOps Field Manual — Module 05 | Page 15 ]**

---

## MODULE 06 : LE CŒUR DU SYSTÈME *(EXPANSION MAJEURE)*

**Fichier : `app/agent/orchestrator.py`**

> **NOTE.** Tout ce qui précède dans ce manuel existe pour soutenir ce fichier unique. Le reste des modules du manuel s'y réfère constamment. C'est la section la plus dense du document — elle mérite d'être lue lentement, avec le code source ouvert à côté.

### 6.1 Objectif Conceptuel & Architecture

`orchestrator.py` implémente la boucle de décision agentique comme une **machine à états finis** (`Graph State Machine` pattern), où :

- **l'état** (`state`) est l'historique complet de la conversation ;
- **les nœuds** (`call_model`, `call_tools`) sont des transformations pures de « état actuel » vers « delta d'état » ;
- **les arêtes** (`edges`), dont une **arête conditionnelle**, décrivent les transitions autorisées ;
- **un reducer** (fourni par LangGraph, pas écrit ici) fusionne chaque delta produit par un nœud dans l'état global.

Ce choix architectural déplace toute la complexité de contrôle de flux (boucle, condition d'arrêt, historique) vers une librairie éprouvée, et réduit le code métier à deux fonctions pures et une fonction de routage.

### 6.2 Code Source Complet

```python
from collections.abc import AsyncIterator, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, MessagesState, StateGraph

from app.agent.tools.base import Tool

SYSTEM_PROMPT = (
    "Tu es un assistant qui répond aux questions en t'appuyant sur la base de connaissances "
    "via l'outil search_knowledge quand c'est pertinent. Cite les sources utilisées."
)

# Une itération = un aller-retour (appel LLM + éventuel appel outil). Le recursion_limit
# de LangGraph compte chaque étape du graphe, donc on double pour couvrir call_model + tools.
MAX_ITERATIONS = 5
RECURSION_LIMIT = MAX_ITERATIONS * 2


def build_graph(llm: BaseChatModel, tools: Sequence[Tool], checkpointer: BaseCheckpointSaver):
    tools_by_name = {tool.name: tool for tool in tools}
    tool_defs = [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.args_schema.model_json_schema(),
        }
        for tool in tools
    ]
    llm_with_tools = llm.bind_tools(tool_defs) if tool_defs else llm

    async def call_model(state: MessagesState) -> dict:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def call_tools(state: MessagesState) -> dict:
        last_message = state["messages"][-1]
        results = []
        for call in last_message.tool_calls:
            tool = tools_by_name.get(call["name"])
            if tool is None:
                content = f"Outil inconnu : {call['name']}"
            else:
                content = await tool.execute(**call["args"])
            results.append(ToolMessage(content=content, tool_call_id=call["id"]))
        return {"messages": results}

    def route_after_model(state: MessagesState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", call_tools)
    graph.set_entry_point("call_model")
    graph.add_conditional_edges("call_model", route_after_model, {"tools": "tools", END: END})
    graph.add_edge("tools", "call_model")

    return graph.compile(checkpointer=checkpointer)


async def stream_chat(app, *, conversation_id: str, user_message: str) -> AsyncIterator[str]:
    config = {"configurable": {"thread_id": conversation_id}, "recursion_limit": RECURSION_LIMIT}
    inputs = {"messages": [HumanMessage(content=user_message)]}
    try:
        async for chunk, metadata in app.astream(inputs, config=config, stream_mode="messages"):
            if metadata.get("langgraph_node") == "call_model" and chunk.content:
                yield chunk.content
    except GraphRecursionError:
        yield "\n\n[Erreur : nombre maximum d'itérations atteint sans réponse finale.]"
```

### 6.3 Analyse Ligne par Ligne

| Ligne / Bloc | Extrait | Explication |
|---|---|---|
| 1 | `from collections.abc import AsyncIterator, Sequence` | `AsyncIterator[str]` type le générateur asynchrone `stream_chat` ; `Sequence[Tool]` accepte toute séquence immuable de `Tool` (liste, tuple) sans imposer `list` précisément — principe de typage le plus permissif possible côté paramètre. |
| 4 | `from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage` | Les quatre types concrets de message du modèle de messages LangChain, chacun avec une sémantique de rôle distincte (voir 6.4). |
| 5 | `from langgraph.checkpoint.base import BaseCheckpointSaver` | Type abstrait — `build_graph` accepte n'importe quel checkpointer conforme, pas seulement `MemorySaver`. |
| 6 | `from langgraph.errors import GraphRecursionError` | Exception spécifique levée par le moteur d'exécution de LangGraph (le *Pregel executor*) quand une limite de récursion est dépassée. |
| 7 | `from langgraph.graph import END, MessagesState, StateGraph` | `END` est un sentinel spécial (pas une chaîne arbitraire) qui signale la sortie du graphe ; `MessagesState` est un état préfabriqué (voir 6.4) ; `StateGraph` est le constructeur de graphe. |
| 11-14 | `SYSTEM_PROMPT = (...)` | Constante module-level — un seul point de vérité pour l'instruction système, réutilisée à chaque appel de `call_model` (voir note 6.7 sur la non-persistance de ce message). |
| 18-19 | `MAX_ITERATIONS = 5` / `RECURSION_LIMIT = MAX_ITERATIONS * 2` | Voir la section 6.6 dédiée — le facteur `* 2` n'est pas arbitraire, il reflète une réalité précise du modèle de comptage de LangGraph. |
| 22 | `def build_graph(llm, tools, checkpointer):` | Factory : construit et compile un nouveau graphe à partir de trois dépendances **injectées**, jamais construites en interne — aucune de ces trois valeurs n'est importée directement dans ce fichier. |
| 23 | `tools_by_name = {tool.name: tool for tool in tools}` | Index en O(1) par nom, utilisé plus bas dans `call_tools` pour retrouver l'outil correspondant à un appel du modèle. |
| 24-31 | `tool_defs = [...]` | Traduit chaque `Tool` (objet Python) en un dictionnaire JSON-compatible `{name, description, parameters}` — c'est exactement le format « simplifié » que `convert_to_openai_tool` de LangChain sait reconnaître et normaliser vers le format function-calling attendu par le fournisseur (ici Ollama). |
| 32 | `llm_with_tools = llm.bind_tools(tool_defs) if tool_defs else llm` | Garde défensive : si la liste d'outils est vide, `bind_tools` n'est même pas appelé — évite un appel inutile ou potentiellement invalide sur certains fournisseurs avec une liste d'outils vide. |
| 34-39 | `async def call_model(state) -> dict:` | Voir 6.5. |
| 41-51 | `async def call_tools(state) -> dict:` | Voir 6.5. |
| 53-57 | `def route_after_model(state) -> str:` | Voir 6.5 — remarquez : **synchrone**, pas `async`, car aucune I/O n'y est effectuée, seulement une inspection de l'état déjà en mémoire. |
| 59-64 | Construction du graphe (`StateGraph`, `add_node`, `set_entry_point`, `add_conditional_edges`, `add_edge`) | Voir 6.5. |
| 66 | `return graph.compile(checkpointer=checkpointer)` | `compile()` transforme la définition déclarative du graphe en un objet exécutable (`CompiledStateGraph`), qui expose `.ainvoke()` et `.astream()`. Le graphe compilé encapsule le checkpointer : chaque invocation ultérieure sait automatiquement où lire/écrire l'état persistant. |
| 69 | `async def stream_chat(app, *, conversation_id: str, user_message: str) -> AsyncIterator[str]:` | `app` ici est le graphe compilé (nom conventionnel LangGraph, à ne pas confondre avec l'application FastAPI du Module 07) ; `*,` force les deux autres paramètres à être nommés. |
| 70 | `config = {"configurable": {"thread_id": conversation_id}, "recursion_limit": RECURSION_LIMIT}` | Le dictionnaire `config` est le canal par lequel LangGraph reçoit à la fois l'identifiant de conversation et la limite de sécurité — deux préoccupations orthogonales transmises dans la même structure, par convention LangGraph. |
| 71 | `inputs = {"messages": [HumanMessage(content=user_message)]}` | Seul le **nouveau** message utilisateur est fourni en entrée — pas l'historique complet. Le checkpointer recharge automatiquement l'historique déjà stocké sous ce `thread_id` et le reducer `add_messages` (voir 6.4) ajoute ce nouveau message à la suite. |
| 73 | `async for chunk, metadata in app.astream(inputs, config=config, stream_mode="messages"):` | Voir 6.8 (streaming). |
| 74-75 | `if metadata.get("langgraph_node") == "call_model" and chunk.content: yield chunk.content` | Double filtre : (a) ne garder que les chunks produits par le nœud `call_model` — pas les `ToolMessage` du nœud `tools`, qui ne sont pas destinés aux yeux de l'utilisateur ; (b) ignorer les chunks à contenu vide (typiquement, les tokens intermédiaires d'un appel d'outil en cours de construction n'ont pas de `content` textuel). |
| 76-77 | `except GraphRecursionError: yield "..."` | Convertit une exception de bas niveau du moteur de graphe en un message utilisateur normal, plutôt qu'un crash serveur brut. Voir 6.6. |

### 6.4 DEEP DIVE — L'État et le Reducer : Mathématique de `add_messages`

`MessagesState` est une forme d'état prête à l'emploi fournie par LangGraph — en substance :

```python
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

Le type `Annotated[list[AnyMessage], add_messages]` attache une **métadonnée de reducer** au champ `messages`. Un **reducer** est une fonction pure `(état_actuel, delta_proposé) -> nouvel_état`. Chaque nœud (`call_model`, `call_tools`) ne renvoie **jamais** l'état entier réécrit à la main — seulement un petit dictionnaire décrivant ce qui a changé (`{"messages": [...]}`). C'est le moteur LangGraph, via le reducer enregistré, qui fusionne ce delta dans l'état réel.

**L'algorithme de `add_messages`, en substance (comportement documenté) :**

```python
def add_messages(left: list[BaseMessage], right: list[BaseMessage]) -> list[BaseMessage]:
    left = coerce_to_messages(left)
    right = coerce_to_messages(right)

    # 1. Toute message sans id explicite en reçoit un, généré aléatoirement.
    for m in left:
        if m.id is None:
            m.id = str(uuid.uuid4())
    for m in right:
        if m.id is None:
            m.id = str(uuid.uuid4())

    # 2. Index des messages existants par id.
    existing_ids = {m.id: i for i, m in enumerate(left)}
    merged = list(left)

    # 3. Fusion : même id => remplacement EN PLACE (position inchangée) ;
    #    id nouveau => ajout en fin de liste.
    for m in right:
        idx = existing_ids.get(m.id)
        if idx is not None:
            merged[idx] = m
        else:
            merged.append(m)

    return merged
```

> **NOTE — CAS LIMITE SUPPLÉMENTAIRE.** LangGraph reconnaît aussi un sentinel spécial, `RemoveMessage(id=...)`, que `add_messages` interprète comme « supprimer le message portant cet id de la liste fusionnée » plutôt que comme un ajout ou un remplacement. Ce mécanisme n'est pas utilisé dans le code actuel de MindOps, mais il explique pourquoi le reducer raisonne fondamentalement **par identité (`id`)**, jamais par égalité de contenu — un point essentiel pour comprendre le Module 09.

**Ce que cela signifie concrètement pour `orchestrator.py` :**

Deux règles gouvernent tout le comportement observable de la boucle :

1. **Un nouveau message (`id` inédit) est toujours ajouté en fin de liste.** C'est le cas normal : chaque réponse du modèle, chaque résultat d'outil, arrive avec un `id` frais (LangChain génère un UUID à la création de chaque `AIMessage`/`ToolMessage` si aucun n'est fourni explicitement) et s'empile donc naturellement à la suite de la conversation.
2. **Un message dont l'`id` existe déjà dans l'état remplace l'ancien, à la même position — il n'est jamais déplacé en fin de liste.** C'est un mécanisme de **mise à jour**, pas d'accumulation. Ce comportement est invisible tant que chaque appel produit des objets avec des `id` distincts — et devient une source de bug silencieux dès qu'un même objet (donc un même `id`) est réutilisé involontairement. **C'est exactement le sujet du post-mortem du Module 09.**

### 6.5 Les Deux Nœuds et la Décision de Routage

**`call_model`** envoie l'historique complet au LLM et récupère une réponse — soit du texte, soit une demande d'appel d'outil (jamais les deux simultanément avec les modèles utilisés ici). Notez la garde `if not messages or not isinstance(messages[0], SystemMessage): messages = [SystemMessage(...), *messages]` : elle construit une **copie locale** de la liste de messages, avec le prompt système préfixé, uniquement pour l'appel `.ainvoke()`. Le retour de la fonction, `{"messages": [response]}`, ne contient **que** la réponse du modèle — jamais ce `SystemMessage` local.

> **NOTE D'ARCHITECTURE — LE SYSTEM PROMPT N'EST JAMAIS PERSISTÉ.** Puisque seule la réponse du modèle (`response`, un `AIMessage`) est renvoyée pour fusion dans l'état, le `SystemMessage` construit localement n'est **jamais** écrit dans l'état géré par le checkpointer. Conséquence directe et non triviale : à chaque invocation de `call_model` — y compris la deuxième, troisième invocation **au sein d'un même tour** de la boucle outil→modèle — `state["messages"][0]` est et reste le tout premier `HumanMessage` de la conversation, jamais un `SystemMessage`. La condition `not isinstance(messages[0], SystemMessage)` est donc **structurellement toujours vraie** dans ce système : le prompt système est reconstruit et préfixé à chaque appel du modèle, pas une seule fois par conversation. Ce n'est pas un bug — le comportement final observé (le modèle voit toujours le system prompt) est correct — mais un lecteur pressé pourrait croire, à tort, que cette garde empêche une duplication qui, en l'état actuel du code, ne peut de toute façon jamais se produire. C'est un exemple concret de code défensif dont la condition de garde est vraie par construction.

**`call_tools`** fait le travail inverse : il regarde le dernier message, trouve chaque appel d'outil demandé par le modèle (`last_message.tool_calls`, une liste — le modèle peut demander plusieurs outils en parallèle), exécute réellement chacun via `await tool.execute(**call["args"])`, et enveloppe chaque résultat dans un `ToolMessage` — un type de message spécial qui **doit** porter le même `tool_call_id` que celui utilisé par le modèle pour poser sa question, afin que le modèle puisse faire correspondre la réponse à sa propre demande.

> **NOTE — TRADE-OFF ASSUMÉ : EXÉCUTION SÉQUENTIELLE, PAS PARALLÈLE.** La boucle `for call in last_message.tool_calls:` exécute chaque appel d'outil **l'un après l'autre** (`await` séquentiel), même si le modèle a demandé plusieurs outils en un seul tour (tool calling parallèle). Une version optimisée utiliserait `asyncio.gather(*(execute_one(c) for c in calls))` pour paralléliser les appels indépendants. Avec un seul outil enregistré aujourd'hui (`search_knowledge`), ce choix est sans conséquence observable — mais il redeviendra pertinent dès qu'un deuxième outil sera ajouté et que le modèle commencera à en demander plusieurs à la fois.

> **NOTE — RÉSILIENCE AUX HALLUCINATIONS DE NOM D'OUTIL.** Si `tools_by_name.get(call["name"])` renvoie `None` (le modèle a halluciné un nom d'outil qui n'existe pas), le code ne lève **pas** d'exception — il construit un `ToolMessage` contenant `"Outil inconnu : {nom}"`, avec le bon `tool_call_id`. Ce message est réinjecté normalement dans la boucle : au tour suivant, le modèle **voit son erreur** et peut se corriger de lui-même, plutôt que de faire planter toute la requête HTTP.

**`route_after_model`** est le seul endroit où la boucle « décide » réellement quelque chose. Si le dernier message du modèle contient des appels d'outils, aller les exécuter ; sinon, la conversation est terminée pour ce tour — aller à `END`. Cette fonction est câblée dans le graphe via `add_conditional_edges`, la façon dont LangGraph exprime « après ce nœud, demander à cette fonction quel nœud vient ensuite ». Le troisième argument, `{"tools": "tools", END: END}`, est une **table de correspondance** entre la valeur renvoyée par `route_after_model` et le nœud réel à activer — un mapping explicite plutôt qu'une convention implicite de nommage.

### 6.6 DEEP DIVE — `GraphRecursionError` : Calcul Exact de la Limite

`recursion_limit` plafonne le nombre total d'**étapes** (chaque exécution d'un nœud = une étape, aussi appelée *super-step* dans la terminologie Pregel dont LangGraph s'inspire) que le graphe entier est autorisé à effectuer, avant que LangGraph lève lui-même une `GraphRecursionError` — sans qu'aucun compteur ne soit écrit à la main dans ce code.

Le commentaire du code est précis et vérifiable : *« Une itération = un aller-retour (appel LLM + éventuel appel outil). Le `recursion_limit` de LangGraph compte chaque étape du graphe, donc on double pour couvrir `call_model` + `tools`. »* Avec `MAX_ITERATIONS = 5`, on obtient `RECURSION_LIMIT = 10`.

**Trace numérique exacte** (cas pathologique : le modèle ne s'arrête jamais de demander l'outil) :

| Étape (super-step) | Nœud exécuté | Cumul d'étapes | État |
|---|---|---|---|
| 1 | `call_model` | 1 | Itération 1 — demande un outil |
| 2 | `tools` | 2 | Résultat de l'outil ajouté |
| 3 | `call_model` | 3 | Itération 2 — redemande un outil |
| 4 | `tools` | 4 | Résultat ajouté |
| 5 | `call_model` | 5 | Itération 3 |
| 6 | `tools` | 6 | Résultat ajouté |
| 7 | `call_model` | 7 | Itération 4 |
| 8 | `tools` | 8 | Résultat ajouté |
| 9 | `call_model` | 9 | Itération 5 |
| 10 | `tools` | 10 | Résultat ajouté — **limite atteinte (10 = `RECURSION_LIMIT`)** |
| **11** | *(tentative)* `call_model` | **11 > 10** | **`GraphRecursionError` levée avant exécution de cette 6ᵉ invocation du modèle** |

**Conclusion opérationnelle :** avec la configuration par défaut, le modèle dispose exactement de **5 allers-retours complets** modèle↔outil pour converger vers une réponse finale. S'il tente un 6ᵉ appel d'outil, l'exception est levée **avant** que ce 6ᵉ appel au modèle ne s'exécute — aucun appel réseau supplémentaire vers Ollama n'est effectué au-delà de la limite.

Ce comportement est directement vérifié par le test `test_agent_stops_when_llm_never_stops_calling_tools` (Module 09), qui utilise volontairement une limite réduite (`recursion_limit: 6`) pour ne pas attendre 10 étapes réelles dans la suite de tests — avec une limite de 6, la trace s'arrête après 3 cycles complets (étapes 1 à 6), et la tentative de 4ᵉ `call_model` (étape 7) lève l'exception.

`stream_chat` capture précisément cette exception, et uniquement celle-ci :

```python
except GraphRecursionError:
    yield "\n\n[Erreur : nombre maximum d'itérations atteint sans réponse finale.]"
```

Toute autre exception (voir Module 07 pour le cas d'une erreur d'outil ou de connexion au LLM) **n'est pas** interceptée ici et se propage plus haut dans la pile d'appel — voir Module 08 pour les conséquences précises sur la connexion SSE.

### 6.7 DEEP DIVE — Le Streaming : `stream_mode="messages"`

`app.astream(inputs, config=config, stream_mode="messages")` est ce qui fait apparaître la réponse mot par mot plutôt que d'un seul bloc à la fin. Ce mode de streaming particulier de LangGraph produit un flux de tuples `(chunk, metadata)` :

- `chunk` est un fragment de message (typiquement un `AIMessageChunk`, portant un morceau de texte dans `.content`) émis dès qu'il est disponible, au niveau du **LLM sous-jacent lui-même** (LangChain relaie le streaming natif d'Ollama token par token).
- `metadata` est un dictionnaire contextuel qui inclut notamment `langgraph_node`, indiquant **quel nœud du graphe** est en train de produire ce chunk au moment précis de l'émission.

C'est ce deuxième élément qui permet le filtre `metadata.get("langgraph_node") == "call_model"` : sans lui, les messages produits — ou les métadonnées internes — du nœud `tools` (qui n'utilise pas le LLM et ne produit donc normalement pas de chunk de ce type) pourraient fuiter vers l'utilisateur. Le filtre est une ceinture de sécurité explicite contre toute fuite de détail d'implémentation interne (comme le texte brut d'un `ToolMessage`) vers le canal destiné à l'utilisateur final.

### 6.8 Tableau des Modes de Défaillance — `orchestrator.py`

| Défaillance | Déclencheur | Comportement actuel | Visible pour l'utilisateur ? |
|---|---|---|---|
| Boucle d'outils infinie | Le modèle redemande toujours un outil, jamais de réponse finale | `GraphRecursionError` levée par LangGraph après `RECURSION_LIMIT` étapes | Oui — message d'erreur clair, capturé dans `stream_chat` |
| Nom d'outil halluciné | Le modèle appelle un outil qui n'existe pas dans `tools_by_name` | `ToolMessage(content="Outil inconnu : ...")` réinjecté ; le modèle peut se corriger au tour suivant | Non directement (traité en interne par la boucle) |
| Exception dans `tool.execute()` (ex. perte de connexion DB pendant `search_knowledge`) | Erreur non gérée dans l'outil lui-même | **Non interceptée** — se propage hors de `call_tools`, hors de `app.astream`, hors de `stream_chat` | Oui, mais de façon dégradée — voir Module 07/08 pour la conséquence exacte sur le flux SSE |
| Appels d'outils multiples demandés par le modèle | Tool calling parallèle | Exécutés séquentiellement (pas de `asyncio.gather`) — latence additive, pas de risque de correction | Non (latence uniquement) |
| `tool_defs` vide (aucun outil enregistré) | `tools` est une liste vide | `llm_with_tools = llm` (pas de `bind_tools` appelé) — le modèle ne pourra jamais demander d'outil | N/A — comportement voulu |

---

### VOCABULAIRE — MODULE 06

| Terme | Définition |
|---|---|
| **state (état d'un graphe)** | Toute l'information que le graphe transporte actuellement — ici, l'historique complet des messages d'une conversation. |
| **reducer** | Une fonction qui prend l'état actuel et un changement proposé, et produit le nouvel état combiné. |
| **super-step** | Une exécution unique d'un nœud dans le modèle d'exécution de type Pregel dont LangGraph s'inspire ; l'unité comptée par `recursion_limit`. |
| **arête conditionnelle (conditional edge)** | Une connexion entre deux nœuds d'un graphe qui n'est empruntée que si une certaine condition est vraie. |
| **récursion (recursion)** | Un processus qui se répète, parfois en rappelant ses propres étapes — ici, la boucle modèle → outil → modèle. |
| **chunk** | Un petit fragment d'une réponse plus grande, envoyé dès qu'il est prêt plutôt que d'attendre l'ensemble. |
| **identité (d'un objet)** | Le fait que deux variables pointent vers le même objet en mémoire, plutôt que vers deux objets distincts qui se ressemblent seulement. |
| **fail-safe (garde-fou)** | Un mécanisme conçu pour transformer une défaillance en un état géré et prévisible, plutôt qu'un crash incontrôlé. |

---

**[ MindOps Field Manual — Module 06 | Page 27 ]**

---

## MODULE 07 : LA PORTE HTTP *(EXPANSION MAJEURE)*

**Fichiers : `app/agent/schemas.py` & `app/agent/router.py`**

### 7.1 Objectif Conceptuel & Architecture

`router.py` est le **composition root** du système : le seul endroit où tous les objets concrets définis dans les Modules 02 à 06 sont enfin assemblés pour une requête HTTP réelle. Le pattern de conception central ici est l'**injection de dépendances** (`Dependency Injection`), fournie nativement par FastAPI via `Depends(...)`.

### 7.2 Code Source Complet — `schemas.py`

```python
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, examples=["conv-1"])
    message: str = Field(min_length=1, examples=["Pourquoi le paiement échoue ?"])
```

### 7.3 Analyse Ligne par Ligne — `schemas.py`

| Ligne | Extrait | Explication |
|---|---|---|
| 4 | `class ChatRequest(BaseModel):` | DTO (Data Transfer Object) Pydantic v2 — décrit et valide automatiquement le corps JSON de la requête entrante. |
| 5 | `conversation_id: str | None = Field(default=None, examples=["conv-1"])` | Type union moderne (`str | None`, syntaxe PEP 604) : le champ est optionnel. Sa valeur par défaut `None` signale « nouvelle conversation » — voir 7.5. `examples=[...]` alimente directement la documentation OpenAPI générée automatiquement par FastAPI (`/docs`). |
| 6 | `message: str = Field(min_length=1, examples=[...])` | `min_length=1` rejette un message vide **avant** même que le code métier ne s'exécute — validation à la frontière du système, exactement là où elle doit avoir lieu (« valider à la frontière, faire confiance en interne »). |

### 7.4 Code Source Complet — `router.py`

```python
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm_client import get_llm_client
from app.agent.memory import checkpointer
from app.agent.orchestrator import build_graph, stream_chat
from app.agent.schemas import ChatRequest
from app.agent.tools.search_knowledge import SearchKnowledgeTool
from app.core.database import get_db
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider

router = APIRouter()


async def _sse_events(app, *, conversation_id: str, message: str) -> AsyncIterator[str]:
    yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"
    async for token in stream_chat(app, conversation_id=conversation_id, user_message=message):
        yield f"event: delta\ndata: {json.dumps({'text': token})}\n\n"
    yield "event: done\ndata: {}\n\n"


@router.post(
    "/chat",
    summary="Discuter avec l'agent",
    description=(
        "Envoie un message à l'agent et streame la réponse en Server-Sent Events. "
        "`conversation_id` (optionnel) permet de poursuivre une conversation existante."
    ),
)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm: BaseChatModel = Depends(get_llm_client),
) -> StreamingResponse:
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    tools = [SearchKnowledgeTool(db=db, provider=provider)]
    app = build_graph(llm, tools, checkpointer)

    return StreamingResponse(
        _sse_events(app, conversation_id=conversation_id, message=payload.message),
        media_type="text/event-stream",
    )
```

### 7.5 Analyse Ligne par Ligne — `router.py`

| Ligne | Extrait | Explication |
|---|---|---|
| 18 | `router = APIRouter()` | Sous-routeur FastAPI, monté par `app/api/router.py` sous le préfixe `/agent` (voir `router.include_router(agent_router, prefix="/agent", tags=["agent"])`) — donc `/chat` devient `/agent/chat` à l'exécution. |
| 21 | `async def _sse_events(app, *, conversation_id: str, message: str) -> AsyncIterator[str]:` | Générateur asynchrone privé (`_` préfixe) — le corps même du flux HTTP renvoyé. |
| 22 | `yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"` | Premier événement SSE, envoyé **avant** tout appel au LLM — le client apprend immédiatement l'identifiant de conversation à réutiliser pour un tour suivant, même si la génération de la réponse prend du temps. |
| 23-24 | `async for token in stream_chat(...): yield f"event: delta\ndata: ..."` | Relaie chaque fragment de texte produit par l'orchestrateur (Module 06) comme un événement SSE `delta` distinct. |
| 25 | `yield "event: done\ndata: {}\n\n"` | Marqueur de fin de flux explicite — signale au client qu'aucun autre événement ne suivra et que la connexion peut être fermée proprement. |
| 28-35 | `@router.post("/chat", summary=..., description=...)` | Les paramètres `summary`/`description` alimentent uniquement la documentation OpenAPI (`/docs`) — zéro effet sur le comportement runtime. |
| 37-41 | Signature de `chat(...)` avec trois `Depends(...)` | Voir 7.6. |
| 42 | `conversation_id = payload.conversation_id or str(uuid.uuid4())` | Motif Python idiomatique « valeur ou valeur par défaut » — `or` court-circuite : si `payload.conversation_id` est `None` **ou** une chaîne vide (`""`), un nouvel UUID est généré. |
| 43 | `tools = [SearchKnowledgeTool(db=db, provider=provider)]` | Construction d'une **nouvelle** instance d'outil, liée à la session `db` de *cette* requête précise (voir Module 03, 3.4). |
| 44 | `app = build_graph(llm, tools, checkpointer)` | Un graphe **neuf** est compilé à chaque requête — mais `checkpointer` est l'objet module-level partagé importé du Module 05, donc l'historique persiste malgré la reconstruction du graphe lui-même. |
| 46-49 | `return StreamingResponse(_sse_events(...), media_type="text/event-stream")` | `StreamingResponse` de FastAPI/Starlette consomme le générateur asynchrone au fur et à mesure, en écrivant chaque `yield` directement sur la connexion HTTP ouverte, sans attendre la fin du générateur. |

### 7.6 DEEP DIVE — L'Injection de Dépendances en Détail

Les trois `Depends(...)` transforment la signature de `chat()` en une déclaration de besoins, pas une construction d'objets :

```python
db: AsyncSession = Depends(get_db),
provider: EmbeddingProvider = Depends(get_embedding_provider),
llm: BaseChatModel = Depends(get_llm_client),
```

FastAPI résout chacune de ces dépendances **avant** d'invoquer le corps de `chat()`, dans l'ordre déclaré, en appelant chaque fonction (`get_db`, `get_embedding_provider`, `get_llm_client`) et en injectant sa valeur de retour. Le bénéfice se révèle entièrement au Module 09 : un test peut dire à FastAPI « quiconque demande `get_llm_client`, donne-lui plutôt mon faux » via `app.dependency_overrides[get_llm_client] = lambda: my_fake` — et rien dans `router.py` ni `orchestrator.py` n'a besoin de changer, ni même de savoir que la substitution a eu lieu.

> **NOTE — CYCLE DE VIE DES DÉPENDANCES.** `get_db` est un générateur (`yield`) — FastAPI l'utilise comme un context manager implicite : la session est ouverte avant l'appel à `chat()`, et fermée automatiquement une fois la fonction terminée (ou, ici, une fois que le générateur `StreamingResponse` sous-jacent a fini d'être consommé). `get_embedding_provider` et `get_llm_client` sont de simples fonctions de retour direct — `get_llm_client` reste en réalité un singleton mis en cache (Module 04), donc son coût de résolution par FastAPI est négligeable après le tout premier appel du processus.

### 7.7 DEEP DIVE — Le Protocole SSE, Précisément

**Server-Sent Events** est un protocole de streaming unidirectionnel construit sur HTTP simple : le serveur écrit des petits blocs de texte commençant par `event:` et `data:`, séparés par une **ligne vide**, et le client les lit au fur et à mesure de leur arrivée plutôt que d'attendre la fermeture de la connexion.

**Anatomie exacte d'un événement, telle qu'émise par ce code :**

```
event: delta
data: {"text": "Le paiement"}

```

Trois éléments non négociables :

1. La ligne `event: <nom>` déclare le type d'événement (ici, un des trois : `start`, `delta`, `done`), que le client peut utiliser pour distinguer les gestionnaires (`EventSource.addEventListener("delta", ...)`).
2. La ligne `data: <payload>` porte la charge utile — toujours sérialisée en JSON ici via `json.dumps(...)`.
3. La **ligne vide finale** (`\n\n`, deux retours à la ligne consécutifs) termine l'événement — c'est le délimiteur que tout parseur SSE conforme utilise pour savoir qu'un événement complet vient d'arriver.

> **NOTE — POURQUOI `json.dumps` N'EST PAS COSMÉTIQUE.** Le texte produit par le modèle de langage peut lui-même contenir des retours à la ligne (une réponse formatée en plusieurs paragraphes, une liste à puces, un bloc de code). Si ce texte était inséré **brut** après `data: `, un retour à la ligne interne casserait la trame SSE : le parseur du client interpréterait la ligne suivante comme un nouveau champ `data:` implicite (ou, pire, comme la ligne vide de fin d'événement s'il s'agissait d'une ligne réellement vide). `json.dumps({'text': token})` échappe systématiquement tout retour à la ligne en `\n` littéral (deux caractères, backslash + n) à l'intérieur d'une chaîne JSON valide sur une seule ligne physique — ce qui garantit que `data: {...}` tient toujours sur une seule ligne, quel que soit le contenu du texte du modèle. Sans cet échappement, un modèle qui répond avec une liste à puces multi-lignes casserait silencieusement le flux SSE pour le client.

### 7.8 DEEP DIVE — Gestion d'Exceptions dans un Générateur Asynchrone : l'État Actuel et le Risque

**Ce qui est géré aujourd'hui :** `stream_chat` (Module 06) intercepte spécifiquement `GraphRecursionError` et transforme cette unique exception connue en un `yield` de texte d'erreur normal, qui continue ensuite vers `_sse_events` comme n'importe quel autre `delta`, jusqu'à l'événement `done` final. Le flux SSE se termine donc **proprement** dans ce cas précis.

**Ce qui n'est pas géré :** ni `stream_chat`, ni `_sse_events`, n'entourent le reste du corps d'un `try/except` généraliste. Si une exception **différente** survient à l'intérieur du graphe — par exemple une perte de connexion à la base de données dans `SearchKnowledgeTool.execute()` (Module 03), ou une erreur réseau vers le serveur Ollama pendant `call_model` (Module 04) — cette exception remonte sans être interceptée à travers :

```
tool.execute()  →  call_tools  →  moteur LangGraph (app.astream)
               →  boucle "async for" de stream_chat (non catchée : ce n'est pas un GraphRecursionError)
               →  boucle "async for" de _sse_events (aucun try/except ici non plus)
               →  StreamingResponse (Starlette)
```

**Conséquence exacte observée côté client :** parce que les en-têtes HTTP (`200 OK`, `Content-Type: text/event-stream`) ont déjà été envoyés **dès le tout premier `yield`** (`event: start`), il est trop tard pour renvoyer un code d'erreur HTTP propre (par exemple un `500`) — le protocole HTTP ne permet pas de changer le code de statut après le début de l'envoi du corps. Starlette termine alors la connexion de façon abrupte : le client reçoit un flux **tronqué**, sans jamais recevoir d'`event: done`, et l'exception est journalisée côté serveur (par le gestionnaire d'exception ASGI par défaut) mais **jamais communiquée au client** de façon structurée. Un client mal préparé pourrait rester bloqué en attente d'un événement qui ne viendra jamais.

> **NOTE — DURCISSEMENT RECOMMANDÉ (non implémenté à ce jour).** Pour fermer ce mode de défaillance, `_sse_events` devrait envelopper sa propre boucle dans un bloc `try/except` généraliste et émettre un quatrième type d'événement, `event: error`, avant de se terminer normalement (ce qui permet toujours d'envoyer un `event: done` final propre) :
>
> ```python
> async def _sse_events(app, *, conversation_id: str, message: str) -> AsyncIterator[str]:
>     yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"
>     try:
>         async for token in stream_chat(app, conversation_id=conversation_id, user_message=message):
>             yield f"event: delta\ndata: {json.dumps({'text': token})}\n\n"
>     except Exception:
>         logger.exception("Échec du flux de chat pour conversation_id=%s", conversation_id)
>         yield f"event: error\ndata: {json.dumps({'message': 'Une erreur interne est survenue.'})}\n\n"
>     finally:
>         yield "event: done\ndata: {}\n\n"
> ```
>
> Le point clé : capturer l'exception **à l'intérieur** du générateur, jamais autour de l'appel qui le consomme (`StreamingResponse` ne peut pas être enveloppée utilement dans un `try/except` côté appelant, puisque le générateur est consommé de façon paresseuse, bien après que `chat()` a déjà retourné). C'est la seule façon d'obtenir une trame SSE finale bien formée plutôt qu'une connexion coupée sans préavis.

---

### VOCABULAIRE — MODULE 07

| Terme | Définition |
|---|---|
| **injection de dépendances (dependency injection)** | Un pattern de conception où une fonction déclare ce dont elle a besoin, et un système extérieur le fournit, plutôt que la fonction ne le construise elle-même. |
| **endpoint** | Une URL précise et une méthode HTTP auxquelles un serveur répond, comme `POST /agent/chat`. |
| **Server-Sent Events (SSE)** | Un protocole permettant à un serveur de pousser un flux de petits messages texte vers un client, sur une connexion HTTP ouverte. |
| **payload** | La donnée réelle transportée dans une requête ou un message, par opposition à ses en-têtes ou métadonnées. |
| **composition root** | L'unique endroit d'une application où les objets concrets sont assemblés à partir d'abstractions. |
| **générateur asynchrone (async generator)** | Une fonction Python `async def` qui utilise `yield` pour produire une séquence de valeurs de façon paresseuse et non bloquante. |

---

**[ MindOps Field Manual — Module 07 | Page 34 ]**

---

## MODULE 08 : UNE QUESTION, DU DÉBUT À LA FIN *(EXPANSION MAJEURE)*

### 8.1 Scénario de Référence

Un utilisateur envoie : *« Pourquoi le paiement échoue ? »* — sans conversation préalable, sans `conversation_id`.

### 8.2 Diagramme de Séquence ASCII Complet

```
UTILISATEUR      ROUTER (FastAPI)      GRAPHE LangGraph      call_model      tools      OLLAMA        CLIENT SSE
    │                    │                     │                  │            │           │               │
    │  POST /agent/chat  │                     │                  │            │           │               │
    │  {message: "..."}  │                     │                  │            │           │               │
    ├───────────────────►│                     │                  │            │           │               │
    │                    │ valide ChatRequest  │                  │            │           │               │
    │                    │ résout 3x Depends() │                  │            │           │               │
    │                    │ (db, provider, llm) │                  │            │           │               │
    │                    │                     │                  │            │           │               │
    │                    │ conversation_id =   │                  │            │           │               │
    │                    │   uuid4()           │                  │            │           │               │
    │                    │ tools = [SearchKnowledgeTool(db, provider)]         │           │               │
    │                    │ app = build_graph(llm, tools, checkpointer)         │           │               │
    │                    │                     │                  │            │           │               │
    │                    │ return StreamingResponse(_sse_events(...))          │           │               │
    │                    ├─────────────────────────────────────────────────────────────────────────────────►
    │                    │                     │                  │            │           │  event: start │
    │                    │                     │                  │            │           │  {conv_id}    │
    │◄─────────────────────────────────────────────────────────────────────────────────────────────────────┤
    │                    │                     │                  │            │           │               │
    │                    │ app.astream(inputs, stream_mode="messages")         │           │               │
    │                    ├────────────────────►│                  │            │           │               │
    │                    │                     │  charge état      │            │           │               │
    │                    │                     │  (checkpointer)   │            │           │               │
    │                    │                     ├─────────────────►│            │           │               │
    │                    │                     │                  │ prépend SystemMessage   │               │
    │                    │                     │                  │ ainvoke(messages)       │               │
    │                    │                     │                  ├────────────────────────►│               │
    │                    │                     │                  │                          │ décide :      │
    │                    │                     │                  │                          │ tool_call     │
    │                    │                     │                  │                          │ search_knowledge│
    │                    │                     │                  │◄─────────────────────────┤               │
    │                    │                     │                  │ (pas de content textuel  │               │
    │                    │                     │                  │  → rien streamé ici)      │               │
    │                    │                     │  {"messages":[AIMessage(tool_calls=[...])]}  │               │
    │                    │                     │◄─────────────────┤            │           │               │
    │                    │                     │  reducer add_messages : append (id neuf)     │               │
    │                    │                     │                  │            │           │               │
    │                    │                     │  route_after_model → "tools" (tool_calls non vide)          │
    │                    │                     ├──────────────────────────────►│           │               │
    │                    │                     │                  │            │ execute(query=...)         │
    │                    │                     │                  │            │  → rag/retriever.search()  │
    │                    │                     │                  │            │  → nearest_chunks (pgvector)│
    │                    │                     │                  │            │◄──────────│               │
    │                    │                     │  {"messages":[ToolMessage(content="[source:...]", tool_call_id)]}
    │                    │                     │◄──────────────────────────────┤           │               │
    │                    │                     │  reducer : append (id neuf)   │           │               │
    │                    │                     │                  │            │           │               │
    │                    │                     │  boucle : add_edge("tools" → "call_model")│               │
    │                    │                     ├─────────────────►│            │           │               │
    │                    │                     │                  │ prépend SystemMessage (à nouveau)       │
    │                    │                     │                  │ ainvoke(messages incl. ToolMessage)     │
    │                    │                     │                  ├────────────────────────►│               │
    │                    │                     │                  │                          │ génère texte  │
    │                    │                     │                  │                          │ TOKEN PAR TOKEN│
    │                    │                     │                  │◄═══════════════════════ (stream) ═══════│
    │                    │                     │  chunk.content="Le", metadata.node="call_model"             │
    │                    │◄════════════════════│◄═════════════════│                          │               │
    │                    ├─────────────────────────────────────────────────────────────────────────────────►│
    │                    │                     │                  │            │           │ event: delta  │
    │◄─────────────────────────────────────────────────────────────────────────────────────────────────────┤ {"text":"Le"}
    │                    │                     │  chunk.content=" paiement", ...                             │
    │                    │◄════════════════════│◄═════════════════│                          │               │
    │                    ├─────────────────────────────────────────────────────────────────────────────────►│
    │◄─────────────────────────────────────────────────────────────────────────────────────────────────────┤ event: delta
    │                    │                     │        ... (un event: delta par fragment de token) ...      │
    │                    │                     │  {"messages":[AIMessage(content="Le paiement échoue...")]}  │
    │                    │                     │◄─────────────────┤            │           │               │
    │                    │                     │  route_after_model → END (tool_calls vide)                 │
    │                    │                     │  fin de app.astream (StopAsyncIteration)                   │
    │                    ├─────────────────────────────────────────────────────────────────────────────────►│
    │                    │                     │                  │            │           │ event: done   │
    │◄─────────────────────────────────────────────────────────────────────────────────────────────────────┤ {}
    │                    │                     │                  │            │           │               │
    │  [connexion HTTP fermée]                 │  checkpointer a déjà persisté tous les messages ci-dessus   │
    │                    │                     │  sous thread_id = conversation_id                          │
```

### 8.3 Trace Textuelle, Étape par Étape

| # | Étape | Détail technique |
|---|---|---|
| 1 | Requête entrante | Le client envoie `POST /agent/chat` avec `{"message": "Pourquoi le paiement échoue ?"}`, sans `conversation_id`. |
| 2 | Validation & injection | FastAPI valide le corps contre `ChatRequest` (Module 07), puis résout les trois `Depends(...)` : une session DB, le fournisseur d'embeddings, le client Ollama mis en cache. |
| 3 | Assemblage | `chat()` génère un nouvel UUID pour `conversation_id`, construit un `SearchKnowledgeTool` lié à la session de *cette* requête, et compile un graphe frais via `build_graph(...)`, câblé au `checkpointer` partagé. |
| 4 | Premier événement | La réponse commence à streamer immédiatement : le client reçoit `event: start` avec le nouvel identifiant de conversation — avant même que le LLM n'ait été interrogé. |
| 5 | Premier appel modèle | À l'intérieur de `stream_chat`, le nœud `call_model` du graphe s'exécute en premier. Il préfixe le prompt système et envoie l'unique message humain à `llama3.1:8b` via Ollama. |
| 6 | Décision de function calling | Le modèle décide qu'il a besoin de faits, et répond par un appel d'outil : `search_knowledge(query="paiement échoue")`, sans texte visible à ce stade — rien n'est donc streamé à l'utilisateur pendant cette étape. |
| 7 | Routage | `route_after_model` détecte un appel d'outil et dirige le graphe vers le nœud `tools`. |
| 8 | Exécution de l'outil | `call_tools` exécute `SearchKnowledgeTool.execute(query=...)`, qui appelle le retriever RAG d'Epic 1, récupère les fragments les plus pertinents, et enveloppe le texte formaté dans un `ToolMessage`. |
| 9 | Retour en boucle | Le graphe reboucle vers `call_model`, cette fois avec la réponse de l'outil incluse dans l'historique des messages. |
| 10 | Réponse finale, en streaming | Le modèle rédige cette fois une vraie réponse en texte clair, en citant la source — et chaque mot est désormais streamé au client sous forme d'`event: delta`, au fur et à mesure de sa génération. |
| 11 | Fin de tour | `route_after_model` ne détecte plus d'appel d'outil ; le graphe atteint `END`. Le flux envoie un `event: done` final et la connexion HTTP se ferme. |
| 12 | Persistance silencieuse | Le `checkpointer` `MemorySaver` a déjà stocké chaque message de cet échange sous le nouveau `conversation_id` — une question de suivi utilisant le même identifiant démarrera donc avec le contexte complet. |

### 8.4 Cas Limites et Variantes du Scénario

| Variante | Ce qui change dans la trace |
|---|---|
| `conversation_id` fourni, correspondant à une conversation existante | L'étape 3 ne génère pas de nouvel UUID ; à l'étape 5, l'état chargé par le checkpointer contient déjà l'historique complet des tours précédents — le nouveau `HumanMessage` est simplement ajouté (reducer `add_messages`, Module 06) à la suite. |
| `conversation_id` fourni mais inconnu du checkpointer | `MemorySaver` ne lève pas d'erreur — un `thread_id` jamais vu se comporte exactement comme une nouvelle conversation (état initial vide). |
| Le modèle répond directement, sans appel d'outil | Les étapes 6 à 9 disparaissent entièrement ; l'étape 5 produit directement la réponse finale en streaming, et le tour se termine dès la première invocation de `call_model`. |
| Le modèle boucle indéfiniment sur des appels d'outils | Après `RECURSION_LIMIT` étapes (Module 06, §6.6), `GraphRecursionError` est levée ; `stream_chat` la convertit en un `event: delta` d'erreur, suivi normalement d'`event: done`. |
| Une exception non prévue survient dans `call_tools` ou `call_model` (ex. panne Ollama, perte de connexion DB) | Aucun `event: done` n'est jamais émis ; la connexion HTTP se termine abruptement après le dernier `event: delta` réussi — voir Module 07, §7.8, pour l'analyse complète et le correctif recommandé. |
| Le modèle demande plusieurs outils dans un seul tour | `call_tools` les exécute séquentiellement (Module 06, §6.5) ; chaque `ToolMessage` résultant est ajouté à l'état avant le retour en boucle vers `call_model`. |

---

**[ MindOps Field Manual — Module 08 | Page 39 ]**

---

## MODULE 09 : TESTER UN AGENT SANS LLM RÉEL *(EXPANSION MAJEURE)*

**Fichiers : `tests/agent/fakes.py`, `tests/agent/test_orchestrator.py`, `tests/agent/test_router.py`, `tests/conftest.py`**

### 9.1 Pourquoi Ne Jamais Appeler un Vrai LLM en Test

Un modèle de langage réel est lent, coûte du temps GPU ou de l'argent, et produit une réponse légèrement différente à chaque exécution — aucune de ces trois propriétés n'est acceptable dans une suite de tests automatisés qui doit être rapide, déterministe, et reproductible en CI. La stratégie retenue n'est **pas** de mocker `ChatOllama` avec une bibliothèque de mocking générique (`unittest.mock`), mais d'écrire un **vrai objet LangChain conforme**, qui implémente réellement l'interface `BaseChatModel` — de sorte que tout le reste du pipeline (liaison d'outils, streaming, gestion des `tool_calls`) s'exécute sans aucune branche de code spécifique aux tests.

### 9.2 Le Pattern « Scripted LLM »

**Code source complet — `tests/agent/fakes.py` :**

```python
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, PrivateAttr

from app.agent.tools.base import Tool


class ScriptedChatModel(BaseChatModel):
    """LLM factice qui rejoue une liste de réponses prédéfinies, un appel à la fois."""

    responses: list[AIMessage]
    _call_count: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        index = min(self._call_count, len(self.responses) - 1)
        self._call_count += 1
        # Nouvel id a chaque appel : le reducer `add_messages` de LangGraph fusionne par id,
        # donc rejouer le meme objet ecraserait le message precedent au lieu d'en ajouter un.
        template = self.responses[index]
        message = AIMessage(content=template.content, tool_calls=template.tool_calls)
        return ChatResult(generations=[ChatGeneration(message=message)])


class EchoArgs(BaseModel):
    text: str


class EchoTool(Tool):
    """Outil factice pour tester la boucle agentique sans dépendre du RAG/DB."""

    name = "echo"
    description = "Renvoie le texte reçu, préfixé, pour vérifier que l'outil a été appelé."
    args_schema = EchoArgs

    def __init__(self):
        self.calls: list[dict] = []

    async def execute(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return f"echo: {kwargs.get('text', '')}"
```

### 9.3 Analyse Ligne par Ligne — `ScriptedChatModel`

| Ligne | Extrait | Explication |
|---|---|---|
| 12 | `class ScriptedChatModel(BaseChatModel):` | Héritage **réel** de la classe de base LangChain — pas une classe maison qui « ressemble » à un LLM. `BaseChatModel` est lui-même un modèle Pydantic v2, donc `ScriptedChatModel` hérite de toute la mécanique de validation Pydantic. |
| 15 | `responses: list[AIMessage]` | Champ Pydantic **public** — apparaît dans le schéma du modèle, doit être fourni à la construction (`ScriptedChatModel(responses=[...])`), et est validé comme une vraie liste de `AIMessage`. |
| 16 | `_call_count: int = PrivateAttr(default=0)` | Voir 9.4 — attribut **privé** Pydantic v2, pas un champ de schéma. |
| 18-20 | `@property def _llm_type(self) -> str: return "scripted-fake"` | `_llm_type` est une méthode/propriété **abstraite** de `BaseChatModel` — sans cette implémentation, Python refuserait d'instancier la classe (même mécanisme `ABC`/`abstractmethod` que le Module 02, appliqué ici en interne par LangChain). Elle sert d'identifiant de type pour le logging et le traçage LangChain (LangSmith, callbacks). |
| 22-23 | `def bind_tools(self, tools, **kwargs) -> "ScriptedChatModel": return self` | Voir 9.5. |
| 25-31 | Signature de `_generate(...)` | Voir 9.6 — signature qui **doit** correspondre exactement à celle attendue par `BaseChatModel` pour que le mécanisme d'appel interne de LangChain la trouve et l'invoque correctement. |
| 32 | `index = min(self._call_count, len(self.responses) - 1)` | Clamping explicite : au-delà du nombre de réponses scriptées, l'**dernière** réponse de la liste est rejouée indéfiniment — c'est ce mécanisme précis qui permet de simuler « le modèle ne s'arrête jamais de demander l'outil » pour le test de récursion (9.9, Test 3), avec une seule entrée dans `responses`. |
| 33 | `self._call_count += 1` | Mutation de l'état privé — chaque appel réel à `_generate` avance le curseur d'un cran, peu importe combien de fois le graphe rappelle le modèle au cours d'une même conversation. |
| 34-35 | *(commentaire)* | Documente explicitement, dans le code lui-même, la leçon tirée du bug du §9.7 — un choix éditorial délibéré pour qu'un futur contributeur ne réintroduise pas l'erreur. |
| 36-37 | `template = self.responses[index]` / `message = AIMessage(content=template.content, tool_calls=template.tool_calls)` | **Reconstruction complète** d'un nouvel objet `AIMessage`, en ne recopiant que les champs de contenu (`content`, `tool_calls`) du gabarit — jamais de `template.id` recopié, jamais le gabarit lui-même retourné. C'est la ligne qui corrige le bug historique. |
| 38 | `return ChatResult(generations=[ChatGeneration(message=message)])` | Format de retour exact attendu par `BaseChatModel._generate` : une liste de `ChatGeneration`, chacune enveloppant un message — même s'il n'y a ici qu'une seule génération (pas de sampling multiple `n>1`). |

### 9.4 Pourquoi `PrivateAttr` et Pas un Champ Pydantic Normal

`BaseChatModel` (et donc `ScriptedChatModel`) est un modèle **Pydantic v2**. Un champ Pydantic ordinaire (`_call_count: int = 0`) ferait partie du schéma public du modèle — sérialisable, validable, exposable — ce qui n'a aucun sens pour un compteur d'appels interne purement mutable, qui ne doit **jamais** être fourni par l'appelant ni apparaître dans une sérialisation. `PrivateAttr(default=0)` déclare explicitement à Pydantic v2 : « ceci est un attribut d'instance mutable, hors du schéma de validation, avec une valeur initiale de 0 » — le mécanisme Pydantic idiomatique pour de l'état mutable interne sur un modèle par ailleurs destiné à être largement immuable/validé.

### 9.5 Pourquoi `bind_tools` Renvoie Simplement `self`

Dans le vrai `ChatOllama` (Module 04), `bind_tools(tool_defs)` fait un travail réel : il attache les définitions JSON Schema des outils à la requête envoyée à Ollama, pour que le modèle réel puisse décider d'appeler une fonction. `ScriptedChatModel` n'a besoin d'aucune de ces définitions — il rejoue un script écrit à l'avance, indépendamment de ce que l'orchestrateur (Module 06) déclare comme outils disponibles. Renvoyer `self` (plutôt que lever `NotImplementedError`, ou ignorer l'appel silencieusement d'une autre façon) permet au code de production **inchangé** — `llm_with_tools = llm.bind_tools(tool_defs) if tool_defs else llm` — de fonctionner exactement de la même manière avec le faux et avec le vrai modèle, sans branche conditionnelle spécifique aux tests dans `orchestrator.py`.

### 9.6 DEEP DIVE — Comment `ainvoke()` Retrouve une Méthode Synchrone `_generate`

Un détail non trivial de LangChain mérite d'être explicité : `orchestrator.py` appelle `await llm_with_tools.ainvoke(messages)` — une méthode **asynchrone** — mais `ScriptedChatModel` ne définit que `_generate`, une méthode **synchrone** (pas de `async def`, pas de `_agenerate` surchargée).

Ceci fonctionne car `BaseChatModel` fournit une implémentation par défaut de `_agenerate` (utilisée en interne par `.ainvoke()`) qui, en l'absence de surcharge asynchrone explicite dans la sous-classe, **délègue automatiquement vers la version synchrone** `_generate`, exécutée dans un thread séparé du pool d'exécuteurs par défaut de l'event loop asyncio (`loop.run_in_executor`), afin de ne jamais bloquer la boucle d'événements principale. Cette délégation est totalement transparente pour `orchestrator.py`, qui n'a besoin de connaître ni l'existence de `_generate`, ni ce mécanisme de délégation interne — il appelle `.ainvoke()` sur n'importe quel `BaseChatModel` conforme, faux ou réel, de façon identique.

### 9.7 POST-MORTEM DU BUG D'IDENTITÉ (« Identity Merging »)

> **INCIDENT RÉEL RENCONTRÉ PENDANT LA CONSTRUCTION DE CE MODULE**

**Symptôme observé.** La toute première version de `ScriptedChatModel` réutilisait littéralement le même objet Python `AIMessage` à chaque fois que le script était à court de nouvelles réponses (c'est-à-dire qu'elle renvoyait directement `template` plutôt qu'un nouvel `AIMessage(content=template.content, tool_calls=template.tool_calls)`). Un test conçu pour vérifier que la boucle s'arrête bien après `RECURSION_LIMIT` étapes lorsqu'un modèle mal élevé redemande sans cesse un outil (le test devenu `test_agent_stops_when_llm_never_stops_calling_tools`) **s'arrêtait après un seul appel d'outil, silencieusement, sans aucune erreur, sans que `GraphRecursionError` ne soit jamais levée.**

**Cause racine, étape par étape :**

1. À la première invocation de `_generate`, le gabarit unique (`always_calls_tool`, un `AIMessage` avec `tool_calls=[...]` et sans `id` explicite) est retourné **directement**, sans reconstruction.
2. Le reducer `add_messages` (Module 06, §6.4) reçoit ce message avec `id=None`. Selon l'algorithme documenté, il lui assigne un `id` fraîchement généré — mais cette assignation **mute l'objet Python lui-même** (`message.id = str(uuid.uuid4())`), et cet objet est précisément l'unique instance stockée dans `self.responses[0]` du faux modèle. Après ce premier appel, le gabarit source porte désormais un `id` non nul, de façon permanente, pour toute la durée de vie de l'objet `ScriptedChatModel`.
3. Le message est ajouté (append) en fin de liste d'état — comportement normal, puisque son `id` était nouveau à ce moment précis. `route_after_model` voit un `AIMessage` avec des `tool_calls`, et route vers `tools`. `call_tools` s'exécute, produit un `ToolMessage` (id neuf, distinct), qui est ajouté **après** l'`AIMessage` dans la liste d'état.
4. Le graphe reboucle vers `call_model`, qui invoque `_generate` une seconde fois. Avec un seul gabarit disponible, `index = min(1, 0) = 0` : **le même objet Python** (`self.responses[0]`, désormais muni d'un `id` non nul depuis l'étape 2) est retourné une seconde fois, à l'identique.
5. Le reducer `add_messages` reçoit ce message : son `id` **existe déjà** dans l'état (assigné à l'étape 2). Selon la règle « même id → remplacement à la position d'origine », le reducer **écrase** l'`AIMessage` déjà présent à sa position d'origine dans la liste — **il ne l'ajoute pas en fin de liste**. Le `ToolMessage` produit à l'étape 3, lui, reste inchangé et demeure le **dernier élément** de la liste.
6. `route_after_model` inspecte `state["messages"][-1]` — qui est toujours ce `ToolMessage`, pas le nouvel `AIMessage` (invisible en fin de liste, puisqu'il a été fusionné à une position antérieure). `isinstance(last_message, AIMessage)` est donc **`False`**. La fonction de routage renvoie `END`, croyant la conversation terminée, alors que le modèle factice tentait en réalité de redemander l'outil indéfiniment.

**Résultat observable :** le graphe se termine après une seule itération, sans erreur, avec un résultat qui *semble* correct en apparence (aucune exception, un résultat renvoyé) — le pire type de défaillance : silencieuse et plausible.

**Le correctif — une seule ligne de logique, capitale :**

```python
# AVANT (bogué) — retourne l'objet gabarit lui-même :
def _generate(self, messages, stop=None, run_manager=None, **kwargs):
    index = min(self._call_count, len(self.responses) - 1)
    self._call_count += 1
    message = self.responses[index]                      # <-- même objet à chaque replay
    return ChatResult(generations=[ChatGeneration(message=message)])

# APRÈS (correct) — reconstruit un objet frais à chaque appel :
def _generate(self, messages, stop=None, run_manager=None, **kwargs):
    index = min(self._call_count, len(self.responses) - 1)
    self._call_count += 1
    template = self.responses[index]
    message = AIMessage(content=template.content, tool_calls=template.tool_calls)  # id=None -> nouveau id généré par le reducer, garanti différent
    return ChatResult(generations=[ChatGeneration(message=message)])
```

En ne recopiant que `content` et `tool_calls` — jamais `template.id`, et jamais `template` lui-même — chaque appel produit un objet dont l'`id` est laissé à `None`, ce qui garantit que le reducer lui assignera un `id` **fraîchement généré et unique** à chaque fusion, indépendamment du nombre de fois où le même gabarit textuel est rejoué.

**La leçon générale, au-delà de ce fichier précis :** pour tout système construit autour d'un reducer qui fusionne par **identité** (`id`) plutôt que par égalité de contenu, il ne faut **jamais** supposer que « même contenu » implique « même objet réutilisable sans risque ». Deux appels qui doivent produire deux entrées distinctes dans l'historique doivent toujours produire deux objets distincts, même quand leur contenu textuel est rigoureusement identique.

### 9.8 Infrastructure de Test Partagée

**`tests/conftest.py` — la fixture `db_session` :**

```python
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as connection:
        await connection.begin()
        # join_transaction_mode="create_savepoint" : un session.commit() fait par le
        # code teste ne cloture qu'un SAVEPOINT, jamais la transaction externe ci-dessous
        # -> connection.rollback() annule tout, meme si le code a appele commit().
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()
```

Cette fixture résout un problème classique des tests d'intégration avec base de données réelle : le code testé (ici, indirectement, `SearchKnowledgeTool` via `rag/retriever.search`) peut légitimement appeler `session.commit()` en cours d'exécution. `join_transaction_mode="create_savepoint"` fait en sorte qu'un tel `commit()` ne clôture qu'un **SAVEPOINT** imbriqué dans la transaction externe ouverte par la fixture — jamais la transaction externe elle-même. Le `connection.rollback()` final annule donc **tout**, y compris les données que le code testé croyait avoir validées de façon permanente. Chaque test démarre ainsi sur une base de données strictement vierge, sans dépendre de nettoyage manuel entre tests.

**`tests/rag/fakes.py` — `FakeEmbeddingProvider` :**

```python
class FakeEmbeddingProvider(EmbeddingProvider):
    dimension = 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._fake_vector(text) for text in texts]

    def _fake_vector(self, text: str) -> list[float]:
        values: list[float] = []
        block = text.encode()
        while len(values) < self.dimension:
            block = hashlib.sha256(block).digest()
            values.extend(byte / 255 for byte in block)
        return values[: self.dimension]
```

Plutôt que de charger un vrai modèle `sentence-transformers` (lent, lourd, non déterministe à l'initialisation), ce faux fournisseur dérive un vecteur **déterministe** de 384 dimensions (alignées sur la colonne `chunks.embedding Vector(384)` en production) à partir d'un hachage SHA-256 répété du texte d'entrée. Le déterminisme du hachage garantit que le même texte produit toujours le même vecteur — condition nécessaire pour que les assertions de test sur la pertinence de recherche restent stables d'une exécution à l'autre.

### 9.9 Les Quatre Cas de Test Fondamentaux

#### Unit Test 1 — Réponse Directe (aucun outil appelé)

```python
async def test_agent_answers_directly_without_tool_call(echo_tool: EchoTool):
    llm = ScriptedChatModel(responses=[AIMessage(content="Pas besoin d'outil ici.")])
    app = build_graph(llm, [echo_tool], MemorySaver())

    result = await app.ainvoke(
        {"messages": [("user", "bonjour")]},
        config={"configurable": {"thread_id": "test-2"}},
    )

    assert echo_tool.calls == []
    assert result["messages"][-1].content == "Pas besoin d'outil ici."
```

**Ce que ce test vérifie précisément :** avec une seule réponse scriptée sans `tool_calls`, `route_after_model` doit atteindre `END` dès le premier passage dans `call_model` — le graphe ne doit jamais visiter le nœud `tools`. L'assertion `echo_tool.calls == []` est la vérification la plus directe possible : elle inspecte l'état mutable interne du faux outil pour prouver son non-appel, plutôt que de déduire cette absence d'appel indirectement.

#### Unit Test 2 — Boucle d'Appel d'Outil (le modèle demande un outil, puis conclut)

```python
async def test_agent_calls_tool_then_returns_final_answer(echo_tool: EchoTool):
    llm = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "echo", "args": {"text": "bonjour"}, "id": "call-1"}],
            ),
            AIMessage(content="Réponse finale basée sur l'outil."),
        ]
    )
    app = build_graph(llm, [echo_tool], MemorySaver())

    result = await app.ainvoke(
        {"messages": [("user", "dis bonjour")]},
        config={"configurable": {"thread_id": "test-1"}},
    )

    assert echo_tool.calls == [{"text": "bonjour"}]
    assert result["messages"][-1].content == "Réponse finale basée sur l'outil."
```

**Ce que ce test vérifie précisément :** le cycle complet `call_model → tools → call_model → END`. Deux réponses scriptées, consommées dans l'ordre exact grâce au compteur `_call_count` (§9.3) : la première force le passage par `tools`, la seconde clôt la boucle. `echo_tool.calls == [{"text": "bonjour"}]` prouve que l'outil a été invoké avec **exactement** les arguments transmis par le modèle dans `call["args"]`, confirmant que `call_tools` (Module 06) fait bien `await tool.execute(**call["args"])` sans altérer les arguments en chemin. Ce test aurait été précisément celui qui **échouait silencieusement** (sans lever d'exception, mais avec une assertion finale fausse) si le bug d'identité du §9.7 n'avait pas été corrigé — la seconde réponse n'aurait alors jamais été consommée, et `result["messages"][-1].content` serait resté vide (`""`, le contenu de la première réponse) plutôt que d'afficher la réponse finale attendue.

*(Test complémentaire, non listé dans les quatre cas fondamentaux mais présent dans la suite : `test_agent_remembers_history_across_turns`, qui prouve qu'un `thread_id` réutilisé sur un second `app.ainvoke()` retrouve l'historique du premier tour, validant le comportement de persistance du Module 05 en conditions réelles de reducer.)*

#### Unit Test 3 — Limite Maximale de Récursion Atteinte (simulation d'appel d'outil infini)

```python
async def test_agent_stops_when_llm_never_stops_calling_tools(echo_tool: EchoTool):
    always_calls_tool = AIMessage(
        content="", tool_calls=[{"name": "echo", "args": {"text": "boucle"}, "id": "call-x"}]
    )
    llm = ScriptedChatModel(responses=[always_calls_tool])
    app = build_graph(llm, [echo_tool], MemorySaver())

    with pytest.raises(GraphRecursionError):
        await app.ainvoke(
            {"messages": [("user", "boucle infinie")]},
            config={"configurable": {"thread_id": "test-4"}, "recursion_limit": 6},
        )
```

**Ce que ce test vérifie précisément :** avec une **unique** réponse scriptée qui redemande systématiquement le même outil (`always_calls_tool`), le clamping `index = min(self._call_count, len(self.responses) - 1)` (§9.3) rejoue cette même réponse à l'infini — chaque fois reconstruite en un objet frais (grâce au correctif du §9.7), donc chaque fois correctement ajoutée en fin de liste par le reducer. Le graphe ne peut donc **jamais** converger naturellement vers `END`. `recursion_limit: 6` (au lieu du défaut `RECURSION_LIMIT = 10`) est délibérément réduit pour que le test échoue rapidement — 3 cycles complets `call_model`/`tools` (6 super-steps) au lieu de 5 — sans ralentir la suite de tests. `pytest.raises(GraphRecursionError)` est l'assertion elle-même : ce test **doit** lever cette exception précise pour être considéré comme réussi ; toute autre issue (fin normale, timeout, une autre exception) constitue un échec du test.

> **NOTE — CE QUE CE TEST NE PEUT PAS DÉTECTER SANS LE CORRECTIF DU §9.7.** Avant la correction du bug d'identité, ce test exact ne levait jamais `GraphRecursionError` — il se terminait normalement après une seule itération, produisant une fausse impression de succès de la garde de sécurité alors que le mécanisme de récursion n'était en réalité jamais exercé. Un test de garde de sécurité qui « passe » sans jamais avoir déclenché la garde qu'il prétend vérifier est un piège classique : toujours confirmer, au moins une fois pendant le développement, qu'un test négatif (`pytest.raises(...)`) échoue bien lorsque le comportement attendu est délibérément cassé.

#### Unit Test 4 — Validation du Flux SSE via un Client de Test HTTP Asynchrone

```python
async def _parse_sse_deltas(text: str) -> str:
    deltas = []
    for block in text.split("\n\n"):
        if block.startswith("event: delta"):
            data_line = next(line for line in block.splitlines() if line.startswith("data: "))
            deltas.append(json.loads(data_line[len("data: ") :])["text"])
    return "".join(deltas)


async def test_chat_answers_directly_without_tool_call():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        llm = ScriptedChatModel(responses=[AIMessage(content="Bonjour !")])
        _override_llm(llm)

        response = await client.post("/agent/chat", json={"message": "salut"})

        assert response.status_code == 200
        full_text = await _parse_sse_deltas(response.text)
        assert full_text == "Bonjour !"
```

**Ce que ce test vérifie précisément :** l'ensemble de la pile HTTP réelle — validation Pydantic (`ChatRequest`), résolution des dépendances FastAPI, exécution complète du graphe LangGraph, formatage SSE — de bout en bout, en passant réellement par une requête HTTP simulée plutôt que par un appel direct de fonction Python.

> **NOTE TERMINOLOGIQUE.** Le code utilise `httpx.AsyncClient` avec un `ASGITransport(app=app)`, et non `fastapi.testclient.TestClient` au sens strict. C'est l'équivalent **natif-asynchrone** du `TestClient` historique de FastAPI (qui repose lui-même sur `httpx` en interne, mais expose une API synchrone construite sur un event loop dédié). Puisque `db_session` (§9.8) et l'ensemble de la suite de tests fonctionnent déjà en mode asynchrone natif (`pytest-asyncio`, `asyncio_mode = "auto"` dans `pyproject.toml`), utiliser directement `AsyncClient` + `ASGITransport` évite tout va-et-vient entre code synchrone et asynchrone, et permet de partager la même boucle d'événements que les fixtures de base de données — un choix d'ingénierie plus rigoureux que le `TestClient` synchrone pour tester spécifiquement un endpoint de **streaming**.

`_parse_sse_deltas` reconstruit le texte complet de la réponse en rejouant manuellement le protocole SSE côté test : découpage sur la ligne vide (`\n\n`, le délimiteur d'événement exact du Module 07, §7.7), filtrage des seuls blocs `event: delta`, extraction de la ligne `data: ...`, désérialisation JSON, puis concaténation de tous les fragments `text`. Ce parseur de test est volontairement écrit à la main plutôt que de dépendre d'une bibliothèque cliente SSE, afin de vérifier que le **format exact** produit par `_sse_events` (Module 07) reste conforme au contrat attendu — un changement accidentel de format (par exemple, oublier la deuxième ligne vide) ferait échouer ce test immédiatement.

Le test frère, `test_chat_cites_knowledge_base_via_search_knowledge_tool`, suit exactement le même schéma mais ingère d'abord un document réel via `POST /rag/ingest` (avec les dépendances `get_db` et `get_embedding_provider` substituées par `db_session` et `FakeEmbeddingProvider`, §9.8), scripte une réponse qui déclenche `search_knowledge`, et vérifie que le texte final streamé correspond à la seconde réponse scriptée — validant que le chemin complet **HTTP → orchestrateur → outil → RAG → LLM → SSE** fonctionne de bout en bout sans jamais toucher un vrai modèle de langage ni un vrai modèle d'embeddings.

**La substitution de dépendances qui rend tout cela possible :**

```python
def _override_llm(llm: ScriptedChatModel) -> None:
    app.dependency_overrides[get_llm_client] = lambda: llm
```

```python
@pytest.fixture(autouse=True)
def _override_dependencies(db_session: AsyncSession):
    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_embedding_provider] = FakeEmbeddingProvider
    yield
    app.dependency_overrides.clear()
```

`app.dependency_overrides` est un dictionnaire maintenu par FastAPI lui-même : le mapper depuis la fonction de dépendance originale (`get_llm_client`, `get_db`, `get_embedding_provider`) vers un remplaçant est la **seule** modification nécessaire pour que `router.py` et `orchestrator.py` s'exécutent, sans une seule ligne changée, contre des doublures de test complètes. La fixture `autouse=True` garantit que ces substitutions sont actives pour **tous** les tests du module, et le `yield` suivi de `app.dependency_overrides.clear()` garantit qu'aucune substitution ne fuit vers un test d'un autre module qui importerait la même instance globale `app` — un oubli fréquent qui produirait des échecs de test dépendants de l'ordre d'exécution.

---

### VOCABULAIRE — MODULE 09

| Terme | Définition |
|---|---|
| **fake / mock (doublure de test)** | Un remplaçant simplifié d'un composant réel, trop lent, coûteux ou imprévisible pour être utilisé directement en test. |
| **override (substitution de dépendance)** | Remplacer temporairement ce qu'une portion de code reçoit, généralement pour la durée d'un seul test. |
| **identité (d'un objet)** | Le fait que deux variables pointent vers exactement le même objet en mémoire, et non vers deux objets distincts qui se ressemblent seulement. |
| **PrivateAttr** | Mécanisme Pydantic v2 pour déclarer un attribut d'instance mutable qui n'appartient pas au schéma public/validé du modèle. |
| **SAVEPOINT** | Un point de restauration imbriqué à l'intérieur d'une transaction SQL, permettant d'annuler une sous-partie des opérations sans annuler la transaction englobante. |
| **ASGI Transport** | Mécanisme `httpx` qui invoque une application ASGI (comme FastAPI) directement en mémoire, sans passer par un vrai socket réseau — utilisé pour des tests HTTP rapides et fiables. |
| **régression silencieuse** | Un défaut qui ne produit ni erreur ni crash visible, mais un résultat incorrect qui peut passer inaperçu sans assertion précise. |

---

**[ MindOps Field Manual — Module 09 | Page 52 ]**

---

## MODULE 10 : CE QUI VIENT ENSUITE — EPIC 4

### 10.1 Le Prochain Palier de Risque

Aujourd'hui, le seul outil que l'agent peut appeler est **en lecture seule** : `search_knowledge` ne modifie jamais rien, donc il s'exécute toujours immédiatement, sans validation humaine. Epic 4 introduit le premier outil qui **agit dans le monde** — l'envoi d'un email — et avec lui, le besoin qu'un humain approuve ou rejette une action sensible avant qu'elle ne s'exécute réellement.

### 10.2 Pourquoi `interrupt` de LangGraph Est le Candidat Naturel

LangGraph permet de marquer un nœud comme **interruptible** : l'exécution du graphe s'arrête juste avant (ou après) ce nœud, rend la main au code appelant, et attend une décision externe — approuver ou rejeter — avant de reprendre, via un objet `Command(resume=...)`, exactement là où elle s'était arrêtée.

C'est précisément le pattern de gating déjà envisagé dans le backlog Epic 4 (`ActionProposal`, statut `pending`, `POST /gating/{id}/decide`) : un outil sensible comme `send_email` pourrait devenir un nœud avec `interrupt_before=["send_email"]`, et la validation humaine reprendrait le graphe exactement là où il s'est arrêté — sans qu'il soit nécessaire d'écrire à la main une file d'attente et un mécanisme de sondage (`polling`).

### 10.3 Ce Que Cela Change, et Ce Que Cela Ne Change Pas

| Aspect | Aujourd'hui (Epic 3) | Demain (Epic 4, anticipé) |
|---|---|---|
| Outils enregistrés | 1 (`search_knowledge`, lecture seule) | + `send_email` (effet de bord réel) |
| Validation humaine | Aucune — inutile pour un outil en lecture seule | Requise avant l'exécution d'un outil sensible |
| Mécanisme d'attente | Aucun | `interrupt_before` sur le nœud sensible, reprise via `Command(resume=...)` |
| Contrat externe `POST /agent/chat` | Streaming SSE simple | Potentiellement enrichi d'un événement `event: pending_approval` |
| Fichiers impactés | — | `orchestrator.py` (nouveau nœud + `interrupt_before`), un nouveau module `gating/` |
| Fichiers **non** impactés | — | `tools/base.py` (le contrat `Tool` ne change pas), `llm_client.py`, `memory.py` |

> **NOTE — CONTINUITÉ ARCHITECTURALE.** Le contrat externe (`POST /agent/chat`) ne change pas fondamentalement de forme, seule l'implémentation interne d'`orchestrator.py` évoluerait. C'est exactement la promesse de l'architecture en couches posée dès le Module 01 : le coût d'apprentissage de LangGraph, payé maintenant, est conçu pour être remboursé au moment précis où le gating devient un besoin réel plutôt qu'une anticipation.

---

**[ MindOps Field Manual — Module 10 | Page 54 ]**

---

## § GLOSSAIRE COMPLET — DE A À Z

| Terme | Définition |
|---|---|
| **ABC (Abstract Base Class)** | Mécanisme Python empêchant l'instanciation directe d'une classe, forçant le passage par une sous-classe concrète. |
| **arête (edge)** | Dans un graphe, une flèche ou connexion reliant un nœud à un autre. |
| **arête conditionnelle (conditional edge)** | Une connexion entre deux étapes d'un graphe qui n'est suivie que si une condition donnée est vraie. |
| **ASGI Transport** | Mécanisme permettant d'invoquer une application ASGI directement en mémoire pour des tests HTTP, sans socket réseau réel. |
| **checkpoint** | Un instantané sauvegardé de l'état d'un programme à un instant donné, rechargeable plus tard. |
| **checkpointer** | Le composant LangGraph responsable de sauvegarder et recharger l'état d'un graphe entre invocations. |
| **chunk** | Un petit fragment d'une réponse ou d'un fichier plus grand, traité ou envoyé seul plutôt que d'un bloc. |
| **classe abstraite** | Une classe qui ne peut être instanciée directement — elle n'existe que pour être étendue. |
| **ClassVar** | Annotation de type indiquant qu'un attribut est partagé au niveau de la classe, pas recréé par instance. |
| **composition root** | L'unique endroit d'une application où les objets concrets sont assemblés à partir d'abstractions. |
| **décorateur (decorator)** | Un marqueur `@` placé au-dessus d'une fonction, qui modifie son comportement sans réécrire son corps. |
| **dependency injection (injection de dépendances)** | Un pattern où une fonction déclare ce dont elle a besoin, et un système extérieur le fournit. |
| **déterministe** | Qui produit toujours la même sortie pour la même entrée, sans aléa. |
| **embedding** | Une liste de nombres représentant le sens d'un texte, utilisée pour comparer deux textes entre eux. |
| **endpoint** | Une URL précise et une méthode HTTP auxquelles un serveur répond. |
| **fail fast** | Principe de conception : détecter et signaler une erreur le plus tôt possible. |
| **fake / mock (doublure de test)** | Un remplaçant simplifié utilisé en test, à la place d'un composant réel trop lent, coûteux ou imprévisible. |
| **générateur asynchrone (async generator)** | Une fonction `async def` utilisant `yield` pour produire une séquence de valeurs de façon paresseuse. |
| **graphe (dans ce contexte)** | Une structure de petit nombre d'étapes (nœuds) reliées par des flèches (arêtes), utilisée pour modéliser une boucle de décision. |
| **identité (d'un objet)** | Le fait que deux variables pointent vers exactement le même objet en mémoire, et non vers deux objets seulement égaux en valeur. |
| **interface** | Une forme ou un contrat défini que différentes portions de code acceptent de suivre, sans connaître les détails internes les unes des autres. |
| **interrupt (LangGraph)** | Une pause intégrée à un graphe, où l'exécution s'arrête avant ou après un nœud et attend une décision externe avant de continuer. |
| **keyword-only argument** | Un paramètre de fonction qui ne peut être passé que par son nom, jamais par position. |
| **méthode abstraite** | Une méthode déclarée dans une classe abstraite sans code réel ; chaque sous-classe doit écrire sa propre version. |
| **mémoïsation (memoization)** | Technique de mise en cache du résultat d'un appel de fonction pour éviter de le recalculer. |
| **nœud (node)** | Une étape unique de travail à l'intérieur d'un graphe. |
| **orchestrateur** | La partie d'un programme qui décide l'ordre d'exécution des autres parties du système. |
| **Open/Closed Principle** | Principe de conception : le code doit être ouvert à l'extension mais fermé à la modification. |
| **override (substitution de dépendance)** | Remplacer temporairement ce qu'un morceau de code reçoit, le plus souvent pour la durée d'un test. |
| **payload** | La donnée réelle transportée dans une requête ou un message, hors en-têtes et métadonnées. |
| **per-request state (état par requête)** | Une information devant être créée fraîche pour chaque requête entrante, jamais partagée entre requêtes. |
| **persistance** | La capacité d'une donnée à rester disponible après l'arrêt du programme qui l'a créée. |
| **Ports & Adapters** | Pattern architectural où le cœur métier définit un « port » que des adaptateurs concrets viennent implémenter. |
| **PrivateAttr** | Mécanisme Pydantic v2 pour un attribut d'instance mutable hors du schéma public/validé du modèle. |
| **récursion (recursion)** | Un processus qui se répète en rappelant ses propres étapes antérieures. |
| **reducer** | Une fonction qui prend l'état actuel et un changement proposé, et produit le nouvel état combiné. |
| **régression silencieuse** | Un défaut qui ne produit ni erreur ni crash visible, mais un résultat incorrect facile à manquer. |
| **schéma (schema)** | Une description précise de la forme attendue d'une donnée — quels champs existent, quel type a chacun. |
| **session (base de données)** | Une connexion temporaire à une base de données, ouverte pour la durée d'une requête. |
| **Server-Sent Events (SSE)** | Un protocole permettant à un serveur de pousser un flux de petits messages texte à un client, sur une connexion HTTP ouverte. |
| **singleton** | Un objet créé une seule fois puis réutilisé partout où il est nécessaire. |
| **sous-classe** | Une nouvelle classe construite sur une classe existante, héritant de sa forme et complétant des détails. |
| **state (état de graphe)** | Toute l'information qu'un graphe transporte à mesure qu'il passe d'un nœud à l'autre. |
| **super-step** | Une exécution unique d'un nœud dans le modèle d'exécution de type Pregel — l'unité comptée par `recursion_limit`. |
| **thread (au sens LangGraph)** | Simplement « une conversation en cours », identifiée par un ID — sans rapport avec un thread d'exécution informatique. |
| **tool (outil)** | Une petite fonction qu'un modèle IA est autorisé à appeler, décrite par un nom, une description, et des arguments attendus. |
| **valider (validate)** | Vérifier qu'une donnée correspond réellement à son schéma attendu avant utilisation. |

---

**[ MindOps Field Manual — Glossaire | Page 58 ]**

---

<div align="center">

**MindOps — Orchestrator Field Manual · Édition Étendue v2.0**
**Documentation Epic 3 · Usage interne**

</div>
