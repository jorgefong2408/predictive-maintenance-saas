FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copiamos primero solo lo necesario para resolver dependencias (cachea la capa
# de `uv sync` entre builds mientras no cambie pyproject.toml/uv.lock).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-group dev

COPY backend/ ./backend/
COPY ml/pipelines/ ./ml/pipelines/
COPY ml/evaluation/ ./ml/evaluation/
COPY ml/data/raw/ai4i2020.csv ./ml/data/raw/ai4i2020.csv

WORKDIR /app/backend
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
