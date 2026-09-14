"""Tipos de columna portables entre SQLite (desarrollo local) y Postgres
(producción, Semana 8) — ver decisión en README ("Base de datos local")."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import CHAR, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class GUID(TypeDecorator):
    """UUID nativo en Postgres, CHAR(36) en cualquier otro dialecto (SQLite)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return str(value) if dialect.name != "postgresql" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return str(value)


def new_uuid() -> str:
    return str(uuid.uuid4())


def to_naive_utc(dt: datetime) -> datetime:
    """`created_at`/`triggered_at`/`predicted_at` etc. son columnas
    `TIMESTAMP WITHOUT TIME ZONE` (a propósito: todo lo que escribe esta app
    ya es UTC, no hace falta que Postgres lo sepa). `psycopg2` truncaba en
    silencio el tzinfo de un `datetime` aware al bindearlo contra una
    columna naive; `asyncpg` (backend async) lo rechaza de plano con "can't
    subtract offset-naive and offset-aware datetimes" -- rompía CADA insert
    contra Postgres real (tenants, users, assets, alerts, predictions),
    encontrado migrando. Esto hace explícito el mismo truncamiento que
    psycopg2 hacía solo, convirtiendo primero a UTC real por si el input
    trae otro offset."""
    return dt.astimezone(UTC).replace(tzinfo=None) if dt.tzinfo is not None else dt


def utc_now_naive() -> datetime:
    return to_naive_utc(datetime.now(UTC))
