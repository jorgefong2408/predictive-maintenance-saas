# Predictive Maintenance SaaS

Plataforma multi-tenant de mantenimiento predictivo: ingiere datos de sensores, detecta anomalías, predice la vida útil remanente (RUL) de activos industriales y presenta todo en un dashboard en tiempo real con alertas.

Este repositorio sigue el plan documentado en [`docs/PLAN.md`](docs/PLAN.md), ejecutado fase por fase (Semana 0 a Semana 10).

## Estado actual

- [x] Semana 0 — Diseño (dataset, esquema de datos, estructura de repo, casos de uso)
- [x] Semanas 1-2 — Pipeline de datos (ingesta, EDA, esquema TimescaleDB, simulador tiempo real)
- [x] Semanas 3-4 — Modelado ML (baseline, Isolation Forest, XGBoost clasificación + RUL, MLflow) — ver [`docs/MODEL_RESULTS.md`](docs/MODEL_RESULTS.md)
- [x] Semana 5 — Backend / API (FastAPI, JWT multi-tenant, servicio de inferencia, Alembic, pytest)
- [ ] Semana 6 — Frontend
- [ ] Semana 7 — MLOps
- [ ] Semana 8 — Infraestructura y despliegue
- [ ] Semana 9 — Observabilidad y pruebas
- [ ] Semana 10 — Documentación y pulido

## Datasets

| Fase | Dataset | Estado |
|---|---|---|
| MVP (clasificación de falla, baseline tabular) | [AI4I 2020 Predictive Maintenance (UCI)](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset) | Descargado en `ml/data/raw/ai4i2020.csv` |
| Fase avanzada (RUL, series temporales) | NASA C-MAPSS (Turbofan Engine Degradation) | Pendiente (Semana 3-4) |

## Estructura del repositorio

```
predictive-maintenance-saas/
├── backend/     # FastAPI + SQLAlchemy + Auth JWT multi-tenant
├── ml/          # Notebooks, pipelines de entrenamiento, evaluación
├── frontend/    # React + Vite + TypeScript + Tailwind
├── infra/       # docker-compose, Kubernetes/Helm, Terraform
├── docs/        # Plan, decisiones, esquema de datos, casos de uso
└── .github/workflows/  # CI/CD
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

`docker-compose.yml` con Postgres/TimescaleDB, backend, frontend y MLflow llega en la Semana 8 de `docs/PLAN.md`.

### Backend (API)

Sin Docker por ahora: corre sobre SQLite local (`backend/predictmaint.db`, ignorado por git). `DATABASE_URL` en `.env` apunta a Postgres+TimescaleDB cuando exista (Semana 8) — el código no cambia.

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
