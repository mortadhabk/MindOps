# Modèles et ingestion (US-101, US-102, US-103)

Ce document décrit le code réellement écrit pour `app/rag/models.py` et `app/rag/ingestion.py`. Il suppose lu le [guide RAG](00-guide-debutant-rag.md) et la [spec du modèle local](01-modele-local-minilm.md).

## `app/rag/models.py` (US-101)

```python
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.rag.embeddings.local import LocalMiniLMEmbeddingProvider


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str]
    content: Mapped[str]
    status: Mapped[str] = mapped_column(default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    text: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(LocalMiniLMEmbeddingProvider.dimension))

    document: Mapped["Document"] = relationship(back_populates="chunks")
```

### Choix expliqués

- **`status: Mapped[str] = mapped_column(default="pending")`** : trois valeurs possibles au fil du cycle de vie — `pending` (document créé, chunking/embedding pas encore tenté), `complete` (tous les chunks embeddés et stockés), `partial` (l'appel au modèle d'embedding a échoué, voir `ingestion.py` ci-dessous). C'est la mise en œuvre directe du critère d'acceptation de l'US-103 : *"En cas d'échec de l'appel, le document reste marqué comme 'ingestion partielle' plutôt que de planter silencieusement."*
- **`Vector(LocalMiniLMEmbeddingProvider.dimension)`** et non `Vector(384)` en dur : la dimension a une seule source de vérité — la classe qui produit réellement les vecteurs (voir [01-modele-local-minilm.md](01-modele-local-minilm.md), section 5.5). Si le modèle change un jour, cette ligne suit automatiquement.
- **`cascade="all, delete-orphan"`** sur `Document.chunks` : supprimer un document supprime ses chunks — pas de fragments orphelins en base. `ondelete="CASCADE"` sur la clé étrangère fait la même chose côté base de données (utile si une suppression est faite hors SQLAlchemy).
- **`created_at` avec `server_default=func.now()`** : l'horodatage est posé par Postgres au moment de l'insertion, pas par l'horloge de l'application — cohérent même si plusieurs instances de l'API tournent avec des horloges légèrement désynchronisées.

## `app/rag/ingestion.py` (US-102, US-103)

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.models import Chunk, Document

DEFAULT_MAX_TOKENS = 200
DEFAULT_OVERLAP = 20


def chunk_text(
    text: str, max_tokens: int = DEFAULT_MAX_TOKENS, overlap: int = DEFAULT_OVERLAP
) -> list[str]:
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap < 0 or overlap >= max_tokens:
        raise ValueError("overlap must be within [0, max_tokens)")

    words = text.split()
    if not words:
        return []

    step = max_tokens - overlap
    return [" ".join(words[start : start + max_tokens]) for start in range(0, len(words), step)]
```

### `chunk_text` — pourquoi des *mots*, pas de vrais *tokens*

Le critère d'acceptation de l'US-102 exige une fonction *"pure (testable sans dépendance externe)"*. Une vraie tokenisation (celle que MiniLM utilise réellement en interne, voir [01-modele-local-minilm.md, section 2](01-modele-local-minilm.md#2-quest-ce-que-minilm-all-minilm-l6-v2-)) nécessiterait de charger le tokenizer du modèle — exactement le genre de dépendance externe que l'US-102 demande d'éviter. `chunk_text` découpe donc par **mots** (`text.split()`) comme *proxy* simple et déterministe pour "unité de découpage", indépendant de tout modèle. C'est une approximation assumée : un "mot" n'est pas un "token" (voir l'exemple de tokenisation réelle dans le guide), mais c'est suffisant pour produire des fragments de taille cohérente sans coupler le chunking au choix du modèle d'embedding.

### Comment le chevauchement est calculé

`step = max_tokens - overlap`, puis une fenêtre glissante de `max_tokens` mots tous les `step` mots. Avec `max_tokens=20` et `overlap=5` sur un texte de 45 mots : fenêtres à `[0:20]`, `[15:35]`, `[30:45]` — chaque fenêtre partage exactement 5 mots avec la suivante (vérifié par `test_chunk_text_overlap_between_consecutive_chunks`, voir [04-tests.md](04-tests.md)). Le slicing Python (`words[start:start+max_tokens]`) gère naturellement la fin du texte : la dernière fenêtre peut être plus courte que `max_tokens` sans qu'aucun mot ne soit perdu ni qu'il faille de logique spéciale pour "la dernière fois".

### Validation stricte des paramètres

`overlap >= max_tokens` lèverait sinon une boucle infinie ou un découpage absurde (`step <= 0`) — on préfère une erreur explicite (`ValueError`) à un comportement silencieusement cassé.

### Le reste du pipeline

```python
async def embed_chunks(texts: list[str], provider: EmbeddingProvider) -> list[list[float]]:
    if not texts:
        return []
    return await provider.embed(texts)


