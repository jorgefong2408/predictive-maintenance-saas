"""row level security para aislamiento multi-tenant

Revision ID: 83dc2610fe35
Revises: 34fd3b03da45
Create Date: 2026-09-13 18:27:45.133253

Solo aplica sobre Postgres (RLS no existe en SQLite — dev local sin Docker
sigue dependiendo únicamente del filtro a nivel de aplicación, como hasta
ahora). Defensa en profundidad: hasta este punto, el aislamiento entre
tenants dependía 100% de que CADA query en app/api/*.py recordara filtrar
por `tenant_id`. Un query nuevo que lo olvide sería una fuga de datos entre
tenants sin nada que lo detecte. Con esto, aunque el filtro de la aplicación
falle, Postgres bloquea la fila igual.

`users`, `tenants` y `login_attempts` quedan FUERA a propósito:
- `login_attempts` es por email, no por tenant (no sabemos el tenant hasta
  después de encontrar al usuario).
- `users` se busca por email en /auth/login ANTES de saber el tenant —
  aplicar RLS ahí crearía el mismo problema del huevo y la gallina. El email
  ya es único globalmente, así que no hay fuga real posible en ese lookup.
- `tenants` no tiene tenant_id (es la entidad tenant en sí).

Requiere FORCE ROW LEVEL SECURITY: por defecto Postgres exime al DUEÑO de
la tabla de sus propias políticas. El dueño (`predictmaint`, quien corre las
migraciones) además es SUPERUSUARIO — y un superusuario de Postgres siempre
salta RLS sin importar FORCE (esto se descubrió probando con SQL crudo
contra el Postgres real: sin esto, con o sin FORCE, todas las filas de
todos los tenants eran visibles). Por eso la app en runtime se conecta con
`predictmaint_app` (migración `52dbcb3527ef`), un rol aparte sin
superusuario y sin BYPASSRLS — el único para el que FORCE realmente importa.

`NULLIF(..., '')` antes del cast a uuid: el valor de la sesión puede llegar
como NULL (nunca seteado) o como '' (reseteado explícitamente al terminar
un request, ver app/api/deps.py::get_tenant_scoped_db) — un `''::uuid` sin
este NULLIF explota con "invalid input syntax for type uuid" en vez de
simplemente no matchear ninguna fila (bug real encontrado en la misma
prueba contra Postgres).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '83dc2610fe35'
down_revision: Union[str, Sequence[str], None] = '34fd3b03da45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_SCOPED_TABLES = ["assets", "sensor_readings", "failure_events", "predictions", "alerts"]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table in TENANT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table in TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
