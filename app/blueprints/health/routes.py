"""Health and readiness check blueprint.

Provides an authenticated / unauthenticated health route that reports system readiness
without leaking internal connection strings, credentials, or internal details.
"""
import logging
from flask import Blueprint, jsonify
from sqlalchemy import text
from app.extensions import db

health_bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint confirming web process and database connectivity."""
    db_ok = False
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.error("Health check database probe failed: %s", exc)

    if db_ok:
        return jsonify({
            "status": "ok",
            "database": "connected"
        }), 200

    return jsonify({
        "status": "degraded",
        "database": "unavailable"
    }), 503
