"""rol restringido predictmaint_app sin bypass de RLS

Revision ID: 52dbcb3527ef
Revises: 83dc2610fe35
Create Date: 2026-09-13 18:34:48.797206

Row-Level Security (migración anterior) no protegía nada en la práctica: el
rol con el que se conecta la app (`predictmaint`, creado por la imagen de
TimescaleDB vía POSTGRES_USER) es SUPERUSUARIO — y un superusuario de
Postgres siempre salta RLS, sin excepción, sin importar FORCE ROW LEVEL
SECURITY. Se descubrió probando con SQL crudo contra el Postgres real de
docker-compose: un SELECT sin filtro de tenant devolvía todas las filas de
todos los tenants, con o sin `set_config('app.current_tenant_id', ...)`.

Esta migración crea un segundo rol, `predictmaint_app`, SIN superusuario y
SIN BYPASSRLS, con permisos de datos (no de DDL) sobre las tablas — este es
el rol que debe usar la app en runtime (`DATABASE_URL` en docker-compose.yml
e infra/k8s/04-backend.yaml). Las migraciones siguen corriendo con el rol
admin (`MIGRATION_DATABASE_URL`), que sí necesita poder hacer DDL.

La contraseña viene de la variable de entorno APP_DB_PASSWORD (nunca
hardcodeada en el archivo) — si no está definida, usa un default obviamente
inseguro pensado solo para docker-compose.yml en local.
"""
import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '52dbcb3527ef'
down_revision: Union[str, Sequence[str], None] = '83dc2610fe35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "predictmaint_app"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    password = os.environ.get("APP_DB_PASSWORD", "predictmaint_app_insecure_default")

    bind.execute(
        text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    CREATE ROLE {APP_ROLE} LOGIN PASSWORD :pwd;
                ELSE
                    ALTER ROLE {APP_ROLE} PASSWORD :pwd;
                END IF;
            END
            $$;
            """
        ),
        {"pwd": password},
    )

    # Explícitamente NO superusuario, NO bypassrls, NO createrole/createdb —
    # solo puede hacer lo que los GRANT de abajo le permiten.
    op.execute(f"ALTER ROLE {APP_ROLE} NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB")

    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    # Para que las tablas de migraciones FUTURAS también queden accesibles
    # sin tener que acordarse de repetir estos GRANT cada vez.
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE}")
