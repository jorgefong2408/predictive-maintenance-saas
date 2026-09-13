"""Semana 11 (optimización) — el scheduler de reentrenamiento debe coordinarse
entre réplicas vía un advisory lock de Postgres (ver app/services/scheduler.py
para el porqué: infra/k8s/04-backend.yaml corre 2 réplicas). Los tests corren
sobre SQLite (ver conftest.py), así que la rama de Postgres se verifica
mockeando la conexión — el objetivo es probar la lógica de coordinación, no
un Postgres real (eso ya lo cubrió la Semana 8 corriendo el stack completo)."""

from unittest.mock import MagicMock, patch

from app.services import scheduler


def test_sqlite_path_retrains_directly_without_lock():
    """En SQLite (dev local sin Docker) no hay con quién competir por el lock."""
    with patch("app.services.scheduler.engine") as mock_engine, patch(
        "app.services.scheduler._do_retrain"
    ) as mock_do_retrain:
        mock_engine.dialect.name = "sqlite"
        scheduler._run_retrain_job()
        mock_do_retrain.assert_called_once()
        mock_engine.connect.assert_not_called()


def test_postgres_path_retrains_when_lock_acquired():
    with patch("app.services.scheduler.engine") as mock_engine, patch(
        "app.services.scheduler._do_retrain"
    ) as mock_do_retrain:
        mock_engine.dialect.name = "postgresql"
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = True
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        scheduler._run_retrain_job()

        mock_do_retrain.assert_called_once()
        # se pidió el lock y se liberó (2 llamadas a execute: lock + unlock)
        assert mock_conn.execute.call_count == 2


def test_postgres_path_skips_when_another_replica_holds_the_lock():
    with patch("app.services.scheduler.engine") as mock_engine, patch(
        "app.services.scheduler._do_retrain"
    ) as mock_do_retrain:
        mock_engine.dialect.name = "postgresql"
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = False  # otra réplica ya lo tiene
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        scheduler._run_retrain_job()

        mock_do_retrain.assert_not_called()
        # solo se intentó adquirir el lock, nunca se liberó uno que no se tenía
        assert mock_conn.execute.call_count == 1
