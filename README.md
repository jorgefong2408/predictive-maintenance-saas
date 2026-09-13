# Predictive Maintenance SaaS

Plataforma multi-tenant de mantenimiento predictivo: ingiere datos de sensores, detecta anomalías, predice la vida útil remanente (RUL) de activos industriales y presenta todo en un dashboard en tiempo real con alertas.

Este repositorio sigue el plan documentado en [`docs/PLAN.md`](docs/PLAN.md), ejecutado fase por fase (Semana 0 a Semana 10).

## Estado actual

- [x] Semana 0 — Diseño (dataset, esquema de datos, estructura de repo, casos de uso)
- [x] Semanas 1-2 — Pipeline de datos (ingesta, EDA, esquema TimescaleDB, simulador tiempo real)
- [x] Semanas 3-4 — Modelado ML (baseline, Isolation Forest, XGBoost clasificación + RUL, MLflow) — ver [`docs/MODEL_RESULTS.md`](docs/MODEL_RESULTS.md)
- [x] Semana 5 — Backend / API (FastAPI, JWT multi-tenant, servicio de inferencia, Alembic, pytest)
- [x] Semana 6 — Frontend (React + Vite + TS + Tailwind, alertas en tiempo real por WebSocket)
- [x] Semana 7 — MLOps (drift con Evidently AI, reentrenamiento con promoción "champion", scheduler) — ver [`docs/MODEL_RESULTS.md`](docs/MODEL_RESULTS.md)
- [x] Semana 8 — Infraestructura (Docker, docker-compose con Postgres+TimescaleDB y MLflow reales, K8s, CI/CD) — despliegue a AWS pendiente de decisión del usuario, ver abajo
- [ ] Semana 9 — Observabilidad y pruebas
- [ ] Semana 10 — Documentación y pulido

## Datasets

| Fase | Dataset | Estado |
|---|---|---|
| MVP (clasificación de falla, baseline tabular) | [AI4I 2020 Predictive Maintenance (UCI)](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset) | Descargado en `ml/data/raw/ai4i2020.csv` |
| Fase avanzada (RUL, series temporales) | NASA C-MAPSS (Turbofan Engine Degradation) | Descargado y entrenado (`ml/pipelines/train_cmapss_rul.py`) |

## Estructura del repositorio

```
predictive-maintenance-saas/
├── backend/     # FastAPI + SQLAlchemy + Auth JWT multi-tenant + Dockerfile
├── ml/          # Notebooks, pipelines de entrenamiento, evaluación
├── frontend/    # React + Vite + TypeScript + Tailwind + Dockerfile (nginx)
├── infra/       # infra/sql (esquema TimescaleDB), infra/k8s (manifiestos)
├── docs/        # Plan, decisiones, esquema de datos, casos de uso
├── docker-compose.yml   # Postgres+TimescaleDB, MLflow, backend, frontend
└── .github/workflows/   # CI/CD (lint, test, build+push a ghcr.io)
```

## Stack

Ver [`docs/PLAN.md#5-stack-tecnológico-por-capa`](docs/PLAN.md) para el detalle completo por capa (datos/ML, backend, frontend, infraestructura).

## Cómo correr el proyecto (desarrollo local)

