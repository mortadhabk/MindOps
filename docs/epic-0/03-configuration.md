# Configuration (US-002)

## Fichier : `app/config.py`

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="ai-agent-poc", alias="APP_NAME")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = Field(default=False, alias="DEBUG")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent_poc",
        alias="DATABASE_URL",
    )

    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str = Field(default="claude-sonnet-5", alias="LLM_MODEL")

    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")

    email_api_key: str | None = Field(default=None, alias="EMAIL_API_KEY")
    email_from: str | None = Field(default=None, alias="EMAIL_FROM")

    api_key: str | None = Field(default=None, alias="API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Pourquoi `pydantic-settings` et pas un simple `os.environ.get(...)` partout

- **Validation au démarrage** : si une variable est du mauvais type (`DEBUG=oui` au lieu de `true`/`false`), l'application refuse de démarrer avec un message clair, plutôt que de planter plus tard au moment d'utiliser la valeur.
- **Un seul point de vérité** : tout module qui a besoin d'une valeur de config importe `get_settings()`, jamais `os.environ` directement. Ça évite que la connaissance des noms de variables d'environnement se disperse dans tout le code.
- **Chargement automatique de `.env`** : `SettingsConfigDict(env_file=".env")` fait que `Settings()` lit d'abord les variables d'environnement du process, puis complète avec `.env` — pratique en local, sans changer de comportement en production (où `.env` n'existe généralement pas et les vraies variables d'environnement du conteneur/host prennent le relais).

### Détails d'implémentation qui comptent

- **`alias="DATABASE_URL"`** : chaque champ Pydantic a un nom Python en `snake_case` (`database_url`) mais un alias qui correspond au nom de la variable d'environnement en `MAJUSCULES` (convention Unix). C'est l'alias, pas le nom du champ, qui est recherché dans l'environnement.
- **`extra="ignore"`** : si une variable d'environnement non déclarée ici traîne dans `.env` (ex. une variable système), `Settings()` ne plante pas dessus. Sans ça, toute variable d'environnement surprise ferait échouer le démarrage.
- **Valeurs par défaut y compris pour `database_url`** : contrairement à un choix strict ("pas de défaut, ça doit planter si absent"), on a mis une valeur par défaut pointant vers le Postgres local de `docker-compose.yml`. Ça permet à `Settings()` de s'instancier sans aucun `.env` — utile pour que `uvicorn app.main:app` démarre out-of-the-box (US-001) avant même que la base de données ne soit branchée (US-004).
- **`@lru_cache` sur `get_settings()`** : `Settings()` est coûteux à réinstancier (elle relit et revalide `.env` à chaque appel) et les valeurs ne changent pas pendant la vie du process — `lru_cache` en fait un singleton implicite. **Piège à connaître** : si un test change une variable d'environnement à la volée en espérant que `get_settings()` la reflète, il faut appeler `get_settings.cache_clear()` avant, sinon l'ancienne instance mise en cache est renvoyée.

## Fichier : `.env.example`

```dotenv
# Application
APP_NAME=ai-agent-poc
ENVIRONMENT=local
LOG_LEVEL=INFO
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent_poc

# LLM (agent orchestrator)
LLM_API_KEY=
LLM_MODEL=claude-sonnet-5

# Connecteur GitHub Issues
GITHUB_TOKEN=

# Envoi d'email (Resend ou SendGrid)
EMAIL_API_KEY=
EMAIL_FROM=

# Authentification API (Epic 7, bonus)
API_KEY=
```

Chaque variable correspond à un champ de `Settings`, avec un commentaire indiquant à quel epic elle sert :

| Variable | Epic qui l'utilise | Usage |
|---|---|---|
| `APP_NAME`, `ENVIRONMENT`, `LOG_LEVEL`, `DEBUG` | Epic 0 | Titre FastAPI, niveau de log, mode debug des erreurs |
| `DATABASE_URL` | Epic 0 (infra), Epic 1+ (données) | Connexion Postgres async |
| `LLM_API_KEY`, `LLM_MODEL` | Epic 3 | Client LLM de l'orchestrateur agentique |
| `GITHUB_TOKEN` | Epic 2 | Authentification API GitHub Issues |
| `EMAIL_API_KEY`, `EMAIL_FROM` | Epic 4 | Envoi d'email via Resend/SendGrid |
| `API_KEY` | Epic 7 (bonus) | Protection de l'API par clé simple |

Aucune valeur réelle n'est commitée — `.env.example` ne contient que des placeholders vides ou des valeurs de développement local sans risque (`postgres:postgres` en local uniquement).

## Fichier : `.gitignore`

```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.ruff_cache/
*.egg-info/
```

La ligne qui compte pour cette US : `.env`. Le fichier réel (avec de vraies clés, le jour où il y en aura) n'est jamais commité — seul `.env.example` l'est.

## Exemple d'usage dans le reste du code

```python
from app.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url)
```

C'est exactement ce que fait [`app/core/database.py`](04-base-de-donnees-migrations.md) — aucun module n'a de raison de lire `os.environ` directement.
