# Plan Detallado — Plataforma SaaS de Mantenimiento Predictivo

## 1. Visión del proyecto

Construir una plataforma completa que ingiera datos de sensores (vibración, temperatura, corriente, presión), detecte anomalías, prediga la vida útil remanente (RUL — Remaining Useful Life) de un activo/máquina, y presente todo en un dashboard multi-tenant en tiempo real. El objetivo no es solo "un modelo de ML", sino un **producto de software completo, desplegado, testeado y documentado** que demuestre dominio full-stack + ML + infraestructura.

**Por qué este proyecto funciona para portafolio:**
- Combina ingeniería de datos, ML aplicado, backend, frontend, DevOps y MLOps — pocos candidatos muestran las seis capas juntas.
- Usa datasets públicos reconocidos (no inventados), lo que le da credibilidad técnica.
- Es demostrable con una demo en vivo y métricas reales, no solo capturas de pantalla.

---

## 2. Alcance

**Incluye:**
- Ingesta y almacenamiento de series temporales de sensores.
- Modelos de detección de anomalías y predicción de RUL.
- API de inferencia con autenticación y multi-tenancy (varias "empresas" gestionando sus propios activos).
- Dashboard en tiempo real con alertas.
- Pipeline de reentrenamiento y monitoreo de drift (MLOps básico).
- Infraestructura contenedorizada, CI/CD y despliegue en la nube.

**No incluye (fuera de alcance, para no perder foco):**
- Hardware real / sensores físicos (se simulan con datasets y generadores de eventos).
- Facturación/pagos reales (se puede simular el concepto de "planes" sin pasarela de pago).
- Soporte multi-idioma o accesibilidad exhaustiva (nice-to-have, no crítico).

---

## 3. Fuentes de datos (elige 1-2 para no dispersarte)

| Dataset | Qué aporta | Uso principal |
|---|---|---|
| **NASA C-MAPSS** (Turbofan Engine Degradation) | Series de sensores de motores hasta el fallo | Predicción de RUL (regresión) |
| **CWRU Bearing Data Center** | Vibración de rodamientos con y sin falla | Clasificación de tipo de falla |
| **AI4I 2020 Predictive Maintenance (UCI)** | Dataset tabular sintético con temperatura, torque, velocidad y modos de falla | Baseline rápido, clasificación de falla |
| **Microsoft Azure Predictive Maintenance (Kaggle)** | Telemetría + fallas + mantenimientos históricos | Simulación de flujo operativo realista |

Recomendación: empezar con **AI4I 2020** (simple, tabular, rápido de iterar) para tener un MVP funcional pronto, y luego incorporar **C-MAPSS** para el modelo de RUL más sofisticado (series temporales), que es el que más impresiona técnicamente.

---

## 4. Arquitectura general

```
                         ┌─────────────────────┐
                         │   Frontend (React)  │
                         │  Dashboard + Alertas │
                         └──────────┬───────────┘
                                    │ HTTPS / WebSocket
                         ┌──────────▼───────────┐
                         │   API Gateway/Backend │
                         │  FastAPI + Auth (JWT) │
                         └──────────┬───────────┘
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
        ┌────────▼───────┐ ┌────────▼────────┐ ┌───────▼────────┐
        │  PostgreSQL +   │ │  Servicio de    │ │  MLflow Model   │
        │  TimescaleDB    │ │  Inferencia ML  │ │  Registry       │
        │ (series tiempo) │ │  (FastAPI aparte│ │ (tracking +     │
        │                 │ │  o mismo backend)│ │  versionado)   │
        └─────────────────┘ └──────────────────┘ └────────────────┘
                 │
        ┌────────▼───────┐
        │ Pipeline batch  │
        │ de reentreno    │
        │ (cron / Celery) │
        └─────────────────┘
```

Todo corre en contenedores Docker, orquestado con Kubernetes (o docker-compose en fase de desarrollo), con CI/CD en GitHub Actions y despliegue en AWS.

---

## 5. Stack tecnológico por capa

**Datos y ML:**
Python 3.11+, pandas, numpy, scikit-learn, PyTorch (para LSTM/autoencoder), XGBoost, MLflow (tracking + registry de modelos), Evidently AI (detección de drift).

**Backend:**
FastAPI, Pydantic v2, SQLAlchemy 2.0 + Alembic (migraciones), PostgreSQL con extensión TimescaleDB, Redis (cache y colas), Celery (jobs de reentrenamiento), autenticación JWT con scoping multi-tenant.

**Frontend:**
React + Vite, TypeScript, TailwindCSS, shadcn/ui, Recharts (gráficas de series temporales), React Query, WebSocket para alertas en tiempo real.

**Infraestructura:**
Docker, Kubernetes (K3s local o AWS EKS), Helm charts, GitHub Actions (CI/CD), Terraform (opcional, para IaC), Prometheus + Grafana (métricas), Loki o CloudWatch (logs).

---

## 6. Cronograma por fases (10 semanas, ritmo part-time)

