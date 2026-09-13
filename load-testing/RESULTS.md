# Prueba de carga — `POST /assets/{id}/predictions` (Semana 9)

Contra el stack de `docker-compose` (Postgres+TimescaleDB y MLflow reales, no SQLite local):

```bash
docker compose up -d
uv run python -m locust -f load-testing/locustfile.py --host http://localhost:8000 \
  --headless -u 20 -r 5 -t 45s --csv load-testing/results
```

(`python -m locust` en vez del script `locust`: en esta máquina una política de Application Control de Windows bloquea el ejecutable generado por pip/uv — el módulo corre igual.)

## Iteración 1 — línea base (20 usuarios, 45s)

| Métrica | Valor |
|---|---|
| Requests | 602 (0 fallos) |
| Throughput | ~20 req/s |
| Mediana | 120 ms |
| p95 | 260 ms |
| **p99** | **~6000 ms** |

**Hallazgo #1 (confirmado):** `predict_failure_probability` resolvía el alias `champion` contra el Model Registry de MLflow — una llamada HTTP — en **cada** predicción, no solo al arrancar. Fix en `backend/app/services/inference.py::_resolve_champion_version`: cachear la versión resuelta 30s (`ALIAS_CACHE_TTL_SECONDS`). Sigue recargando sin downtime tras un reentrenamiento (UC5), solo que con hasta 30s de staleness en vez de una llamada de red por request.

## Iteración 2 — tras cachear el alias (20 usuarios, 45s)

| Métrica | Antes | Después |
|---|---|---|
| Mediana | 120 ms | **69 ms** ✅ |
| Throughput | ~20 req/s | ~21 req/s |
| p99 | ~6000 ms | ~5900 ms (sin cambio) |

La mediana mejoró de forma clara y reproducible (la llamada de red de sobra sí se estaba pagando en el camino típico). La cola p98-p99 de varios segundos **no se movió** — señal de que tiene una causa distinta a la que se acababa de arreglar.

## Hipótesis descartadas para la cola p99

Se probaron dos causas candidatas obvias, ambas cambios legítimos que se dejaron en el código por ser buenas prácticas, pero **ninguna cerró la cola**:

1. **Pool de conexiones de SQLAlchemy** (`backend/app/core/database.py`): el default (5 + 10 overflow) parecía corto para 20 requests concurrentes haciendo varias idas a la base cada uno. Se subió a `pool_size=20, max_overflow=20` sobre Postgres. Resultado: p99 ~5600ms — sin cambio significativo.
2. **XGBoost usando todos los cores por predicción** (`n_jobs=-1` por defecto): para una fila a la vez no aporta nada y bajo concurrencia real cada request compite por todos los cores. Se fijó `n_jobs=1` al cargar el modelo. Resultado: p99 ~5600ms — sin cambio significativo.

## Lo que sí se confirmó: la cola escala con la concurrencia

| Usuarios concurrentes | Requests | Max latencia |
|---|---|---|
| 3 | 89 | 1176 ms |
| 20 | ~780 | ~6700 ms |

No es un evento periódico de duración fija (ej. un job en background cada N segundos) — crece con la carga concurrente, lo cual apunta a algún tipo de contención (de threads, o de la capa de red virtualizada de Docker Desktop en Windows) en vez de una causa puntual en el código de la aplicación.

## Conclusión honesta

Se encontró y corrigió un problema real medible (llamada de red evitable en el hot path — el tipo de hallazgo que una prueba de carga saca a la luz y pytest, corriendo secuencial, no puede detectar). La cola p99 restante quedó **diagnosticada pero no resuelta**: se descartaron dos hipótesis razonables con evidencia, y el patrón (crece con concurrencia, no es periódico) queda documentado para quien retome esto — el siguiente paso sería perfilar el proceso bajo carga (ej. `py-spy dump` contra el contenedor) o repetir la misma prueba en un host Linux nativo para descartar la virtualización de red de Docker Desktop en Windows como variable.
