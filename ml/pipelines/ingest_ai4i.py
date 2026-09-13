"""Ingesta y limpieza del dataset AI4I 2020 Predictive Maintenance.

AI4I 2020 es tabular: cada fila tiene un `Product ID` único, sin identificador
de máquina real ni timestamp. Para obtener series de tiempo por activo (y que
el dashboard muestre tendencias, no puntos sueltos), esta ingesta agrupa
`N_ASSETS` bloques consecutivos de `UDI` en activos sintéticos ("Mill-01" ...
"Mill-12"), cada uno con lecturas secuenciales espaciadas 1 minuto. Ver
docs/DATA_SCHEMA.md para el detalle de esta decisión.

Salida (docs/DATA_SCHEMA.md):
  - assets: una fila por activo sintético
  - sensor_readings: formato largo (time, asset_id, sensor_name, value)
  - failure_events: una fila por cada bandera de falla activa (TWF/HDF/PWF/OSF/RNF)

Uso:
    uv run python ml/pipelines/ingest_ai4i.py
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "ai4i2020.csv"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

SENSOR_COLUMNS = {
    "Air temperature [K]": ("air_temperature", "K"),
    "Process temperature [K]": ("process_temperature", "K"),
    "Rotational speed [rpm]": ("rotational_speed", "rpm"),
    "Torque [Nm]": ("torque", "Nm"),
    "Tool wear [min]": ("tool_wear", "min"),
}

FAILURE_FLAGS = {
    "TWF": "tool_wear_failure",
    "HDF": "heat_dissipation_failure",
    "PWF": "power_failure",
    "OSF": "overstrain_failure",
    "RNF": "random_failure",
}

DEMO_TENANT_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "acme-manufacturing.predictmaint")
SERIES_START = datetime(2025, 1, 1, tzinfo=UTC)
SAMPLE_INTERVAL = timedelta(minutes=1)
N_ASSETS = 12


def load_raw() -> pd.DataFrame:
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró {RAW_PATH}. Corre primero la descarga (docs/PLAN.md, Semana 0)."
        )
    df = pd.read_csv(RAW_PATH)
    df.columns = [c.strip() for c in df.columns]
    return df.sort_values("UDI").reset_index(drop=True)


def assign_synthetic_assets(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa bloques consecutivos de filas en N_ASSETS activos sintéticos."""
    df = df.copy()
    chunk_id = (df.index * N_ASSETS) // len(df)
    df["asset_name"] = chunk_id.map(lambda i: f"Mill-{i + 1:02d}")
    df["asset_id"] = df["asset_name"].map(
        lambda name: str(uuid.uuid5(DEMO_TENANT_ID, name))
    )
    df["seq_in_asset"] = df.groupby("asset_id").cumcount()
    df["time"] = df["seq_in_asset"].apply(lambda i: SERIES_START + i * SAMPLE_INTERVAL)
    return df


def build_assets(df: pd.DataFrame) -> pd.DataFrame:
    def majority_type(s: pd.Series) -> str:
        return s.mode().iat[0]

    grouped = (
        df.groupby(["asset_id", "asset_name"])["Type"]
        .agg(majority_type)
        .reset_index()
        .rename(columns={"Type": "quality_variant"})
    )
    grouped["tenant_id"] = str(DEMO_TENANT_ID)
    grouped["asset_type"] = "cnc_milling_machine"
    grouped["external_ref"] = grouped["asset_name"]
    grouped["status"] = "ok"
    return grouped.rename(columns={"asset_name": "name"})[
        ["asset_id", "tenant_id", "name", "asset_type", "external_ref", "quality_variant", "status"]
    ]


def build_sensor_readings(df: pd.DataFrame) -> pd.DataFrame:
    long_frames = []
    for col, (sensor_name, unit) in SENSOR_COLUMNS.items():
        frame = df[["time", "asset_id", col]].rename(columns={col: "value"})
        frame["sensor_name"] = sensor_name
        frame["unit"] = unit
        long_frames.append(frame)

    readings = pd.concat(long_frames, ignore_index=True)
    readings["tenant_id"] = str(DEMO_TENANT_ID)
    return readings[["time", "asset_id", "tenant_id", "sensor_name", "value", "unit"]].sort_values(
        ["asset_id", "time", "sensor_name"]
    )


def build_failure_events(df: pd.DataFrame) -> pd.DataFrame:
    events = []
    for flag_col, failure_type in FAILURE_FLAGS.items():
        flagged = df[df[flag_col] == 1]
        for _, row in flagged.iterrows():
            events.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "tenant_id": str(DEMO_TENANT_ID),
                    "asset_id": row["asset_id"],
                    "occurred_at": row["time"],
                    "failure_type": failure_type,
                    "source": "historical_dataset",
                }
            )
    return pd.DataFrame(events)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    raw = load_raw()
    raw = assign_synthetic_assets(raw)

    assets = build_assets(raw)
    readings = build_sensor_readings(raw)
    failures = build_failure_events(raw)

    assets.to_parquet(PROCESSED_DIR / "assets.parquet", index=False)
    readings.to_parquet(PROCESSED_DIR / "sensor_readings.parquet", index=False)
    failures.to_parquet(PROCESSED_DIR / "failure_events.parquet", index=False)

    print(f"assets:          {len(assets):>7} filas -> {PROCESSED_DIR / 'assets.parquet'}")
    print(f"sensor_readings: {len(readings):>7} filas -> {PROCESSED_DIR / 'sensor_readings.parquet'}")
    print(f"failure_events:  {len(failures):>7} filas -> {PROCESSED_DIR / 'failure_events.parquet'}")


if __name__ == "__main__":
    main()