### Semana 0 — Diseño
- Elegir dataset(s) definitivos.
- Diseñar el esquema de datos (tablas de activos, lecturas de sensores, eventos de falla, alertas).
- Bocetar el dashboard (wireframes simples).
- Crear el repositorio (monorepo: `/backend`, `/frontend`, `/ml`, `/infra`).
- Definir los "casos de uso" que vas a demostrar (ej. "Máquina X mostró vibración anómala y el sistema predijo falla en 12 días").

### Semanas 1-2 — Pipeline de datos
- Scripts de ingesta y limpieza del dataset elegido.
- Notebook de EDA (distribución de sensores, correlaciones, ciclos de vida de los activos).
- Diseño del esquema de series temporales en TimescaleDB.
- Carga inicial de datos históricos + simulador de "nuevas lecturas" en tiempo real (para que la demo se vea viva).

### Semanas 3-4 — Modelado ML
- Modelo baseline (regla simple / regresión lineal) como punto de comparación.
- Modelo de detección de anomalías (Isolation Forest y/o Autoencoder).
- Modelo de predicción de RUL (XGBoost como primera opción; LSTM si quieres subir el nivel técnico).
- Evaluación con métricas claras: RMSE/MAE para RUL, precision/recall/F1 para anomalías.
- Tracking de experimentos en MLflow, selección y registro del mejor modelo.

### Semana 5 — Backend / API
- Endpoints principales: activos, lecturas, predicciones, alertas, autenticación.
- Servicio de inferencia que carga el modelo desde el MLflow Model Registry.
- Multi-tenancy vía `tenant_id` en cada tabla y en el token JWT.
- Tests unitarios con pytest.

### Semana 6 — Frontend
- Autenticación y layout base.
- Vista de lista de activos con estado (OK / advertencia / crítico).
- Gráfica de series temporales por activo con la predicción de RUL superpuesta.
- Panel de alertas en tiempo real (WebSocket).

### Semana 7 — MLOps
- Job programado de reentrenamiento (Celery beat o cron).
- Detección de drift de datos con Evidently AI.
- Endpoint para disparar reentrenamiento manual y ver historial de versiones de modelo.

### Semana 8 — Infraestructura y despliegue
- Dockerfiles de cada servicio + docker-compose para desarrollo.
- Manifiestos de Kubernetes (o Helm chart) para producción.
- Pipeline CI/CD en GitHub Actions: lint → test → build imagen → push a registry → deploy.
- Despliegue en AWS (EKS o, si quieres ahorrar costos, ECS Fargate) con dominio propio y HTTPS.

### Semana 9 — Observabilidad y pruebas
- Métricas de sistema con Prometheus + dashboard en Grafana.
- Logs centralizados.
- Pruebas de carga básicas (Locust) sobre el endpoint de inferencia.
- Pruebas end-to-end del flujo completo.

### Semana 10 — Documentación y pulido para portafolio
- README profesional: arquitectura (diagrama con Mermaid), decisiones técnicas, resultados de los modelos con gráficas.
- Video demo corto (2-3 min) mostrando el flujo completo.
- Deploy público accesible (aunque sea con un dataset de ejemplo) para que cualquiera lo pruebe.
- Limpieza final de código, licencias, y un `CONTRIBUTING.md`/`ARCHITECTURE.md` si quieres mostrar madurez de proyecto open source.

---

## 7. Estructura de repositorio sugerida

```
predictive-maintenance-saas/
├── backend/
│   ├── app/
│   │   ├── api/          # routers FastAPI
│   │   ├── models/       # modelos SQLAlchemy
│   │   ├── schemas/      # Pydantic
│   │   ├── services/     # lógica de negocio + inferencia
│   │   └── core/         # config, auth, seguridad
│   ├── tests/
│   └── Dockerfile
├── ml/
│   ├── notebooks/        # EDA y experimentación
│   ├── pipelines/        # entrenamiento reproducible
│   ├── models/           # artefactos versionados (o link a MLflow)
│   └── evaluation/
├── frontend/
│   ├── src/
│   └── Dockerfile
├── infra/
│   ├── k8s/               # manifiestos o Helm chart
│   ├── terraform/         # opcional
│   └── docker-compose.yml
├── .github/workflows/     # CI/CD
└── README.md
```

---

## 8. Métricas de éxito a mostrar en el portafolio

- **Modelo:** RMSE/MAE del modelo de RUL comparado contra el baseline; precision/recall del detector de anomalías.
- **Sistema:** latencia promedio del endpoint de inferencia, throughput soportado en la prueba de carga.
- **Producto:** captura de pantalla o GIF del dashboard detectando una anomalía y disparando una alerta en tiempo real.

Estos tres tipos de métricas (modelo, sistema, producto) son justo lo que distingue un proyecto de portafolio "juguete" de uno que se ve como un producto real.

---

## 9. Siguiente paso sugerido

Empezar por la **Semana 0**: fijar el dataset, diseñar el esquema de datos y dejar el repo con la estructura base lista. Si quieres, en el siguiente paso te ayudo a diseñar el esquema de base de datos exacto (tablas, tipos, relaciones) o a armar el primer notebook de EDA sobre el dataset que elijas.
