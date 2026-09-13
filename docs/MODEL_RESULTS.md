# Resultados de modelado (Semana 3-4)

Todos los experimentos están trackeados en MLflow (`ml/mlflow.db`, backend SQLite local — correr `uv run mlflow ui --backend-store-uri sqlite:///ml/mlflow.db` para explorarlos). Reproducible con:

```bash
uv run python ml/pipelines/train_ai4i_models.py
uv run python ml/pipelines/train_cmapss_rul.py
```

## Clasificación de falla — AI4I 2020 (`ai4i-failure-detection`)

Split estratificado 75/25 sobre las 10 000 filas originales (desbalance real: ~3.4% de fallas).

| Modelo | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|
| Baseline (DummyClassifier, clase mayoritaria) | 0.000 | 0.000 | 0.000 | — |
| Isolation Forest (no supervisado) | 0.140 | 0.141 | 0.140 | 0.776 |
| **XGBoost** (supervisado, `scale_pos_weight≈28.5`) | **0.465** | **0.859** | **0.603** | **0.975** |

**Lectura:** el baseline confirma que accuracy sería una métrica engañosa (>96% solo con predecir "sin falla"). Isolation Forest, sin ver la etiqueta, ya separa señal de ruido muy por encima del azar (ROC-AUC 0.78) — útil como red de seguridad ante modos de falla no vistos. XGBoost supervisado es el modelo candidato a producción: recall de 0.86 (detecta 86% de las fallas reales) a costa de precision moderada (46%), un trade-off razonable para mantenimiento predictivo donde una falla no detectada es mucho más cara que una alerta falsa. Registrado en el Model Registry como `ai4i-failure-classifier` v1.

## Predicción de RUL — NASA C-MAPSS FD001 (`cmapss-rul-fd001`)

Split oficial del dataset (100 motores train hasta el fallo, 100 motores test cortados antes del fallo con RUL verdadero vía `RUL_FD001.txt`). RUL limitado a un techo de 125 ciclos (práctica estándar en la literatura de C-MAPSS).

| Modelo | RMSE (ciclos) | MAE (ciclos) |
|---|---|---|
| Baseline (regresión lineal, señales crudas) | 20.75 | 16.64 |
| **XGBoost** (`n_estimators=300, max_depth=5`) | **17.06** | **12.02** |

**Lectura:** XGBoost reduce el error absoluto medio en ~4.6 ciclos frente al baseline lineal (-28%). En línea con lo reportado en la literatura de FD001 para modelos sin ventaneo temporal ni redes recurrentes (RMSE típico 15-20 con XGBoost/Random Forest; LSTM con feature engineering más sofisticado baja a ~12-15). Extensión natural marcada en el plan: LSTM sobre ventanas deslizantes de ciclos, si se quiere subir el nivel técnico del RUL. Registrado en el Model Registry como `cmapss-rul-regressor` v1.

## Hallazgos de EDA que informaron el modelado

Ver [`ml/notebooks/01_eda_ai4i2020.ipynb`](../ml/notebooks/01_eda_ai4i2020.ipynb):
- `air_temperature` y `process_temperature` altamente correlacionadas (redundantes).
- Dataset fuertemente desbalanceado (~3.4% fallas) → descartada accuracy como métrica.
- `tool_wear` muestra el patrón de "sierra" más interpretable como ciclo de vida del activo en AI4I.

Para C-MAPSS FD001, 4 de 21 sensores (`sensor_1`, `sensor_5`, `sensor_10`, `sensor_16`, `sensor_18`, `sensor_19`) resultaron constantes bajo la única condición operativa del subset y se descartaron automáticamente en `train_cmapss_rul.py::select_features` (std ≈ 0 en train).

## Próximos pasos (fuera de alcance de Semana 3-4)

- Servir estos modelos vía el servicio de inferencia del backend (Semana 5), cargándolos desde el MLflow Model Registry por nombre + versión (`predictions.model_name` / `model_version` en `docs/DATA_SCHEMA.md`).
- Monitoreo de drift con Evidently AI y reentrenamiento automático (Semana 7) — ver abajo.
- Opcional: LSTM sobre C-MAPSS con ventanas deslizantes para bajar el RMSE de RUL.

## MLOps (Semana 7): drift, reentrenamiento y versionado

**Drift** (`ml/pipelines/detect_drift.py`, reporte en `ml/evaluation/drift_summary.json`): compara los 5 sensores de AI4I entre la primera y segunda mitad del dataset. Como todavía no hay tráfico productivo acumulado, la "ventana actual" incluye un corrimiento sintético (`torque += 6`, `tool_wear *= 1.15`) para poder demostrar la mecánica de detección con una señal real y conocida — no es drift real de producción. Evidently eligió *Wasserstein distance (normed)* como método (no K-S) por el tamaño de muestra; el drift se marca cuando la distancia supera el umbral 0.1, dirección opuesta a un p-value. Resultado: 4/5 columnas marcadas, incluyendo `torque` (el corrimiento inyectado) — ver `ml/pipelines/detect_drift.py` para el detalle de por qué la dirección del umbral depende del método.

**Reentrenamiento con promoción condicional** (`ml/pipelines/retrain.py`, patrón "champion" vía alias de MLflow): cada corrida registra una versión nueva, pero solo mueve el alias `champion` — el que sirve `backend/app/services/inference.py` — si el F1 nuevo supera al del champion actual. Un reentrenamiento nunca degrada el modelo en producción en silencio. El backend expone esto como `POST /admin/models/ai4i-failure-classifier/retrain` (dispara manualmente) y `GET /admin/models/{name}/versions` (historial completo con métricas), y un `BackgroundScheduler` (`backend/app/services/scheduler.py`) lo corre cada `RETRAIN_INTERVAL_HOURS` (default 24h) — sustituto documentado de Celery beat mientras no hay Docker/Redis en este entorno (ver README).

Como el dataset de AI4I es estático, "reentrenar" hoy repite el mismo proceso sobre los mismos datos (F1 idéntico, por eso normalmente no promueve). La mecánica de versionado/promoción es la pieza real y reusable; conectarla a datos frescos de `sensor_readings` es un paso de ingeniería de features fuera de alcance de esta fase.
