# Recherche et API (US-104, US-105, US-106)

## `app/rag/vector_store.py` (US-104)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.models import Chunk


async def nearest_chunks(
    db: AsyncSession, query_embedding: list[float], top_k: int
) -> list[tuple[Chunk, float]]:
    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = select(Chunk, (1 - distance).label("similarity")).order_by(distance).limit(top_k)

    result = await db.execute(stmt)
    return [(chunk, similarity) for chunk, similarity in result.all()]
```

### Ce que fait chaque ligne

- **`Chunk.embedding.cosine_distance(query_embedding)`** : `Vector` (le type pgvector utilisé pour la colonne `embedding`, voir [02-modeles-et-ingestion.md](02-modeles-et-ingestion.md)) ajoute cette méthode directement utilisable dans une expression SQLAlchemy — elle compile en l'opérateur SQL `<=>` de pgvector, expliqué en détail dans le [guide RAG, section 8](00-guide-debutant-rag.md#8-la-recherche-par-similarité-avec-pgvector). Aucun SQL brut écrit à la main.
- **`(1 - distance).label("similarity")`** : converti la distance cosinus en score de similarité (1 = identique, 0 = aucun rapport) — c'est ce score, pas la distance brute, que l'US-106 demande de renvoyer au client.
- **`order_by(distance).limit(top_k)`** : le tri se fait sur la *distance* (croissante), pas sur la colonne calculée `similarity` — c'est strictement équivalent (trier par distance croissante = trier par similarité décroissante) mais évite d'imposer à Postgres de recalculer ou de trier sur une expression dérivée.
- **Rôle de ce fichier** : isoler la seule requête SQL du module dans un point unique, pour que `retriever.py` n'ait jamais à connaître les détails pgvector — cohérent avec la présence de `vector_store.py` dans la structure du backlog (*"abstraction pgvector, remplaçable"*).

## `app/rag/retriever.py` (US-104)

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.models import Chunk
from app.rag.vector_store import nearest_chunks


async def search(
    db: AsyncSession,
    query: str,
    provider: EmbeddingProvider,
    top_k: int = 5,
    similarity_threshold: float | None = None,
) -> list[tuple[Chunk, float]]:
    threshold = (
        similarity_threshold
        if similarity_threshold is not None
        else get_settings().rag_similarity_threshold
    )

    [query_vector] = await provider.embed([query])
    results = await nearest_chunks(db, query_vector, top_k)
    return [(chunk, score) for chunk, score in results if score >= threshold]
```

### Pourquoi un seuil de similarité (`rag_similarity_threshold`)

Sans seuil, `nearest_chunks` renvoie toujours exactement `top_k` résultats, même si aucun n'est réellement pertinent (pgvector renvoie les *k plus proches disponibles*, pas "les k pertinents" — une base avec un seul chunk sur un tout autre sujet serait quand même renvoyée). Le seuil filtre les résultats dont la similarité est trop faible pour être utile. C'est directement le critère d'acceptation de l'US-107 : *"Un test vérifie qu'une recherche non pertinente ne retourne rien au-delà d'un seuil de similarité configurable."* Le seuil vient de `Settings.rag_similarity_threshold` par défaut (0.2, une valeur basse — voir [03-configuration.md](../epic-0/03-configuration.md) pour le mécanisme), mais reste surchargeable par appel (utile pour les tests, voir [04-tests.md](04-tests.md)).

### `[query_vector] = await provider.embed([query])`

`EmbeddingProvider.embed` travaille toujours par lot (`list[str] -> list[list[float]]`, voir [01-modele-local-minilm.md](01-modele-local-minilm.md)), même pour une seule question — cohérence stricte avec l'interface, pas de méthode séparée `embed_one`. Le déballage `[query_vector] = ...` documente au passage, par sa forme, qu'on attend exactement un seul élément en retour.

## `app/rag/schemas.py` (US-105, US-106)

