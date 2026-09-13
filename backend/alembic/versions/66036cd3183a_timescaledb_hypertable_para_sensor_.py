"""timescaledb hypertable para sensor_readings

Revision ID: 66036cd3183a
Revises: 695a492d67dd
Create Date: 2026-09-13 16:29:15.757197

Solo aplica sobre Postgres. En SQLite (desarrollo local sin Docker, ver
README) `sensor_readings` queda como una tabla normal — mismo esquema
lógico, sin las ventajas de particionado de TimescaleDB.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66036cd3183a'
down_revision: Union[str, Sequence[str], None] = '695a492d67dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute(
        """
        SELECT create_hypertable(
            'sensor_readings', 'time',
            partitioning_column => 'asset_id',
            number_partitions => 4,
            if_not_exists => TRUE,
            migrate_data => TRUE
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_sensor_readings_asset_time ON sensor_readings (asset_id, time DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sensor_readings_tenant_time ON sensor_readings (tenant_id, time DESC)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS idx_sensor_readings_tenant_time")
    op.execute("DROP INDEX IF EXISTS idx_sensor_readings_asset_time")
    # TimescaleDB no soporta "des-convertir" una hypertable de vuelta a una
    # tabla normal; un rollback real de esta migración implica recrear
    # sensor_readings desde cero (fuera de alcance de un downgrade simple).
