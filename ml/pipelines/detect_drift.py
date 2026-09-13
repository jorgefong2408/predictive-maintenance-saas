"""Semana 7 — Detección de drift de datos con Evidently AI.

Compara la distribución de los 5 sensores de AI4I entre una ventana de
referencia (primera mitad del dataset, "época de entrenamiento") y una
ventana "actual". Como todavía no hay tráfico productivo real acumulado en
`sensor_readings`, la ventana actual se simula aplicando un corrimiento
sintético (recalibración de sensor) sobre la segunda mitad del dataset — la
mecánica de detección es real, el origen del dato "actual" es la
simplificación explícita de esta fase (en producción, `current` sería el
resultado de consultar las lecturas más recientes de la base).

Uso:
    uv run python ml/pipelines/detect_drift.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset

RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "ai4i2020.csv"
EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"

SENSOR_COLS = {
    "Air temperature [K]": "air_temperature",
    "Process temperature [K]": "process_temperature",
    "Rotational speed [rpm]": "rotational_speed",
    "Torque [Nm]": "torque",
    "Tool wear [min]": "tool_wear",
}

# Corrimiento sintético para simular una recalibración de sensor (ver docstring).
SYNTHETIC_SHIFT = {"torque": 6.0, "tool_wear_scale": 1.15}


def load_reference_and_current() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(RAW_PATH)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns=SENSOR_COLS)[list(SENSOR_COLS.values())]

    midpoint = len(df) // 2
    reference = df.iloc[:midpoint].reset_index(drop=True)
    current = df.iloc[midpoint:].reset_index(drop=True).copy()

    current["torque"] = current["torque"] + SYNTHETIC_SHIFT["torque"]
    current["tool_wear"] = current["tool_wear"] * SYNTHETIC_SHIFT["tool_wear_scale"]
    return reference, current


def run_drift_report(reference: pd.DataFrame, current: pd.DataFrame) -> dict:
    ref_dataset = Dataset.from_pandas(reference, data_definition=DataDefinition())
    cur_dataset = Dataset.from_pandas(current, data_definition=DataDefinition())

    report = Report(metrics=[DataDriftPreset()])
    result = report.run(reference_data=ref_dataset, current_data=cur_dataset)

    metrics = result.dict()["metrics"]
    column_drift = {}
    dataset_summary = {}
    for m in metrics:
        if m["metric_name"].startswith("ValueDrift"):
            column = m["config"]["column"]
            method = m["config"]["method"]
            threshold = float(m["config"]["threshold"])
            value = float(m["value"])
            # Los métodos basados en p-value (ej. K-S) marcan drift por DEBAJO
            # del umbral; los basados en distancia (Wasserstein, PSI, JS...)
            # lo marcan por ENCIMA. Evidently elige el método según los datos,
            # así que hay que leer la dirección de config en vez de asumirla.
            drifted = value < threshold if "p_value" in method else value > threshold
            column_drift[column] = {"method": method, "value": value, "threshold": threshold, "drifted": drifted}
        elif m["metric_name"].startswith("DriftedColumnsCount"):
            dataset_summary = {"drifted_columns": m["value"]["count"], "drifted_share": m["value"]["share"]}

    summary = {"dataset": dataset_summary, "columns": column_drift}

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    result.save_html(str(EVAL_DIR / "drift_report.html"))
    with open(EVAL_DIR / "drift_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    return summary


def main() -> None:
    reference, current = load_reference_and_current()
    summary = run_drift_report(reference, current)

    print(f"Columnas con drift: {summary['dataset']['drifted_columns']}/{len(summary['columns'])} "
          f"({summary['dataset']['drifted_share']:.0%})")
    for col, info in summary["columns"].items():
        flag = "DRIFT" if info["drifted"] else "ok"
        print(f"  {col:24s} {info['method']}={info['value']:.4g} (umbral {info['threshold']})  [{flag}]")
    print(f"\nReporte completo: {EVAL_DIR / 'drift_report.html'}")


if __name__ == "__main__":
    main()
