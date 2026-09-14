from app.core.database import _to_async_url


def test_to_async_url_rewrites_sqlite_driver():
    assert _to_async_url("sqlite:///./predictmaint.db") == "sqlite+aiosqlite:///./predictmaint.db"


def test_to_async_url_rewrites_psycopg2_driver():
    assert _to_async_url("postgresql+psycopg2://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db"


def test_to_async_url_rewrites_bare_postgresql_scheme():
    assert _to_async_url("postgresql://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db"
