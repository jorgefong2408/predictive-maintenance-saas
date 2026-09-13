-- Esquema inicial: Postgres + TimescaleDB.
-- Corresponde al diseño en docs/DATA_SCHEMA.md.
-- Se ejecuta contra una base con la extensión timescaledb ya creada
-- (ver infra/docker-compose.yml, imagen timescale/timescaledb).

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE tenants (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        text NOT NULL,
    slug        text NOT NULL UNIQUE,
    plan        text NOT NULL DEFAULT 'free',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email           text NOT NULL UNIQUE,
    hashed_password text NOT NULL,
    role            text NOT NULL DEFAULT 'operator' CHECK (role IN ('admin', 'operator', 'viewer')),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE assets (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            text NOT NULL,
    asset_type      text NOT NULL,
    external_ref    text,
    status          text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'warning', 'critical')),
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    installed_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, external_ref)
);

-- Hypertable en formato largo: (time, asset_id, sensor_name) -> value.
-- Formato largo elegido porque distintos datasets (AI4I, C-MAPSS, CWRU)
-- traen conjuntos de sensores distintos; ver docs/DATA_SCHEMA.md.
CREATE TABLE sensor_readings (
    time        timestamptz NOT NULL,
    asset_id    uuid NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sensor_name text NOT NULL,
    value       double precision NOT NULL,
    unit        text,
    PRIMARY KEY (time, asset_id, sensor_name)
);

SELECT create_hypertable(
    'sensor_readings', 'time',
    partitioning_column => 'asset_id',
    number_partitions => 4,
    if_not_exists => TRUE
);

CREATE INDEX idx_sensor_readings_asset_time ON sensor_readings (asset_id, time DESC);
CREATE INDEX idx_sensor_readings_tenant_time ON sensor_readings (tenant_id, time DESC);

CREATE TABLE failure_events (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    asset_id        uuid NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    occurred_at     timestamptz NOT NULL,
    failure_type    text NOT NULL,
    source          text NOT NULL DEFAULT 'historical_dataset',
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_failure_events_asset ON failure_events (asset_id, occurred_at DESC);

CREATE TABLE predictions (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    asset_id        uuid NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    predicted_at    timestamptz NOT NULL DEFAULT now(),
    model_name      text NOT NULL,
    model_version   text NOT NULL,
    prediction_type text NOT NULL CHECK (prediction_type IN ('rul_days', 'anomaly_score', 'failure_probability')),
    value           double precision NOT NULL,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_predictions_asset_time ON predictions (asset_id, predicted_at DESC);

CREATE TABLE alerts (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    asset_id        uuid NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    triggered_at    timestamptz NOT NULL DEFAULT now(),
    severity        text NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    alert_type      text NOT NULL,
    message         text NOT NULL,
    acknowledged_at timestamptz,
    acknowledged_by uuid REFERENCES users(id),
    resolved_at     timestamptz
);

CREATE INDEX idx_alerts_tenant_active ON alerts (tenant_id, resolved_at) WHERE resolved_at IS NULL;