```python
from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    source: str = Field(min_length=1)
    content: str = Field(min_length=1)


class IngestResponse(BaseModel):
    document_id: int
    status: str
    chunks_created: int


class SearchResultItem(BaseModel):
    chunk_id: int
    document_id: int
    text: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
```

`min_length=1` sur `source` et `content` : un document sans contenu n'a rien à ingérer — FastAPI renvoie automatiquement une erreur `422 Unprocessable Entity` avant même d'entrer dans l'endpoint (testé par `test_ingest_rejects_empty_content`, voir [04-tests.md](04-tests.md)).

## `app/rag/router.py` (US-105, US-106)

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.ingestion import ingest_document
from app.rag.retriever import search as search_chunks
from app.rag.schemas import DocumentIn, IngestResponse, SearchResponse, SearchResultItem

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    payload: DocumentIn,
    db: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> IngestResponse:
    document, chunks_created = await ingest_document(
        db, source=payload.source, content=payload.content, provider=provider
    )
    return IngestResponse(
        document_id=document.id, status=document.status, chunks_created=chunks_created
    )


@router.get("/search", response_model=SearchResponse)
async def search_endpoint(
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> SearchResponse:
    results = await search_chunks(db, q, provider, top_k=top_k)
    return SearchResponse(
        query=q,
        results=[
            SearchResultItem(
                chunk_id=chunk.id, document_id=chunk.document_id, text=chunk.text, score=score
            )
            for chunk, score in results
        ],
    )
```

### Injection de dépendances

Chaque endpoint reçoit `db` (session par requête, `get_db`, Epic 0) et `provider` (`get_embedding_provider`, mis en cache — le modèle MiniLM n'est chargé qu'une fois pour toute la durée de vie du processus, voir [01-modele-local-minilm.md, section 5.3](01-modele-local-minilm.md#53-la-fabrique-factory--choisir-et-mettre-en-cache-le-provider)) via `Depends(...)`. Aucun endpoint n'ouvre de connexion ou ne charge de modèle lui-même.

### `top_k: int = Query(5, ge=1, le=50)`

Borné entre 1 et 50 : un `top_k` non borné exposerait un endpoint qui pourrait renvoyer arbitrairement tous les chunks d'une base volumineuse sur une requête mal formée ou malveillante.

## Montage dans l'agrégateur — `app/api/router.py`

```python
from fastapi import APIRouter

from app.rag.router import router as rag_router

router = APIRouter()
router.include_router(rag_router, prefix="/rag", tags=["rag"])
```

Exactement la modification annoncée dans [02-architecture-hexagonale.md](../epic-0/02-architecture-hexagonale.md) — la seule touchée en dehors du dossier `rag/`.

## Exemple d'usage — vraie exécution, vrai modèle

Testé en conditions réelles (vrai `LocalMiniLMEmbeddingProvider`, pas un fake de test), en reformulant volontairement la question avec des mots différents du document ingéré :

```bash
curl -X POST http://localhost:8000/rag/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "manuel", "content": "Le service de paiement echoue quand le montant depasse 10 000 euros. La cause identifiee est un depassement du champ DECIMAL en base de donnees."}'
# {"document_id":14,"status":"complete","chunks_created":1}

curl "http://localhost:8000/rag/search?q=pourquoi%20le%20paiement%20ne%20fonctionne%20pas%20au-dela%20de%2010000%20euros&top_k=3"
# {"query":"pourquoi le paiement ne fonctionne pas au-dela de 10000 euros","results":[{"chunk_id":13,"document_id":14,"text":"Le service de paiement echoue quand le montant depasse 10 000 euros. La cause identifiee est un depassement du champ DECIMAL en base de donnees.","score":0.784}]}
```

La question ("pourquoi le paiement ne fonctionne pas") ne partage presque aucun mot avec le document ingéré ("le service de paiement échoue") — score de similarité 0,784, largement au-dessus du seuil par défaut (0,2). C'est la confirmation, en conditions réelles, que le choix du modèle multilingue (section 2 de [01-modele-local-minilm.md](01-modele-local-minilm.md)) fonctionne comme attendu sur du français.
