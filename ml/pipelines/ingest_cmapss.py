"""Ingesta del dataset NASA C-MAPSS (Turbofan Engine Degradation), subset FD001.

FD001: 100 motores, una condición operativa (nivel del mar), un modo de falla
(degradación de HPC) — el subset más simple de los 4, elegido para el primer
modelo de RUL (Semana 3-4). FD002-FD004 (múltiples condiciones/fallas) quedan
como extensión natural una vez que el pipeline funcione end-to-end.

A diferencia de AI4I 2020, aquí cada `unit_number` YA es una serie de tiempo
real hasta el fallo (o hasta el corte, en test) — no hace falta sintetizar
agrupación de activos. Por eso la salida es un dataframe plano listo para
entrenar (unit, cycle, settings, sensores, RUL), en vez de forzarlo al
esquema relacional producto (assets/sensor_readings) — ese mapeo se hace en
la Semana 5 cuando el backend sirva estos datos al dashboard.

Uso:
    uv run python ml/pipelines/ingest_cmapss.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "cmapss"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

COLUMNS = (
    ["unit_number", "cycle", "op_setting_1", "op_setting_2", "op_setting_3"]
    + [f"sensor_{i}" for i in range(1, 22)]
)

# Práctica estándar en la literatura de C-MAPSS: limitar el RUL de
# entrenamiento a un techo (la degradación real es despreciable muy lejos del
# fallo, y sin el clip el modelo intenta ajustar una región plana ruidosa).
RUL_CLIP = 125


def _read_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", header=None, names=COLUMNS)
    return df


def build_train(subset: str = "FD001") -> pd.DataFrame:
    df = _read_raw(RAW_DIR / f"train_{subset}.txt")
    max_cycle = df.groupby("unit_number")["cycle"].transform("max")
    df["RUL"] = (max_cycle - df["cycle"]).clip(upper=RUL_CLIP)
    df["subset"] = subset
    return df


def build_test(subset: str = "FD001") -> pd.DataFrame:
    """Test: cada unidad se corta antes del fallo; el RUL verdadero en la
    ÚLTIMA fila de cada unidad viene en RUL_<subset>.txt (una línea por unidad,
    en el mismo orden). Se usa solo para evaluar, nunca como feature."""
    df = _read_raw(RAW_DIR / f"test_{subset}.txt")
    true_rul = pd.read_csv(RAW_DIR / f"RUL_{subset}.txt", header=None, names=["RUL_true_at_cutoff"])
    true_rul["unit_number"] = true_rul.index + 1

    last_cycle = df.groupby("unit_number")["cycle"].transform("max")
    df = df.merge(true_rul, on="unit_number", how="left")
    # RUL en cada fila de test = RUL_true_at_cutoff + (cycles restantes hasta el corte)
    df["RUL"] = (df["RUL_true_at_cutoff"] + (last_cycle - df["cycle"])).clip(upper=RUL_CLIP)
    df["subset"] = subset
    return df.drop(columns=["RUL_true_at_cutoff"])


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    train = build_train("FD001")
    test = build_test("FD001")

    train.to_parquet(PROCESSED_DIR / "cmapss_fd001_train.parquet", index=False)
    test.to_parquet(PROCESSED_DIR / "cmapss_fd001_test.parquet", index=False)

    print(f"train FD001: {train.shape} -> {len(train['unit_number'].unique())} motores")
    print(f"test  FD001: {test.shape} -> {len(test['unit_number'].unique())} motores")


if __name__ == "__main__":
    main()
