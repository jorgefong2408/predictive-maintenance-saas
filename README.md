# Predictive Maintenance SaaS

[![CI](https://github.com/jorgefong2408/predictive-maintenance-saas/actions/workflows/ci.yml/badge.svg)](https://github.com/jorgefong2408/predictive-maintenance-saas/actions/workflows/ci.yml)

Plataforma multi-tenant de mantenimiento predictivo: ingiere datos de sensores, detecta anomalías, predice la vida útil remanente (RUL) de activos industriales y presenta todo en un dashboard en tiempo real con alertas.

Este repositorio sigue el plan documentado en [`docs/PLAN.md`](docs/PLAN.md), ejecutado fase por fase (Semana 0 a Semana 10). Cada decisión de arquitectura no obvia tiene su porqué documentado en el propio código o en `docs/` — no es una lista de tecnologías, es un sistema que se puede levantar y probar de punta a punta hoy mismo con `docker compose up`.

## Arquitectura

```mermaid
flowchart TB
    Browser["Navegador<br/>(dashboard React)"]

    subgraph compose["docker-compose"]
        Frontend["frontend<br/>nginx + React SPA"]
        Backend["backend<br/>FastAPI"]
        Postgres[("postgres<br/>TimescaleDB<br/>hypertable de sensor_readings")]
        MLflow["mlflow<br/>tracking + model registry"]
        Prometheus["prometheus"]
        Grafana["grafana"]
        Loki["loki"]
        Promtail["promtail<br/>lee logs de todos los contenedores"]
        Scheduler["BackgroundScheduler<br/>(en el proceso del backend)"]
    end

    Browser -- "HTTPS" --> Frontend
    Browser -- "WebSocket /ws/alerts" --> Backend
    Frontend -- "fetch /auth /assets /alerts /admin" --> Backend
    Backend -- "SQLAlchemy + Alembic" --> Postgres
    Backend -- "carga modelo por alias champion" --> MLflow
    Scheduler -- "reentrena + promueve si mejora F1" --> MLflow
    Prometheus -- "scrape /metrics" --> Backend
    Promtail --> Loki
    Grafana --> Prometheus
    Grafana --> Loki
```

Fuera del diagrama (corren aparte, no dentro de docker-compose): los pipelines de `ml/` (ingesta, EDA, entrenamiento, drift) se ejecutan bajo demanda con `uv run`, apuntando al mismo Postgres/MLflow cuando hace falta — no son servicios de larga duración.

## Estado actual

- [x] Semana 0 — Diseño (dataset, esquema de datos, estructura de repo, casos de uso)
- [x] Semanas 1-2 — Pipeline de datos (ingesta, EDA, esquema TimescaleDB, simulador tiempo real)
- [x] Semanas 3-4 — Modelado ML (baseline, Isolation Forest, XGBoost clasificación + RUL, MLflow) — ver [`docs/MODEL_RESULTS.md`](docs/MODEL_RESULTS.md)
- [x] Semana 5 — Backend / API (FastAPI, JWT multi-tenant, servicio de inferencia, Alembic, pytest)
- [x] Semana 6 — Frontend (React + Vite + TS + Tailwind, alertas en tiempo real por WebSocket)
- [x] Semana 7 — MLOps (drift con Evidently AI, reentrenamiento con promoción "champion", scheduler) — ver [`docs/MODEL_RESULTS.md`](docs/MODEL_RESULTS.md)
- [x] Semana 8 — Infraestructura (Docker, docker-compose con Postgres+TimescaleDB y MLflow reales, K8s, CI/CD) — despliegue a AWS pendiente de decisión del usuario, ver abajo
- [x] Semana 9 — Observabilidad (Prometheus+Grafana, Loki), prueba de carga con Locust, test e2e — ver [`load-testing/RESULTS.md`](load-testing/RESULTS.md)
- [x] Semana 10 — Documentación y pulido — video demo y deploy público pendientes de decisión del usuario, ver abajo

## Resultados

**Modelo** — comparado siempre contra un baseline explícito, no contra "nada" (detalle completo en [`docs/MODEL_RESULTS.md`](docs/MODEL_RESULTS.md)):

| | Baseline | Modelo final | Mejora |
|---|---|---|---|
| Clasificación de falla (AI4I 2020) — F1 | 0.000 (DummyClassifier) | **0.603** (XGBoost, ROC-AUC 0.975) | — |
| RUL (NASA C-MAPSS FD001) — RMSE | 20.75 ciclos (regresión lineal) | **17.06 ciclos** (XGBoost) | -28% error |

**Sistema** — bajo carga real con Locust, no solo "funciona en mi máquina" (detalle en [`load-testing/RESULTS.md`](load-testing/RESULTS.md)):

| | Antes | Después |
|---|---|---|
| Latencia mediana, endpoint de inferencia | 120 ms | **69 ms** |
| Throughput sostenido (20 usuarios concurrentes) | ~20 req/s, 0 fallos | ~21 req/s, 0 fallos |

**Producto** — UC1 completo, de punta a punta, en el navegador real: ingesta de lecturas → predicción de riesgo de falla (84.7%) vía el modelo real registrado en MLflow → estado del activo pasa a CRÍTICO → alerta aparece en la campana **sin recargar la página** (WebSocket) → se puede reconocer. Multi-tenancy (UC3) verificado: un segundo tenant recibe 404 al intentar ver el activo del primero.

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

## Semana 9 — Observabilidad y pruebas

Con `docker compose up -d` (Semana 8) también levantan:

- **Prometheus** (`:9090`) — scrapea `/metrics` del backend (vía `prometheus-fastapi-instrumentator`: latencia, throughput y tasa de error por endpoint).
- **Grafana** (`:3001`, sin login — anónimo habilitado solo para esta demo local) — dashboard "PredictMaint API - Overview" pre-provisto, datasources de Prometheus y Loki ya configurados.
- **Loki + Promtail** — logs centralizados de **todos** los contenedores del stack, leídos directamente del socket de Docker (sin instrumentar cada servicio); consultables desde Grafana → Explore → datasource Loki.

Prueba de carga con Locust sobre `POST /assets/{id}/predictions` (el endpoint de inferencia, no el CRUD alrededor):

```bash
uv run python -m locust -f load-testing/locustfile.py --host http://localhost:8000 \
  --headless -u 20 -r 5 -t 45s --csv load-testing/results
```

Encontró y corrigió un cuello de botella real (el servicio de inferencia resolvía la versión del modelo contra MLflow por red en cada request) y descartó dos hipótesis más sobre una cola de latencia p99 que persiste sin causa confirmada — ver el detalle completo, con números de antes/después, en [`load-testing/RESULTS.md`](load-testing/RESULTS.md).

Test end-to-end del flujo completo (`backend/tests/test_e2e_flow.py`): UC3 (alta de tenant) → UC4 (alta de activo) → UC1 (ingesta → predicción real vía MLflow → alerta automática → reconocimiento) → UC6 (trazabilidad), todo en una sola corrida — se suma a los tests unitarios/de integración existentes (`uv run pytest backend/tests -v`).

### Por qué no hay despliegue real a AWS

Requiere una cuenta de AWS del usuario, sus credenciales, y autorización explícita para el gasto que eso implica (EKS/ECS, Load Balancer, etc.) — no es algo que esta sesión deba decidir por su cuenta. Además, esta máquina ya tiene `kubectl` configurado contra un cluster EKS real de otro proyecto (`recomendaciones-cluster`); no se ejecutó ningún comando contra él.

## Semana 10 — Documentación y pulido

Este README (arquitectura, checklist por semana, resultados de modelo/sistema/producto), `docs/` (plan, esquema de datos, casos de uso, resultados de modelo detallados), `load-testing/RESULTS.md` y `infra/k8s/README.md` son la documentación final — no un documento aparte, para que no se desactualice del código. Licencia MIT (`LICENSE`) para dejar claro que el código es reusable como referencia de portafolio.

**Pendiente de decisión del usuario, no de esta sesión:**
- **Video demo (2-3 min):** requiere grabar pantalla, algo que esta sesión no puede hacer. Guion sugerido: (1) `docker compose up -d` levantando todo el stack, (2) registro de un tenant nuevo en el dashboard, (3) crear un activo e ingestar lecturas, (4) "Predecir riesgo de falla" → alerta apareciendo en vivo por WebSocket, (5) `GET /admin/models/.../versions` mostrando el historial en MLflow, (6) el dashboard de Grafana con métricas reales de la corrida de Locust.
- **Deploy público:** bloqueado por lo mismo que el despliegue a AWS de la Semana 8 — necesita una decisión explícita sobre cuenta/credenciales/gasto en la nube.

## Optimización y escalabilidad (post-plan)

Pasada de revisión sobre lo ya construido, buscando específicamente qué se rompería al escalar — no features nuevas. Cada punto es un hallazgo real, no una mejora especulativa.

**Bug real encontrado: reentrenamiento duplicado entre réplicas.** `infra/k8s/04-backend.yaml` corre 2 réplicas del backend, pero `BackgroundScheduler` (Semana 7) es un scheduler en memoria por proceso — sin coordinación, las dos réplicas reentrenarían por separado en cada tick. Fix: un advisory lock de Postgres (`pg_try_advisory_lock`) en `app/services/scheduler.py` — solo una réplica ejecuta el job en cada tick, sin sumar infraestructura nueva. Verificado con tests que mockean ambas ramas (lock adquirido / lock ocupado por otra réplica).

**Bug real encontrado: las alertas por WebSocket no cruzaban entre réplicas.** El `ConnectionManager` (Semana 6) solo conocía las conexiones de SU PROPIO proceso — con 2 réplicas, un cliente conectado a la réplica B nunca se enteraba de una alerta creada por la réplica A. Fix: Postgres LISTEN/NOTIFY (`app/services/ws_manager.py::PostgresListener`) — cada réplica escucha el mismo canal y reenvía a sus propios clientes locales; la que crea la alerta también se entera por la misma vía (ya no hay entrega "directa" en Postgres). **Verificado de verdad, no solo con mocks:** un listener externo (simulando una segunda réplica) recibió la notificación disparada por una predicción real contra el backend corriendo en Docker.

**Índices faltantes en las consultas que sí importan.** `alerts` y `predictions` no tenían índices más allá de la PK — pero *toda* consulta multi-tenant filtra por `tenant_id`/`asset_id`. Añadidos `ix_alerts_tenant_resolved`, `ix_alerts_asset_id`, `ix_predictions_asset_predicted_at` (migración `2da84ca336c5`), confirmados en el Postgres real vía `\di`.

**Paginación ausente en `/assets` y `/alerts`.** Ambos devolvían la tabla completa del tenant sin límite. Añadido `limit`/`offset` (default 100, tope 500) — no rompe al frontend actual (no manda esos params, usa el default) pero acota el peor caso a medida que crecen los datos.

**Frontend: bundle de 713KB en un solo chunk → dividido por ruta.** `AssetDetailPage` (con `recharts`, la dependencia más pesada) ahora es un `React.lazy` — solo se descarga cuando el usuario entra al detalle de un activo, no en la carga inicial de `/login`. `LoginPage`/`RegisterPage` quedaron en 2-3KB cada una.

**Frontend: un token vencido fallaba en silencio.** `RequireAuth` solo comprobaba que hubiera *algún* token, no que fuera válido — con uno vencido o de un `JWT_SECRET_KEY` distinto, la UI mostraba listas vacías sin explicación (lo noté probando a mano en la Semana 6). Fix: interceptor de respuesta en `lib/api.ts` que, ante un 401 en una petición autenticada, limpia el token y redirige a `/login`. Verificado corrompiendo el token a mano y confirmando la redirección.

**Corrección de dependencias:** `psycopg2-binary` lo usa el backend directamente (driver de Postgres) pero solo estaba declarado en el grupo `ml` de `pyproject.toml` — funcionaba porque ambos grupos se instalan juntos hoy, pero era información incorrecta.

## Seguridad (post-plan)

Segunda pasada de revisión, esta vez enfocada en bugs y seguridad. Cada punto se verificó contra el Postgres real de `docker-compose`, no solo con tests.

**Bug real: race condition en las migraciones de K8s.** `infra/k8s/04-backend.yaml` corre `alembic upgrade head` en un initContainer por réplica (2 réplicas) — si arrancan a la vez, dos migraciones concurrentes contra el mismo Postgres es una carrera real (Alembic no tiene locking propio). Fix: `backend/scripts/migrate_with_lock.py`, que serializa con un advisory lock de Postgres antes de correr la migración — mismo patrón que ya usaba el scheduler. **Verificado con Postgres real:** dos procesos compitiendo por el mismo lock se serializaron exactamente como se espera (el segundo esperó a que el primero soltara el lock, no hubo ejecución concurrente).

**Bug de seguridad real: sin rate limiting en `/auth/login`.** Nada impedía fuerza bruta sobre contraseñas. Fix: `login_attempts` (tabla nueva, persistida en Postgres — no en memoria, para que sea correcto entre réplicas), bloqueo de 15 min tras 5 intentos fallidos por email. En el camino apareció un bug de tz-aware/naive datetimes (`can't subtract offset-naive and offset-aware datetimes` en el segundo intento fallido) — SQLite no preserva tzinfo en el round-trip a la base aunque la columna se declare `timezone=True`; se normaliza a mano en vez de confiar en el tipo de columna.

**Bug de seguridad real: `JWT_SECRET_KEY=change-me` no se bloqueaba en ningún lado.** El sistema arrancaba igual de "producción" con el secreto default público (cualquiera que vea este repo lo conoce). Fix: `Settings` rechaza arrancar si `ENVIRONMENT=production` y el secreto sigue siendo uno de los valores default conocidos.

**Row-Level Security como defensa en profundidad — con un hallazgo serio en el camino.** Hasta acá, el aislamiento multi-tenant dependía 100% de que cada query recordara `.filter(tenant_id=...)`. Se agregaron políticas de RLS en Postgres (`tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid`, fail-closed si no está seteado) para que un query que lo olvide siga sin poder ver filas de otro tenant.

Al probarlo con SQL crudo contra el Postgres real — sin pasar por la API, exactamente el escenario que esto debía cubrir — **las políticas no protegían nada**: `predictmaint`, el rol con el que se conecta la app, resultó ser SUPERUSUARIO (así lo crea la imagen de TimescaleDB vía `POSTGRES_USER`), y un superusuario de Postgres salta RLS siempre, sin excepción, sin importar `FORCE ROW LEVEL SECURITY`. Sin este hallazgo, el código habría quedado *pareciendo* seguro sin estarlo.

Fix real: un segundo rol, `predictmaint_app` (migración `52dbcb3527ef`), sin superusuario y sin `BYPASSRLS`, con permisos de datos pero no de DDL — es el que ahora usa el backend en runtime (`DATABASE_URL`); las migraciones siguen corriendo con el rol admin (`MIGRATION_DATABASE_URL`). Un segundo bug apareció al conectar así: varias rutas hacen más de un `commit()` por request (insertar la predicción, después la alerta), y `set_config(..., true)` ("is_local", equivalente a `SET LOCAL`) se descarta en el primer commit — el segundo `db.refresh(...)` fallaba con `invalid input syntax for type uuid: ''`. Se cambió a `set_config(..., false)` (dura toda la sesión/conexión) con reset explícito al final del request.

**Verificación final, conectado como `predictmaint_app` (el rol real de producción), con SQL crudo que "olvida" el filtro de tenant:**

```
-- sin fijar el tenant:
SELECT name FROM assets;
 name
------
(0 rows)                          -- bloqueado, aunque la tabla tenga filas de sobra

-- con el tenant fijado:
SELECT set_config('app.current_tenant_id', '<id-tenant-A>', false);
SELECT name FROM assets;
   name
-----------
 AssetA2                          -- solo la fila de ese tenant, ninguna de otro
```

No se ejecutó nada de esto en el cluster EKS de otro proyecto detectado en la Semana 8 — solo contra el Postgres de `docker-compose`.

## Testing (post-plan)

**Cobertura de backend medida y exigida, no solo "hay tests".** `pytest-cov` con `fail_under=95` en `pyproject.toml` — CI corre `pytest --cov --cov-report=term-missing` y rompe el build si baja del umbral (98.83% real). Cubre las ramas de dialecto Postgres/SQLite (RLS, WebSocket cross-réplica, advisory locks del scheduler) que antes solo se habían verificado a mano.

**Bug propio en CI, encontrado y corregido en el camino:** el `fail_under=95` se validó solo contra la máquina local, donde `ml/mlflow.db` (gitignored) ya existía de semanas anteriores. En un checkout limpio de CI ese archivo no existe, así que los tests que dependen del Model Registry se saltaban y la cobertura real caía a 91.35%, rompiendo el gate. En vez de bajar el umbral para taparlo, CI ahora entrena y registra el modelo champion real (`uv run python ml/pipelines/retrain.py`, ~20s con el dataset AI4I ya incluido en el repo) antes de correr pytest — verificado clonando el repo a un directorio limpio y reproduciendo el paso exacto de CI.

**Frontend: de 0% de cobertura a una suite real.** Vitest + Testing Library + jsdom, cubriendo el interceptor de axios, `AuthProvider`/`RequireAuth`, y los flujos de login/registro/lista de activos/alertas/reconexión de WebSocket (ver más abajo). De paso aparecieron 3 bugs reales de accesibilidad: labels sin `htmlFor`/`id` en `LoginPage`, `RegisterPage` y `AssetListPage`, encontrados porque `getByLabelText` de Testing Library no los encontraba — no se cambió la query, se arregló el componente.

## Arquitectura y observabilidad (post-plan, batch 3)

Tercera pasada, esta vez sobre huecos operativos de bajo riesgo: qué pasa cuando algo se cae, no qué tan rápido corre.

**El backend no tenía healthcheck en `docker-compose.yml`** (solo Postgres lo tenía) — `depends_on: backend` en `frontend`/`prometheus` significaba "arrancó el proceso", no "puede responder". Fix: `healthcheck` contra `/health` usando `python -c "urllib.request..."` (sin sumar `curl` a la imagen `python:3.12-slim`, que no lo trae); `frontend` y `prometheus` ahora dependen de `condition: service_healthy`. K8s (`infra/k8s/04-backend.yaml`) ya tenía el `readinessProbe`/`livenessProbe` equivalente desde la Semana 8 — este era el hueco de docker-compose específicamente. Verificado en vivo contra el stack real: `docker compose ps` reporta `backend ... (healthy)`.

**Cero reglas de alerting en Prometheus** — había dashboards en Grafana pero nada que avisara solo. Añadidas 3 reglas en `infra/observability/alert_rules.yml` (`BackendDown`, `HighErrorRate` sobre `http_requests_total{status="5xx"}`, `HighP99Latency > 2s` sobre `http_request_duration_highr_seconds_bucket` — el mismo histograma que documentó la cola p99 sin causa confirmada en `load-testing/RESULTS.md`; esta regla es la que la habría señalado en tiempo real). Verificado contra el Prometheus real: `curl localhost:9090/api/v1/rules` devuelve las 3 con `"health":"ok"`.

**Sin logging estructurado.** Todo salía como texto libre de uvicorn — imposible de filtrar en Loki por campo (solo por regex). Fix: `app/core/logging.py` (formatter JSON propio, sin sumar una dependencia nueva) más un middleware en `app/main.py` que loguea una línea por request con `method`/`path`/`status_code`/`duration_ms`/`tenant_id` (resuelto del JWT, best-effort — nunca afecta la respuesta real). **Verificado de punta a punta, no solo que imprime JSON:** una query real a la API de Loki (`{container=~"...backend.*"} | json | status_code = \`401\``) devolvió exactamente la request que generó ese 401 — confirma que el campo es filtrable de verdad, no solo que se ve bien en la consola.

**Frontend: un error de render tumbaba toda la app en blanco.** No había ningún error boundary — cualquier excepción durante un render (ej. un campo inesperado en una respuesta) dejaba la pantalla vacía sin ninguna pista. Fix: `components/ErrorBoundary.tsx` envolviendo `<App />` en `main.tsx`, con una UI de fallback y botón de recarga. Cubierto con test (`ErrorBoundary.test.tsx`, un componente que lanza a propósito).

**Frontend: el WebSocket de alertas no se reconectaba nunca.** Un reinicio del backend (redeploy, restart de contenedor) o cualquier corte de red dejaba el panel de alertas muerto en silencio hasta recargar la página a mano. Fix: `lib/useAlertsSocket.ts` reconecta con backoff exponencial (1s → 2s → 4s... tope 30s, reset al reconectar), salvo que el cierre sea por token inválido (código `4401` que ya usa `app/api/ws.py` — reintentar ahí solo repetiría el mismo rechazo). Verificado con un WebSocket falso y timers controlados (`useAlertsSocket.test.tsx`, 6 casos: backoff creciente, reset en `onopen`, no reintento en 4401, cleanup al desmontar) **y** en vivo: reiniciando el backend real con la sesión abierta en el navegador, la UI no se rompió y el error de conexión quedó en consola como se esperaba.

## Paginación real en el frontend (post-plan, batch 4)

`/assets` y `/alerts` ya soportaban `limit`/`offset` desde la pasada de optimización, pero el frontend nunca los usaba — pedía la tabla completa y punto. Wirearlo de verdad expuso un bug real, no solo faltaba UI.

**Bug real encontrado: `/assets` ordenaba por severidad al revés.** `Asset.status` es un `String` plano (`'ok'/'warning'/'critical'`), no un enum con orden propio en SQL — `order_by(Asset.status.desc())` comparaba el string tal cual, y alfabéticamente `"warning" > "ok" > "critical"`. El resultado quedaba enmascarado porque el frontend traía **todos** los activos (sin paginar) y los reordenaba en el cliente con un `STATUS_ORDER` propio — con paginación real (offset server-side) ese enmascaramiento desaparece: un activo crítico podía terminar en una página que la UI nunca pide. Fix: `_SEVERITY_RANK` (`CASE WHEN status='critical' THEN 0 WHEN status='warning' THEN 1 ELSE 2 END`) en `app/api/assets.py`, portable entre SQLite y Postgres. El reordenamiento en el cliente ahora es redundante y se eliminó — una sola fuente de verdad para el orden. Cubierto con test (`test_list_assets_orders_by_severity_not_alphabetically`, que fuerza los status directo en la DB porque la API no tiene forma de crear un activo ya en warning/critical) y **verificado contra el Postgres real**: con 25 activos y dos marcados a mano (`UPDATE assets SET status=...`), los dos aparecieron primero en la página 1 pese a estar en medio alfabéticamente.

**`AssetListPage`:** 20 activos por página, controles "Anterior"/"Siguiente". Como el backend devuelve un array plano (sin total), se pide `limit=PAGE_SIZE+1` para saber si hay página siguiente sin necesitar ese total — el elemento de más nunca se renderiza. `placeholderData: keepPreviousData` de React Query evita el parpadeo de "Cargando..." al cambiar de página (se ve la página anterior hasta que llega la nueva). Los controles solo se muestran si de verdad hay más de una página. Verificado en vivo contra el stack real (25 activos, 2 críticos/warning): página 1 con 20 ítems y los dos de mayor severidad primero, página 2 con los 5 restantes, "Siguiente" deshabilitado al llegar al final.

**Por qué el panel de alertas (la campana) NO se paginó:** su badge muestra el conteo total de alertas activas — paginar la lista visible rompería ese conteo (mostraría "ítems en esta página", no el total real) a menos que se sume un endpoint de conteo aparte, que es más cambio de API del que esto pedía. Hoy sigue acotado a 100 alertas activas (`limit=100`), razonable para un panel de notificaciones — una página dedicada de alertas con paginación propia sería la extensión natural si hace falta.

## Contrato de tipos compartido (post-plan, batch 5)

`frontend/src/types.ts` mantenía a mano las mismas formas que ya describían los schemas de Pydantic del backend — dos fuentes de verdad para lo mismo, con el riesgo real de que un campo cambiara en uno y no en el otro sin que nada lo avisara.

**Cómo funciona:** `backend/scripts/export_openapi.py` vuelca `app.openapi()` a `frontend/openapi.json` (no necesita Postgres ni MLflow corriendo — FastAPI arma el esquema a partir de las rutas y los modelos Pydantic, sin ejecutar ninguna query). `npm run codegen` (en `frontend/`, vía `openapi-typescript`) lo convierte en `frontend/src/lib/api-schema.ts` — tipos puros, sin código en runtime. `types.ts` quedó como una capa fina de alias sobre esos tipos generados (`export type Asset = components["schemas"]["AssetOut"]`, etc.) para no tener que tocar ninguno de los imports `from "../types"` que ya existían en el resto del frontend.

**Bug real encontrado al generar los tipos:** los schemas `*Out` de Pydantic (`AssetOut.status`, `AlertOut.severity`, `PredictionOut.prediction_type`) estaban declarados como `str` genérico, aunque cada uno tiene un `CheckConstraint` en Postgres que los restringe a un set fijo de valores (ej. `status IN ('ok', 'warning', 'critical')`). El `types.ts` escrito a mano SÍ tenía los union types correctos (`AssetStatus = "ok" | "warning" | "critical"`) — pero eso era conocimiento duplicado a mano, no derivado del backend; de haber generado los tipos tal cual estaban, se habría perdido esa precisión (`status: string` en vez del union). Fix: los tres campos pasaron a `Literal[...]` en los schemas (coincidiendo exactamente con cada `CheckConstraint`), incluyendo `PredictionRequest.prediction_type` (antes validado con `Field(pattern=...)`, un regex haciendo a mano lo que un `Literal` valida nativo). Ahora el backend es la única fuente de verdad, incluyendo la precisión de tipos que antes solo existía en el frontend.

**CI verifica que el contrato no se desactualice** (job `contract` en `.github/workflows/ci.yml`): regenera `openapi.json` + `api-schema.ts` desde cero y falla si el resultado no coincide byte a byte con lo commiteado — si alguien cambia un schema de Pydantic sin correr el codegen, el build se rompe en vez de dejar que el frontend quede mintiendo en silencio.

**Problema real encontrado instalando la herramienta de codegen, no relacionado con los tipos en sí:** `openapi-typescript@7.13.0` declara como peer dependency `typescript ^5.x`, y el proyecto ya usa `typescript ~6.0.2` — un conflicto de peer dependencies. `npm install --legacy-peer-deps` "resolvió" el conflicto pero cambiando el algoritmo de resolución de *todo* el árbol, lo que rompió silenciosamente cómo se resolvía `@testing-library/dom` (`@testing-library/react` re-exporta `screen`/`waitFor`/`within` desde ahí) — `tsc -b` fallaba con "no exported member 'screen'" en los 6 archivos de test que los usan. Se revirtió y se usó en cambio `"overrides": { "openapi-typescript": { "typescript": "$typescript" } }` en `package.json` — le dice a npm "para esta dependencia puntual, confiá en mi versión de typescript" sin tocar la resolución del resto del árbol. Verificado con `npm ci` (lo que corre el Dockerfile y CI, más estricto que `npm install`) desde un `node_modules` limpio.

## Backend síncrono a async (post-plan, batch 6)

La pasada más grande del backlog de arquitectura: SQLAlchemy 2.0 async (`asyncpg`/`aiosqlite` en vez de `psycopg2`/`pysqlite`) para el ciclo request/response completo de la API.

**Qué se convirtió y qué no, a propósito.** Todas las rutas (`assets`, `readings`, `alerts`, `auth`, `predictions`) pasaron a `async def` con `select()`/`await db.execute(...)` (SQLAlchemy 2.0 style — `AsyncSession` no soporta el `.query()` de 1.x en absoluto). El scheduler de reentrenamiento (`app/services/scheduler.py`, un `BackgroundScheduler` en su propio hilo de SO) y el `PostgresListener` del WebSocket (`app/services/ws_manager.py`, ya usa `psycopg2` crudo en su propio hilo) se dejaron **sin tocar** — corren fuera del ciclo request/response y no tienen nada que ganar volviéndose async; forzarlos habría sumado complejidad (`AsyncIOScheduler`, puentes async/sync) sin beneficio real. Alembic y `scripts/migrate_with_lock.py` ya tenían su propio engine independiente desde antes — tampoco los usa este cambio. `app/core/database.py` ahora expone dos motores: `async_engine` (el real, para las rutas) y `engine`/`SessionLocal` síncronos de siempre (para el scheduler y para que los tests que arman datos directo contra la base — `test_auth.py`, `test_assets_readings.py` — no tuvieran que cambiar una sola línea). bcrypt (login/registro) y las llamadas a MLflow (`mlflow.xgboost.load_model`, `model.predict_proba`) son bloqueantes/CPU-bound — se sacan del event loop con `run_in_threadpool` en vez de congelarlo para todas las requests en curso.

**Blast radius real, no el que parecía al empezar.** Mantener los nombres `engine`/`SessionLocal` síncronos intactos (en vez de renombrarlos) significó que de los 62 tests del backend, **59 pasaron sin tocarlos** — `TestClient` corre la app async transparentemente por debajo aunque el test en sí sea una función sync normal. Solo 3 necesitaron reescribirse: los 2 tests de `get_tenant_scoped_db` (ahora un generador async, se prueban con `AsyncMock` + `asyncio.run`) y el de `notify_alert` (ahora `async def`, ídem). Sin `pytest-asyncio` — el proyecto ya venía probando código async envolviendo con `asyncio.run(...)` dentro de tests sync normales (ver `test_ws_manager.py`), mismo patrón.

**Bug real #1: coverage.py no seguía la ejecución a través de SQLAlchemy async.** Los 62 tests pasaban en verde pero la cobertura cayó de 98.83% a 89% — no porque el código dejara de correr, sino porque `coverage.py` no sigue la traza cuando la ejecución cruza a un greenlet nuevo (SQLAlchemy usa `greenlet` como puente entre `await` y el driver DBAPI) ni a un hilo nuevo (`run_in_threadpool` usa hilos de verdad vía AnyIO). Fix: `concurrency = ["greenlet", "thread"]` en `[tool.coverage.run]` — cobertura volvió a 98.87%.

**Bug real #2: `asyncpg` rechaza lo que `psycopg2` truncaba en silencio.** `Tenant.created_at`, `User.created_at`, `Asset.created_at`, `Alert.triggered_at`, `Prediction.predicted_at` son columnas `TIMESTAMP WITHOUT TIME ZONE` (a propósito, ver comentario ya existente en `models/login_attempt.py`), pero sus defaults de Python (`datetime.now(UTC)`) son *aware*. `psycopg2` truncaba el tzinfo en silencio al bindear; `asyncpg` lo rechaza de plano con `"can't subtract offset-naive and offset-aware datetimes"` — rompía **cada** insert contra Postgres real (tenants, users, assets, alerts, predictions), encontrado recién al probar contra el stack de Docker, no en los tests contra SQLite. Fix: `to_naive_utc()`/`utc_now_naive()` en `app/models/types.py` (mismo archivo que ya tenía el `GUID` portable), usados como default en los 6 modelos afectados y para normalizar `SensorReading.time` (que viene de afuera, del payload del request, no de un default).

**Bug real #3, el más serio: Row-Level Security se rompía después del primer `commit()`.** `create_asset` (y cualquier ruta que haga `db.add(x); await db.commit(); await db.refresh(x)`) fallaba con `InvalidRequestError: Could not refresh instance` — pero el `INSERT` sí había committeado (confirmado con `SELECT` directo en `psql`: la fila estaba ahí). La causa: `get_db()` armaba el `AsyncSession` bindeado directo al *engine* (`async_sessionmaker(async_engine)()`), y en SQLAlchemy eso es "sin conexión fija" — cada `commit()` puede devolver la conexión física al pool, y el siguiente statement (el `refresh()`) toma una conexión *distinta* del pool que no tiene seteado `app.current_tenant_id` (ver `get_tenant_scoped_db`, la variable de sesión de la que depende RLS) — la política de `SELECT` bloqueaba la relectura como si fuera de otro tenant. El diseño original (`is_local=false`, "sobrevive a los commits") asumía implícitamente que la conexión física no cambiaba durante el request — cierto por suerte con el pool síncrono, falso con el pool async. Fix real: `get_db()` ahora hace `async with async_engine.connect() as conn:` una vez y bindea el `AsyncSession` a *esa* conexión (`AsyncSession(bind=conn, ...)`) en vez de al engine — la misma conexión física dura todo el request sin importar cuántos commits haga, sin importar cómo decida reciclar conexiones el pool entre requests distintos.

**Verificado de punta a punta contra Postgres real** (no solo pytest contra SQLite): registro de tenant → creación de activo → 5 lecturas AI4I → predicción real vía MLflow (corrida en threadpool) → alerta automática → `pg_notify` → `PostgresListener` → WebSocket → badge de la campana actualizándose en el navegador **sin recargar la página**, con una segunda predicción disparada mientras la sesión estaba abierta. Aislamiento RLS re-confirmado con SQL crudo como el rol restringido (`predictmaint_app`): 0 filas sin tenant seteado, filas correctas con el tenant correcto.

**El bonus real: la cola p99 sin explicar de la Semana 9 quedó resuelta.** `load-testing/RESULTS.md` documentaba un p99 de ~5900ms bajo 20 usuarios concurrentes que escalaba con la concurrencia (3 usuarios: ~1200ms máx; 20 usuarios: ~6700ms máx) y que dos hipótesis descartadas (pool de conexiones, `n_jobs` de XGBoost) no lograron explicar. Hipótesis nueva, consistente con lo que el async realmente cambia: con rutas síncronas, FastAPI corría el handler **completo** (incluida la inferencia) en un hilo del threadpool compartido (~40 de capacidad) — bajo concurrencia real, todas las requests competían por ese pool limitado de hilos aunque la mayoría de su trabajo fuera esperar a la base, no CPU. Con las rutas async, solo la inferencia de MLflow (lo único genuinamente bloqueante) usa un hilo — el resto corre en el event loop sin consumir threadpool. Corriendo la prueba de carga documentada, sin cambiar nada más (`docker compose up -d`, `uv run python -m locust -f load-testing/locustfile.py --host http://localhost:8000 --headless -u 20 -r 5 -t 45s`):

| Métrica | Antes (Semana 9, sync) | Después (async) |
|---|---|---|
| Mediana | 69 ms | 76 ms |
| p95 | 260 ms | 180 ms |
| **p99** | **~5900 ms** | **~360 ms** |
| Máx a 3 usuarios concurrentes | 1176 ms | 807 ms |

No queda 100% limpio con honestidad: 2 de 830 requests (0.24%) siguen golpeando un timeout de conexión aislado (`ConnectionResetError`) en vez de la cola sistemática de antes — consistente con la hipótesis original de `load-testing/RESULTS.md` sobre la capa de red virtualizada de Docker Desktop en Windows como variable de fondo, no con un problema de la aplicación.
