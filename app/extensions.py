"""Application extensions module.

Initializes SQLAlchemy, Flask-Migrate, and Flask-WTF CSRF protection.
No SQLite fallback is permitted (ADR-001).
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
