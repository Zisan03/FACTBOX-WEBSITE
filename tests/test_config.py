"""Tests for application configuration and fail-closed validation."""
import pytest
from app.config import clean_database_url, ProductionConfig, DevelopmentConfig, TestingConfig, get_config


def test_sqlite_prohibition():
    """Verify that any SQLite URL immediately raises a ValueError."""
    with pytest.raises(ValueError, match="SQLite is prohibited"):
        clean_database_url("sqlite:///app.db")

    with pytest.raises(ValueError, match="SQLite is prohibited"):
        clean_database_url("sqlite+pysqlite:///:memory:")


def test_postgres_url_normalization():
    """Verify that legacy postgres:// scheme is rewritten to postgresql://."""
    raw = "postgres://user:pass@ep-server.render.com/factbox"
    cleaned = clean_database_url(raw)
    assert cleaned.startswith("postgresql://")


def test_production_fails_without_strong_secret(monkeypatch):
    """Verify that ProductionConfig fails closed if SECRET_KEY is default or weak."""
    monkeypatch.setenv("SECRET_KEY", "insecure-default-change-me")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@ep-db.render.com:5432/factbox_prod")

    with pytest.raises(ValueError, match="strong, non-default SECRET_KEY"):
        ProductionConfig()


def test_production_fails_with_localhost_database(monkeypatch):
    """Verify that ProductionConfig fails closed if DATABASE_URL points to localhost."""
    monkeypatch.setenv("SECRET_KEY", "very-strong-production-key-here-123456789")
    monkeypatch.setenv("DATABASE_URL", "postgresql://factbox_user:pass@localhost:5432/factbox_prod")

    with pytest.raises(ValueError, match="must not point to localhost"):
        ProductionConfig()


def test_production_valid_configuration(monkeypatch):
    """Verify that ProductionConfig succeeds with remote DB and strong secret."""
    monkeypatch.setenv("SECRET_KEY", "super-secret-unique-production-key-999")
    monkeypatch.setenv("DATABASE_URL", "postgresql://prod_user:secret@dpg-abc123.oregon-postgres.render.com/factbox_prod")

    config = ProductionConfig()
    assert config.SESSION_COOKIE_SECURE is True
    assert config.DEBUG is False
    assert config.TESTING is False


def test_development_config_loads():
    """Verify that DevelopmentConfig instantiates successfully."""
    config = get_config("development")
    assert config.DEBUG is True
    assert "postgresql" in config.SQLALCHEMY_DATABASE_URI
