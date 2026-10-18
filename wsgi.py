"""WSGI entry point for Fact Box Consult web application.

Used by Gunicorn in production and Flask CLI in development.
"""
from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
