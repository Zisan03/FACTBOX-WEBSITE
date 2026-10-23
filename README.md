# Fact Box Consult

> **Corporate Web Platform & Media Management System**  
> An audiovisual media, documentary research, and creative communications consultancy.

---

## Overview

**Fact Box Consult** delivers high-impact documentary filmmaking, investigative field research, institutional photography, and communications strategy across West Africa. This repository houses the official corporate web platform, client portfolio showcase, and administrative content management system.

The platform is engineered with a secure Python/Flask architecture, relational PostgreSQL storage, Cloudinary media optimization, and a lightweight, high-performance vanilla frontend designed for modern responsiveness and accessibility.

---

## Key Features

### Public Platform
- **Modern Homepage & Showcase**: Dynamic hero with high-resolution photo gallery showcasing field projects and documentary productions.
- **Structured Portfolio**: Filtered showcases for video productions (responsive YouTube embeds with lazy loading) and photography collections.
- **Institutional Trust Ribbon**: Global partner ribbon highlighting collaborations with organizations such as Mercy Corps, International Alert, Malaria Consortium, and international development agencies.
- **Service Catalog**: Comprehensive breakdown of audiovisual, investigative, and strategic communications capabilities.
- **Secure Contact Channel**: Server-validated, CSRF-protected, and rate-limited enquiry form storing messages in PostgreSQL with automated notification pipelines.

### Administration CMS
- **Authentication & Security Suite**: Session-based authentication with bcrypt password hashing, in-dashboard password updates, single-use signed token password reset via email, and an emergency CLI recovery tool.
- **Content & Media Management**: Upload, categorize, order, and toggle project media with automated Cloudinary cloud synchronization and orphaned asset cleanup.
- **Partner Logo Management**: Manage collaborating organization logos and visibility directly from the administrative dashboard.
- **Enquiry Inbox**: Centralized dashboard to review, triage, filter, and respond to incoming client enquiries.

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.12+, Flask (Application Factory & Blueprints) |
| **Database** | PostgreSQL 15+ (mandatory across development, testing, and production) |
| **ORM & Migrations** | SQLAlchemy 2.0, Alembic, Flask-Migrate |
| **Security & Forms** | Flask-WTF (CSRF), Flask-Limiter, Flask-Talisman, itsdangerous, bcrypt |
| **Frontend** | Semantic HTML5, Vanilla CSS3 (Custom Design System tokens), Vanilla JavaScript (No heavy frameworks) |
| **Cloud & Media** | Cloudinary SDK (portfolio & partner logos), YouTube Embeds (video streams) |
| **Testing** | pytest, pytest-flask (PostgreSQL integration test suite) |
| **Production WSGI** | Gunicorn (`Procfile` configured for container & PaaS deployment) |

---

## Documentation & Governance

Full architectural, requirements, and engineering governance documents are organized in the [`docs/`](docs/) directory:

- [**docs/PRD.md**](docs/PRD.md) — Product Requirements Document, scope boundaries, and feature matrices.
- [**docs/ARCHITECTURE.md**](docs/ARCHITECTURE.md) — System topology, security boundaries, and component interaction.
- [**docs/ARCHITECTURE_DECISIONS.md**](docs/ARCHITECTURE_DECISIONS.md) — Architecture Decision Records (ADRs).
- [**docs/DATABASE_SCHEMA.md**](docs/DATABASE_SCHEMA.md) — PostgreSQL data model, relational constraints, and indexes.
- [**docs/ROADMAP.md**](docs/ROADMAP.md) — Staged implementation milestones and acceptance criteria.
- [**docs/TESTING_AND_RELEASE_CHECKLIST.md**](docs/TESTING_AND_RELEASE_CHECKLIST.md) — Quality gates, security audit, and deployment checklist.
- [**docs/README_PROJECT_DOCS.md**](docs/README_PROJECT_DOCS.md) — Comprehensive documentation index.

---

## Local Development Setup

### 1. Prerequisites
- **Python**: 3.12 or higher
- **PostgreSQL**: 15+ running locally (SQLite fallback is explicitly prohibited)
- **Git**

### 2. Environment Setup

Clone the repository and create an isolated virtual environment:

```powershell
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

Install pinned production and testing dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configuration

Copy the sample environment file and configure local PostgreSQL credentials:

```bash
cp .env.example .env
```

Key environment variables in `.env`:
```ini
FLASK_ENV=development
SECRET_KEY=generate-a-strong-random-key
DATABASE_URL=postgresql://factbox_user:factbox_password@localhost:5432/factbox_consult_dev
TEST_DATABASE_URL=postgresql://factbox_user:factbox_password@localhost:5432/factbox_consult_test
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### 4. Database Migrations

Apply the reviewed schema migrations to your local PostgreSQL instance:

```bash
flask db upgrade
```

### 5. Running the Application

Start the local development server:

```bash
python wsgi.py
```
The platform is accessible at `http://127.0.0.1:5000`.

To create an initial administrative user:
```bash
flask create-admin --username admin --email admin@factboxconsult.com
```

In the event of lost credentials, use the emergency CLI reset:
```bash
flask reset-admin-password --email admin@factboxconsult.com
```

---

## Running Automated Tests

The test suite runs against an isolated PostgreSQL test database specified by `TEST_DATABASE_URL`:

```bash
pytest -v
```

All test cases verify models, CSRF enforcement, upload restrictions, rate limits, contact workflows, and administrative authorization.

---

## Production Deployment

The codebase is cloud-ready and adheres to twelve-factor application methodologies:
- **Web Server**: Managed via `Procfile` using Gunicorn: `web: gunicorn wsgi:app`
- **Static & Media**: Static CSS/JS served via production WSGI / CDN; media assets stored in Cloudinary.
- **Database**: Connects to managed PostgreSQL via standard `DATABASE_URL`.
- **Security Headers**: HSTS, CSP, X-Frame-Options, and secure cookies enabled automatically in production mode.

---

## License & Ownership

Copyright &copy; Fact Box Consult. All rights reserved.

