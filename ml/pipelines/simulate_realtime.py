"""Simulador de lecturas de sensores en tiempo real.

Reproduce el histórico procesado (ml/data/processed/sensor_readings.parquet)
como si fuera un stream en vivo: agrupa las lecturas por timestamp original y
las va emitiendo a un ritmo configurable, re-timestampando cada lote al
momento de emisión. Semana 5 conecta este stream al endpoint de ingesta del
backend; por ahora corre standalone (NDJSON a stdout o a un archivo) para
poder probar el pipeline sin depender del backend.

Uso:
    uv run python ml/pipelines/simulate_realtime.py --speed 60 --limit 500
    uv run python ml/pipelines/simulate_realtime.py --speed 60 --out live_feed.ndjson
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def load_readings() -> pd.DataFrame:
    path = PROCESSED_DIR / "sensor_readings.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No se encontró {path}. Corre antes ingest_ai4i.py")
    df = pd.read_parquet(path)
    return df.sort_values("time").reset_index(drop=True)


def stream_batches(df: pd.DataFrame, limit: int | None = None) -> Iterator[list[dict]]:
    """Agrupa las lecturas por timestamp original y las emite en orden, una
    "tick" de simulación por grupo, con el timestamp reescrito al momento real
    de emisión (para que se vea como un feed en vivo, no un replay histórico)."""
    grouped = df.groupby("time", sort=True)
    emitted = 0
    for _, batch in grouped:
        now = datetime.now(UTC).isoformat()
        records = [
            {
                "time": now,
                "asset_id": str(row.asset_id),
                "tenant_id": str(row.tenant_id),
                "sensor_name": row.sensor_name,
                "value": float(row.value),
                "unit": row.unit,
            }
            for row in batch.itertuples(index=False)
        ]
        yield records
        emitted += 1
        if limit is not None and emitted >= limit:
            return


def run(speed: float, limit: int | None, sink: TextIO) -> None:
    df = load_readings()
    # `speed` = factor de aceleración respecto al intervalo original (1 min/lote).
    delay = 60.0 / speed if speed > 0 else 0.0
    for batch in stream_batches(df, limit=limit):
        for record in batch:
            sink.write(json.dumps(record) + "\n")
        sink.flush()
        if delay:
            time.sleep(delay)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speed", type=float, default=60.0, help="Factor de aceleración (60 = 1 min real -> 1s)")
    parser.add_argument("--limit", type=int, default=None, help="Número máximo de lotes (timestamps) a emitir")
    parser.add_argument("--out", type=str, default=None, help="Archivo NDJSON de salida (default: stdout)")
    args = parser.parse_args()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            run(args.speed, args.limit, fh)
    else:
        run(args.speed, args.limit, sys.stdout)


if __name__ == "__main__":
    main()
