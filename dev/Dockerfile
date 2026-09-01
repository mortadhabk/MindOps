FROM python:3.12-slim

WORKDIR /code

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN uv run --no-sync python -c "from app.rag.embeddings import get_embedding_provider; get_embedding_provider()"

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
