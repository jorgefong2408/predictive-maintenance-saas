# Terraform (no implementado)

El plan (`docs/PLAN.md`, sección 5) marca Terraform como opcional para IaC de la infraestructura de AWS. Se dejó deliberadamente sin implementar: solo tiene sentido escribirlo contra una cuenta de AWS real, con sus credenciales — la misma razón por la que no hay despliegue real (ver "Por qué no hay despliegue real a AWS" en el README raíz). `infra/k8s/` documenta la misma topología en manifiestos planos, listos para cuando exista esa cuenta.
