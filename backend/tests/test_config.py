"""Bug de seguridad real: nada impedía arrancar en "producción" con el
secreto de JWT default. Ver app/core/config.py::Settings._reject_insecure_secret_in_production."""

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_production_with_default_secret_is_rejected():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(environment="production", jwt_secret_key="change-me", database_url="sqlite:///:memory:")


def test_production_with_real_secret_is_accepted():
    settings = Settings(
        environment="production", jwt_secret_key="a-real-random-secret-value", database_url="sqlite:///:memory:"
    )
    assert settings.jwt_secret_key == "a-real-random-secret-value"


def test_development_with_default_secret_is_allowed():
    """El check solo se activa con ENVIRONMENT=production — dev local y
    docker-compose.yml (que no lo setean) siguen funcionando sin tocar nada."""
    settings = Settings(jwt_secret_key="change-me", database_url="sqlite:///:memory:")
    assert settings.environment == "development"
    assert settings.jwt_secret_key == "change-me"