async def ingest_document(
    db: AsyncSession,
    *,
    source: str,
    content: str,
    provider: EmbeddingProvider,
    max_tokens: int | None = None,
    overlap: int | None = None,
) -> tuple[Document, int]:
    settings = get_settings()
    max_tokens = max_tokens if max_tokens is not None else settings.rag_chunk_max_tokens
    overlap = overlap if overlap is not None else settings.rag_chunk_overlap

    document = Document(source=source, content=content, status="pending")
    db.add(document)
    await db.flush()

    chunk_texts = chunk_text(content, max_tokens=max_tokens, overlap=overlap)

    try:
        vectors = await embed_chunks(chunk_texts, provider)
    except Exception:
        document.status = "partial"
        await db.commit()
        await db.refresh(document)
        return document, 0

    for text, vector in zip(chunk_texts, vectors, strict=True):
        db.add(Chunk(document_id=document.id, text=text, embedding=vector))

    document.status = "complete"
    await db.commit()
    await db.refresh(document)
    return document, len(chunk_texts)
```

### Détails d'implémentation

- **`embed_chunks` isole l'appel au provider** (US-103 : *"L'appel au modèle d'embedding est isolé dans une fonction facilement remplaçable"*) — `ingest_document` ne sait pas si `provider.embed(...)` parle à un modèle local ou une API externe.
- **`await db.flush()` avant de chunker/embedder** : `flush()` envoie l'`INSERT` du document à Postgres et récupère son `id` généré (auto-increment), sans committer — nécessaire pour renseigner `Chunk.document_id` avant même de savoir si l'embedding va réussir.
- **`max_tokens`/`overlap` lus depuis `Settings` si non fournis explicitement** : reproduit le même principe que le reste du projet (un seul point de configuration, voir [03-configuration.md](../epic-0/03-configuration.md)) — `chunk_text` elle-même n'importe jamais `app.config`, seule la fonction d'orchestration (déjà impure, déjà couplée à la DB) le fait.
- **`try/except Exception` autour du seul appel d'embedding** : si `provider.embed(...)` lève (panne réseau pour un futur provider API, erreur du modèle, etc.), le document déjà `flush()` reste en base avec `status="partial"` — pas de perte du document, pas de crash de la requête HTTP (voir [03-implementation-recherche-api.md](03-implementation-recherche-api.md) pour ce que le endpoint renvoie dans ce cas).
- **`zip(chunk_texts, vectors, strict=True)`** : `strict=True` fait lever une erreur si `provider.embed(...)` ne renvoie pas exactement autant de vecteurs que de textes fournis — un bug de l'implémentation du provider serait détecté immédiatement plutôt que de silencieusement associer le mauvais vecteur au mauvais chunk.
- **Retour `tuple[Document, int]`** plutôt que de compter via `document.chunks` après coup : accéder à une relation SQLAlchemy après un `commit()` en async nécessiterait un rechargement explicite (lazy-loading asynchrone) — on évite ce piège en renvoyant directement le compte déjà connu localement (`len(chunk_texts)`).

## Ce qui n'est pas encore fait

`GET /rag/documents/{id}` (récupérer un document par identifiant) n'est demandé par aucune US du backlog — pas implémenté. `DocumentNotFoundError` (déjà présente dans `app/core/exceptions.py` depuis l'Epic 0) reste prête à être utilisée le jour où un tel endpoint sera ajouté.
