"""Application configuration module.

Implements environment-specific configurations with fail-closed validation.
Enforces ADR-001: PostgreSQL only; SQLite is strictly prohibited.
"""
import os
from urllib.parse import urlparse


def clean_database_url(url: str | None) -> str:
    """Normalize PostgreSQL URL and validate that SQLite is never used."""
    if not url:
        raise ValueError("DATABASE_URL is not configured.")

    if url.startswith("sqlite"):
        raise ValueError(
            "SQLite is prohibited by project architecture (ADR-001). "
            "PostgreSQL is mandatory across all environments."
        )

    # Convert deprecated postgres:// prefix to postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


class BaseConfig:
    """Base configuration shared by all environments."""
    SECRET_KEY = os.getenv("SECRET_KEY", "insecure-default-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Cookie security defaults
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Media & Uploads (ADR-004: Cloudinary is media store, 10MB limit)
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")


class DevelopmentConfig(BaseConfig):
    """Configuration for local development."""
    DEBUG = True
    TESTING = False

    def __init__(self):
        super().__init__()
        raw_url = os.getenv("DATABASE_URL")
        self.SQLALCHEMY_DATABASE_URI = clean_database_url(raw_url)


class TestingConfig(BaseConfig):
    """Configuration for automated test suite.

    Requires an isolated test PostgreSQL database.
    """
    __test__ = False
    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False  # Allows straightforward testing of endpoints
    RATELIMIT_ENABLED = False  # Disables throttling during automated testing

    def __init__(self):
        super().__init__()
        test_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
        self.SQLALCHEMY_DATABASE_URI = clean_database_url(test_url)


class ProductionConfig(BaseConfig):
    """Fail-closed configuration for production deployment."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

    def __init__(self):
        super().__init__()
        # Validate SECRET_KEY
        secret = os.getenv("SECRET_KEY")
        if not secret or secret in ("insecure-default-change-me", "dev-secret-key-replace-in-prod-factbox-consult-2026"):
            raise ValueError("Production requires a strong, non-default SECRET_KEY.")
        self.SECRET_KEY = secret

        # Validate PostgreSQL URL
        prod_url = os.getenv("DATABASE_URL")
        cleaned_url = clean_database_url(prod_url)

        parsed = urlparse(cleaned_url)
        if parsed.hostname in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Production DATABASE_URL must not point to localhost.")

        self.SQLALCHEMY_DATABASE_URI = cleaned_url


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(config_name: str | None = None) -> BaseConfig:
    """Retrieve and instantiate configuration by environment name."""
    name = config_name or os.getenv("FLASK_CONFIG", "development").lower()
    config_class = CONFIG_MAP.get(name)
    if not config_class:
        raise ValueError(f"Unknown configuration environment: '{name}'. Choose from: {list(CONFIG_MAP.keys())}")
    return config_class()
