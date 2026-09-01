# Tests (US-107)

## Un bug corrigé avant même d'écrire le premier test

La fixture `db_session` de l'Epic 0 (voir [08-tests.md](../epic-0/08-tests.md)) ouvrait une transaction et l'annulait (`rollback`) à la fin de chaque test — mais aucun test de l'Epic 0 n'appelait jamais `session.commit()` (le seul test existant, `/health`, ne touchait pas la base). `ingest_document` (Epic 1), lui, appelle bien `db.commit()`. Or un `commit()` sur une session liée directement à une connexion **clôt la transaction externe** : plus rien à annuler ensuite, et les données écrites par un test auraient réellement persisté dans la base de développement.

### Le correctif — `tests/conftest.py`

```python
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()
```

`join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0) change ce que `session.commit()` fait réellement : au lieu de committer la transaction de la connexion, il crée/libère un **SAVEPOINT** — la transaction externe reste ouverte tout du long. `connection.rollback()`, à la fin du test, annule alors tout, y compris tout ce que le code testé a "committé" entre-temps. C'est le pattern documenté par SQLAlchemy lui-même pour brancher une session de test sur une transaction externe annulable ("Joining a Session into an External Transaction").

**Sans ce correctif**, `test_ingest_document_creates_chunks_with_embeddings` (ci-dessous) aurait silencieusement laissé des lignes dans les tables `documents`/`chunks` de la base de développement à chaque exécution de la suite de tests.

## Un deuxième bug découvert en exécutant la suite complète

Une fois plusieurs tests utilisant `db_session` exécutés à la suite, le deuxième (et les suivants) échouaient avec une erreur asyncpg de bas niveau :

```
asyncpg.exceptions._base.InterfaceError: cannot perform operation: another operation is in progress
```

### Cause

`pytest-asyncio` crée par défaut **un nouvel event loop par fonction de test** (`asyncio_default_test_loop_scope = "function"`). Mais l'`engine` SQLAlchemy async de l'application (`app/core/database.py`) est un **singleton créé une seule fois à l'import du module**, avec son propre pool de connexions. Une connexion établie sous l'event loop du premier test, remise dans le pool à la fin de ce test, se retrouve réutilisée par le test suivant — qui tourne, lui, sur un **event loop différent**. Une connexion asyncio (et l'objet asyncpg sous-jacent) n'est pas transférable d'un event loop à un autre : la réutiliser ainsi produit exactement ce type d'erreur de protocole de bas niveau.

Signe révélateur : le tout premier test touchant la base (`test_ingest_document_creates_chunks_with_embeddings`) passait toujours ; c'est le **suivant** qui échouait — cohérent avec "la connexion du pool vient de l'event loop du test précédent".

### Le correctif — `pyproject.toml`

```toml
[tool.pytest.ini_options]
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

Tous les tests d'une même exécution de `pytest` partagent désormais **le même event loop** — cohérent avec le fait que l'`engine` (et son pool de connexions) est lui aussi partagé pour toute la durée de vie du process. C'est la configuration recommandée par `pytest-asyncio` dès qu'un engine/pool de connexions asynchrone est partagé entre plusieurs tests plutôt que recréé à chaque fois.

## `tests/rag/fakes.py` — `FakeEmbeddingProvider`

