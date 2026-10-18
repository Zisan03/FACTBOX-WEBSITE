"""Pytest test suite configuration and fixtures.

Mandates an isolated PostgreSQL database for test execution (ADR-001).
SQLite is prohibited.
"""
import os
import pytest
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db


@pytest.fixture(scope="session")
def test_db_url():
    """Verify and return the PostgreSQL test database URL."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL must be defined in the environment. "
            "Testing requires an isolated PostgreSQL database (ADR-001)."
        )
    if "sqlite" in url.lower():
        raise RuntimeError(
            "SQLite detected in TEST_DATABASE_URL! "
            "ADR-001 strictly prohibits SQLite in all environments including tests."
        )
    return url


@pytest.fixture(scope="session")
def app(test_db_url):
    """Create application instance configured for testing."""
    application = create_app("testing")

    with application.app_context():
        # Verify connection to PostgreSQL test database
        db.session.execute(text("SELECT 1"))
        yield application


@pytest.fixture
def client(app):
    """Test client fixture."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """CLI runner fixture."""
    return app.test_cli_runner()