Gestión de dependencias con [`uv`](https://docs.astral.sh/uv/) (Python 3.12).

```bash
uv sync                                          # instala dependencias (grupo ml)
uv run python ml/pipelines/ingest_ai4i.py        # descarga -> ml/data/raw/ai4i2020.csv ya incluida
uv run jupyter notebook ml/notebooks/01_eda_ai4i2020.ipynb
uv run python ml/pipelines/simulate_realtime.py --speed 60 --limit 100
```

Carga a Postgres/TimescaleDB (requiere `infra/sql/001_schema.sql` aplicado y `DATABASE_URL` configurado, ver `.env.example`):

```bash
uv run python ml/pipelines/load_to_postgres.py
```

Hay dos formas de correr el resto del stack — misma base de código en ambas, cambia solo `DATABASE_URL`/`MLFLOW_TRACKING_URI`:

- **Sin Docker** (SQLite local, ver sección Backend abajo) — más rápido para iterar en el backend.
- **Con Docker** (`docker-compose.yml`, Postgres+TimescaleDB y MLflow reales) — ver "Semana 8" más abajo, es la que se probó de punta a punta.

### Backend (API) — sin Docker

Corre sobre SQLite local (`backend/predictmaint.db`, ignorado por git).

```bash
cd backend
uv run --project .. alembic upgrade head        # crea/actualiza el esquema (backend/alembic/)
uv run --project .. uvicorn app.main:app --reload --port 8000
```

Docs interactivos en `http://localhost:8000/docs`. Flujo mínimo: `POST /auth/register` (crea tenant + admin) → `POST /assets` → `POST /assets/{id}/readings` (5 sensores AI4I) → `POST /assets/{id}/predictions` (`failure_probability`, carga el modelo desde el Model Registry de MLflow y dispara una alerta si el riesgo es alto).

Tests (usan un SQLite temporal aislado, no tocan `predictmaint.db`; los de `/predictions` requieren haber corrido `train_ai4i_models.py` al menos una vez):

```bash
uv run pytest backend/tests -v
```

### Frontend (dashboard)

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 — espera el backend en :8000 (VITE_API_URL, ver .env.example)
```

Flujo de demo: `/register` (crea tenant + admin, UC3) → `/assets` (crear activo) → ingestar lecturas vía la API (`POST /assets/{id}/readings`, lo hace `ml/pipelines/simulate_realtime.py` en un flujo real) → abrir el activo → "Predecir riesgo de falla" dispara la inferencia real (MLflow) y, si el riesgo es alto, la alerta aparece en la campana **sin recargar la página** (WebSocket).

### MLOps (drift + reentrenamiento)

```bash
uv run python ml/pipelines/detect_drift.py     # ml/evaluation/drift_report.html + drift_summary.json
uv run python ml/pipelines/retrain.py          # nueva versión; promueve el alias "champion" solo si mejora el F1
```

El backend expone lo mismo por API (rol admin): `POST /admin/models/ai4i-failure-classifier/retrain` y `GET /admin/models/ai4i-failure-classifier/versions`. Un `BackgroundScheduler` interno corre el reentrenamiento cada `RETRAIN_INTERVAL_HOURS` (default 24h, ver `.env.example`) — el plan permite explícitamente "Celery beat *o cron*"; se optó por esto último para no sumar Redis sin un uso real todavía.

## Semana 8 — Infraestructura y despliegue

### Docker Compose (probado de punta a punta)

```bash
docker compose build
docker compose up -d
```

Levanta Postgres+TimescaleDB real (Alembic corre las migraciones al iniciar el backend, incluida la conversión a hypertable — ver `backend/alembic/versions/66036cd3183a_*.py`), un servidor MLflow real (no el sqlite embebido de desarrollo), el backend (`:8000`) y el frontend servido por nginx (`:5173`).

**Paso único tras el primer `up`:** el MLflow del contenedor arranca vacío — hay que sembrar el Model Registry corriendo el pipeline de entrenamiento contra él (una vez; igual que en cualquier entorno nuevo de MLOps):

```bash
MLFLOW_TRACKING_URI=http://localhost:5000 uv run python ml/pipelines/train_ai4i_models.py
MLFLOW_TRACKING_URI=http://localhost:5000 uv run python ml/pipelines/retrain.py   # fija el alias "champion"
```

Dos problemas reales que aparecieron al levantar esto por primera vez (documentados en `docker-compose.yml`):
1. **Versión de imagen de MLflow.** El cliente `mlflow` local es 3.16.x; un servidor 2.x no tiene los endpoints REST que ese cliente espera (`/api/2.0/mlflow/logged-models`) y falla con 404. La imagen del servicio `mlflow` debe coincidir con la versión del paquete `mlflow` en `pyproject.toml`.
2. **`default-artifact-root`.** Tiene que ser el esquema `mlflow-artifacts:/` (proxied a través del servidor por HTTP), no una ruta de archivo local — con una ruta local, cualquier cliente que no comparta el filesystem del contenedor de MLflow (ej. el backend, en su propio contenedor) falla al descargar el modelo con `No such artifact`.

### Kubernetes / CI-CD

- `.github/workflows/ci.yml`: lint + test (backend y frontend) en cada push/PR; build y push de imágenes a `ghcr.io` en `main`. El job de deploy a AWS existe como plantilla pero queda deshabilitado (`if: false`) — necesita credenciales de una cuenta real.
- `infra/k8s/`: manifiestos planos (Postgres, MLflow, backend, frontend, Ingress) con la misma topología que `docker-compose.yml`. **Escritos pero no aplicados contra ningún cluster** — ver [`infra/k8s/README.md`](infra/k8s/README.md) para los pasos pendientes y por qué.

### Por qué no hay despliegue real a AWS

Requiere una cuenta de AWS del usuario, sus credenciales, y autorización explícita para el gasto que eso implica (EKS/ECS, Load Balancer, etc.) — no es algo que esta sesión deba decidir por su cuenta. Además, esta máquina ya tiene `kubectl` configurado contra un cluster EKS real de otro proyecto (`recomendaciones-cluster`); no se ejecutó ningún comando contra él.
