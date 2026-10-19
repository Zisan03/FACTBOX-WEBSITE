"""Pytest test suite configuration and fixtures.

Mandates an isolated PostgreSQL database for test execution (ADR-001).
SQLite is prohibited.
"""
import os
import pytest
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models.admin import AdminUser


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
    """Test client fixture with CSRF disabled for standard testing."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """CLI runner fixture."""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Database session fixture that cleans up all tables after each test."""
    with app.app_context():
        yield db.session
        db.session.rollback()
        # Clean up database tables in reverse dependency order
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def sample_admin(db_session):
    """Create and return a sample active admin user."""
    admin = AdminUser(
        email="testadmin@factboxconsult.com",
        is_active=True,
    )
    admin.set_password("SecurePassword2026!")
    db_session.add(admin)
    db_session.commit()
    return admin
