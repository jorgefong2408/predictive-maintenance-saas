# Kubernetes (Semana 8)

Manifiestos planos (alternativa a Helm que permite el plan) que reflejan la misma topología que `docker-compose.yml`: Postgres+TimescaleDB, MLflow, backend, frontend, más un `Ingress` para exponerlo con dominio propio y TLS.

**Estado: escritos, no aplicados contra ningún cluster.** Antes de `kubectl apply -f infra/k8s/`:

1. Reemplazar `ghcr.io/OWNER/REPO/...` en `04-backend.yaml` y `05-frontend.yaml` por las imágenes reales que publica `.github/workflows/ci.yml`.
2. Crear el secret real (`01-secrets.yaml` es una plantilla, no commitear valores reales — ver comentario en el archivo).
3. Tener un ingress controller + cert-manager instalados en el cluster, y un dominio real apuntando al Load Balancer (`06-ingress.yaml` usa `predictmaint.example.com` como placeholder).
4. Reconstruir la imagen del frontend con `VITE_API_URL`/`VITE_WS_URL` apuntando al dominio real — quedan quemadas en el bundle en build time (ver `frontend/Dockerfile`), no son variables de entorno en runtime.

**Por qué no se aplicó nada aquí:** esta máquina de desarrollo ya tiene un `kubectl` configurado contra un cluster EKS real de otro proyecto (`recomendaciones-cluster`). Aplicar manifiestos nuevos ahí sin más sería tocar infraestructura ajena y generar gasto en una cuenta de AWS que no es de este proyecto — exactamente el tipo de acción que requiere confirmación explícita antes de ejecutarla. El despliegue real a un cluster (de este proyecto o el que se decida usar) queda como una decisión consciente del usuario, no de esta sesión.
