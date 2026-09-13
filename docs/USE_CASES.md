# Casos de uso a demostrar

Definidos en Semana 0 para guiar el diseño de datos, modelos y UI. Cada uno debe ser reproducible en la demo final.

## UC1 — Detección de anomalía y alerta en tiempo real
Un simulador inyecta lecturas de `air_temperature`, `process_temperature`, `torque` y `rotational_speed` para el activo **Mill-07** (tenant `acme-manufacturing`). El Isolation Forest entrenado sobre AI4I 2020 marca una combinación fuera de distribución (score de anomalía por debajo del umbral). El backend crea un registro en `alerts` con severidad `warning` y lo empuja por WebSocket al dashboard sin recargar la página.

**Demuestra:** ingesta en tiempo real, inferencia online, alertas push, UI reactiva.

## UC2 — Predicción de vida útil remanente (RUL)
Para un motor turbofan del dataset C-MAPSS (**Unit-24**), el modelo de RUL (XGBoost o LSTM) predice **12 ciclos restantes** en un punto donde el valor real conocido (post-hoc) era de ~15 ciclos. Se muestra la serie de sensores con la curva de degradación y la predicción superpuesta, junto con el intervalo de confianza.

**Demuestra:** modelado de series temporales, calidad de predicción vs. baseline, visualización de RUL.

## UC3 — Aislamiento multi-tenant
Dos empresas (`acme-manufacturing` y `borealis-industrial`) usan la plataforma simultáneamente. Un operador autenticado con un JWT de `acme-manufacturing` nunca puede ver, listar ni recibir alertas de activos de `borealis-industrial`, incluso conociendo IDs internos.

**Demuestra:** seguridad multi-tenant, scoping por `tenant_id` en API y base de datos.

## UC4 — Ciclo de vida de un activo (dashboard)
Un operador inicia sesión, ve la lista de sus activos con semáforo de estado (**OK / warning / critical**) ordenado por severidad, abre el detalle de **Mill-07**, y ve: (a) la serie de tiempo de sus sensores clave, (b) la predicción de RUL superpuesta, (c) el historial de alertas del activo.

**Demuestra:** flujo de producto end-to-end, UX de dashboard operativo.

## UC5 — Reentrenamiento y control de drift (MLOps)
Evidently AI detecta drift estadístico en la distribución de `tool_wear` del último mes de datos simulados respecto al set de entrenamiento original. Esto dispara (manual o automáticamente vía Celery beat) un job de reentrenamiento; el nuevo modelo se registra en MLflow Model Registry con una nueva versión, y el servicio de inferencia recarga el modelo en producción sin downtime.

**Demuestra:** MLOps básico, monitoreo de drift, versionado de modelos, actualización sin downtime.

## UC6 — Trazabilidad de una predicción
Para cualquier predicción mostrada en el dashboard, se puede inspeccionar: qué versión de modelo la generó (link a MLflow), con qué features, y en qué timestamp fue calculada — vía el registro en la tabla `predictions`.

**Demuestra:** explicabilidad/auditoría, madurez de producto ML.
