# Predictive Maintenance SaaS

Plataforma multi-tenant de mantenimiento predictivo: ingiere datos de sensores, detecta anomalías, predice la vida útil remanente (RUL) de activos industriales y presenta todo en un dashboard en tiempo real con alertas.

Este repositorio sigue el plan documentado en [`docs/PLAN.md`](docs/PLAN.md), ejecutado fase por fase (Semana 0 a Semana 10).

## Estado actual

- [x] Semana 0 — Diseño (dataset, esquema de datos, estructura de repo, casos de uso)
- [ ] Semanas 1-2 — Pipeline de datos
- [ ] Semanas 3-4 — Modelado ML
- [ ] Semana 5 — Backend / API
- [ ] Semana 6 — Frontend
- [ ] Semana 7 — MLOps
- [ ] Semana 8 — Infraestructura y despliegue
- [ ] Semana 9 — Observabilidad y pruebas
- [ ] Semana 10 — Documentación y pulido

## Datasets

| Fase | Dataset | Estado |
|---|---|---|
| MVP (clasificación de falla, baseline tabular) | [AI4I 2020 Predictive Maintenance (UCI)](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset) | Descargado en `ml/data/raw/ai4i2020.csv` |
| Fase avanzada (RUL, series temporales) | NASA C-MAPSS (Turbofan Engine Degradation) | Pendiente (Semana 3-4) |

## Estructura del repositorio

```
predictive-maintenance-saas/
├── backend/     # FastAPI + SQLAlchemy + Auth JWT multi-tenant
├── ml/          # Notebooks, pipelines de entrenamiento, evaluación
├── frontend/    # React + Vite + TypeScript + Tailwind
├── infra/       # docker-compose, Kubernetes/Helm, Terraform
├── docs/        # Plan, decisiones, esquema de datos, casos de uso
└── .github/workflows/  # CI/CD
```

## Stack

Ver [`docs/PLAN.md#5-stack-tecnológico-por-capa`](docs/PLAN.md) para el detalle completo por capa (datos/ML, backend, frontend, infraestructura).

## Cómo correr el proyecto (desarrollo local)

_Se documentará al final de la Semana 1-2 una vez exista `docker-compose.yml` funcional._