```python
import hashlib

from app.rag.embeddings.base import EmbeddingProvider


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

Conforme à la spec de [01-modele-local-minilm.md, section 5.6](01-modele-local-minilm.md#56-fakeembeddingprovider--pour-les-tests-us-107), avec un ajustement décidé à l'implémentation : **`dimension = 384`**, pas 8 comme envisagé initialement dans la spec. Raison : la colonne réelle `chunks.embedding` est typée `Vector(384)` (voir [02-modeles-et-ingestion.md](02-modeles-et-ingestion.md)) — un provider de test à 8 dimensions ne pourrait tout simplement pas insérer de ligne dans cette colonne. `_fake_vector` étend donc le hash SHA-256 (32 octets par tour) sur autant de tours que nécessaire pour remplir 384 valeurs, en re-hachant le résultat précédent — toujours déterministe (le même texte produit toujours le même vecteur), sans dépendre du vrai modèle.

### Une propriété statistique vérifiée avant d'écrire les tests

Avant d'écrire des assertions sur des scores de similarité, un calcul rapide a confirmé le comportement de ces vecteurs "faux" :

| Comparaison | Similarité cosinus observée |
|---|---|
| Deux textes différents | ~0,76 |
| Un texte contre lui-même | 1,0 |

Ces vecteurs sont tous à composantes positives (octets divisés par 255), ce qui donne une similarité de base élevée (~0,76) entre deux vecteurs *indépendants* du fait de la géométrie des vecteurs non centrés — sans rapport avec une vraie proximité sémantique. **Conséquence pour les tests** : un seuil de similarité de `0.9` sépare de façon fiable "le même texte" (1,0) de "un texte différent" (~0,76), ce qui permet d'écrire des tests de seuil non-fragiles (`test_search_filters_out_results_below_threshold`) sans dépendre du vrai modèle ni d'un comportement sémantique réel.

## `tests/rag/test_ingestion.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_chunk_text_empty_text_returns_no_chunks` | Texte vide ou uniquement des espaces → `[]` |
| `test_chunk_text_shorter_than_max_returns_single_chunk` | Texte plus court que `max_tokens` → un seul chunk, identique au texte |
| `test_chunk_text_overlap_between_consecutive_chunks` | Les 5 derniers mots d'un chunk = les 5 premiers mots du suivant (chevauchement réel, pas juste "ça ne plante pas") |
| `test_chunk_text_rejects_overlap_greater_or_equal_to_max_tokens` | `ValueError` si la config est incohérente |
| `test_chunk_text_rejects_non_positive_max_tokens` | `ValueError` si `max_tokens <= 0` |
| `test_ingest_document_creates_chunks_with_embeddings` | Le document est `complete`, le bon nombre de chunks est en base, chaque embedding a la bonne dimension |
| `test_ingest_document_marks_partial_on_embedding_failure` | Avec un provider qui lève une exception (`_FailingEmbeddingProvider`), le document reste `partial`, **aucun** chunk n'est créé, et surtout **aucune exception ne remonte** au test — exactement le critère de l'US-103 |

Les cinq premiers tests sur `chunk_text` sont synchrones et ne touchent pas la base — ils valident la fonction *pure* isolément (US-102 : *"pure (testable sans dépendance externe)"*). Les deux derniers utilisent la fixture `db_session`.

## `tests/rag/test_retriever.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_search_returns_exact_match_first` | Deux documents sans rapport ingérés ; une recherche sur le texte exact du premier le renvoie en tête, avec un score > 0,99 |
| `test_search_respects_top_k` | Cinq documents ingérés, `top_k=2` → exactement 2 résultats |
| `test_search_filters_out_results_below_threshold` | Avec `similarity_threshold=0.9`, un document sans rapport avec la requête est bien exclu des résultats |

## `tests/rag/test_router.py` — tests HTTP de bout en bout

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

### Pourquoi surcharger les dépendances FastAPI dans les tests

- **`get_db` → `db_session`** : sans cette surcharge, les endpoints appelés via le `client` de test ouvriraient leurs *propres* sessions (via `async_session_factory`, la vraie fabrique de production), complètement indépendantes de la transaction annulable de `db_session`. Les écritures faites par une requête HTTP de test ne seraient alors *jamais* annulées — même risque que le bug de la section précédente. En pointant `get_db` vers `db_session`, la requête HTTP et les assertions du test partagent la même transaction, annulée ensemble à la fin.
- **`get_embedding_provider` → `FakeEmbeddingProvider`** : sans cette surcharge, chaque test HTTP chargerait le vrai modèle MiniLM (plusieurs secondes, en plus d'un vrai calcul CPU) — inutile pour vérifier que le *routing*, la *validation* et le *format de réponse* HTTP sont corrects.
- **`autouse=True`** : s'applique à tous les tests du fichier sans avoir à le demander explicitement à chaque fonction de test — seul `db_session` doit être déclaré en paramètre de la fixture elle-même (pour la lier au bon cycle de vie), pas de chaque test individuel.

| Test | Ce qu'il vérifie |
|---|---|
| `test_ingest_then_search_end_to_end` | `POST /rag/ingest` puis `GET /rag/search` sur le même texte, en passant par la vraie pile HTTP (validation Pydantic, routing FastAPI, dépendances) |
| `test_ingest_rejects_empty_content` | `content=""` → `422` (Pydantic, avant même d'entrer dans l'endpoint) |

## Lancer les tests

```bash
docker compose exec api uv run pytest tests/rag -v
```

Tous les tests de `tests/rag/` sont rapides (aucun ne charge le vrai modèle MiniLM) — la seule dépendance externe réelle est la base de données Postgres, déjà nécessaire pour tout le reste du projet.

## Ce qui n'est volontairement pas testé ici

Aucun test n'utilise le vrai `LocalMiniLMEmbeddingProvider` — la pertinence sémantique réelle du modèle a été vérifiée manuellement pendant le développement (voir la note sur le choix du modèle multilingue dans [01-modele-local-minilm.md](01-modele-local-minilm.md)), mais un test automatisé dessus serait lent (chargement du modèle) et sortirait du périmètre de l'US-107, qui porte sur le *pipeline*, pas sur la qualité intrinsèque d'un modèle tiers.
