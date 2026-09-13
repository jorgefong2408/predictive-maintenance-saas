# Esquema de datos

Diseño para Postgres + extensión TimescaleDB. Multi-tenancy por columna `tenant_id` en cada tabla de dominio (no por schema-per-tenant, para simplicidad operativa) + scoping obligatorio en la capa de servicios del backend y claim `tenant_id` en el JWT.

## Diagrama entidad-relación

```mermaid
erDiagram
    TENANTS ||--o{ USERS : "tiene"
    TENANTS ||--o{ ASSETS : "posee"
    ASSETS ||--o{ SENSOR_READINGS : "genera"
    ASSETS ||--o{ FAILURE_EVENTS : "sufre"
    ASSETS ||--o{ PREDICTIONS : "recibe"
    ASSETS ||--o{ ALERTS : "dispara"
    USERS ||--o{ ALERTS : "reconoce"

    TENANTS {
        uuid id PK
        text name
        text slug UK
        text plan
        timestamptz created_at
    }
    USERS {
        uuid id PK
        uuid tenant_id FK
        text email UK
        text hashed_password
        text role
        timestamptz created_at
    }
    ASSETS {
        uuid id PK
        uuid tenant_id FK
        text name
        text asset_type
        text external_ref
        text status
        jsonb metadata
        timestamptz installed_at
        timestamptz created_at
    }
    SENSOR_READINGS {
        timestamptz time PK
        uuid asset_id PK_FK
        uuid tenant_id FK
        text sensor_name PK
        double value
        text unit
    }
    FAILURE_EVENTS {
        uuid id PK
        uuid tenant_id FK
        uuid asset_id FK
        timestamptz occurred_at
        text failure_type
        text source
        text notes
    }
    PREDICTIONS {
        uuid id PK
        uuid tenant_id FK
        uuid asset_id FK
        timestamptz predicted_at
        text model_name
        text model_version
        text prediction_type
        double value
        jsonb metadata
    }
    ALERTS {
        uuid id PK
        uuid tenant_id FK
        uuid asset_id FK
        timestamptz triggered_at
        text severity
        text alert_type
        text message
        timestamptz acknowledged_at
        uuid acknowledged_by FK
        timestamptz resolved_at
    }
```

## Notas de diseño

**`sensor_readings` en formato largo (narrow/long), no ancho.**
Cada fila es `(time, asset_id, sensor_name, value)` en vez de una columna por sensor. Razón: los datasets objetivo tienen esquemas de sensores distintos (AI4I: 5 señales tabulares; C-MAPSS: 21 sensores + 3 settings operacionales; CWRU: vibración a alta frecuencia). El formato largo permite ingerir cualquiera sin migraciones de esquema, a costa de más filas — mitigado por el particionado nativo de TimescaleDB (hypertable sobre `time`).

**Hypertable:** `SELECT create_hypertable('sensor_readings', 'time', partitioning_column => 'asset_id', number_partitions => 4);` — particiona por tiempo y por activo para acelerar consultas por rango + por máquina, que es el patrón de acceso dominante del dashboard.

**`status` en `assets` es una columna cacheada/derivada** (no fuente de verdad): se recalcula cuando llega una nueva predicción o alerta, para que el listado de activos no tenga que agregar `alerts`/`predictions` en cada request.

**`predictions.prediction_type`** distingue `rul_days` (regresión, C-MAPSS) de `failure_probability`/`anomaly_score` (clasificación/detección de anomalías, AI4I). Misma tabla, distintos tipos — evita duplicar estructura para dos problemas de ML relacionados.

**Trazabilidad de modelo:** `predictions.model_name` + `model_version` apuntan al MLflow Model Registry (fuente de verdad de artefactos y métricas); Postgres solo guarda la referencia, no el modelo.

**Mapeo desde AI4I 2020** (`ml/data/raw/ai4i2020.csv`):

AI4I 2020 es tabular: cada una de sus 10 000 filas tiene un `Product ID` único y no trae identificador de máquina real ni timestamps — es una snapshot, no una serie temporal por activo. Para poder ejercitar el modelo de datos orientado a series de tiempo (y que el dashboard muestre tendencias reales por máquina), la ingesta **agrupa filas consecutivas de `UDI` en un número fijo de activos sintéticos** (`N_ASSETS = 12`, ver `ml/pipelines/ingest_ai4i.py`), simulando una planta con 12 máquinas (`Mill-01` … `Mill-12`) cada una con ~833 lecturas secuenciales (1/minuto). Esta es una decisión explícita para la fase MVP; el modelo de series temporales "real" (sin necesidad de sintetizar agrupación) llega con C-MAPSS en la Semana 3-4.

- Cada chunk de filas consecutivas → un `asset` (`Mill-XX`); `Type` (L/M/H) más frecuente del chunk → `assets.metadata.quality_variant`
- `Air temperature [K]`, `Process temperature [K]`, `Rotational speed [rpm]`, `Torque [Nm]`, `Tool wear [min]` → 5 filas en `sensor_readings` por fila original, con timestamp secuencial dentro del activo asignado
- `Machine failure`, `TWF`, `HDF`, `PWF`, `OSF`, `RNF` → `failure_events.failure_type` cuando alguna bandera es 1, con `occurred_at` = timestamp sintético de esa fila

## Índices previstos
- `sensor_readings`: índice compuesto implícito por hypertable en `(asset_id, time DESC)`.
- `assets`: índice único en `(tenant_id, external_ref)`.
- `alerts`: índice en `(tenant_id, resolved_at)` para el panel de alertas activas.
- `users`: índice único en `email` (global) — un email pertenece a un solo tenant en este diseño simplificado.
