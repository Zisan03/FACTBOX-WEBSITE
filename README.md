# Fact Box Consult — Website Project

Official web platform for **Fact Box Consult** (RC: 7592601), an audiovisual media, research, and creative consultancy.

## Project Governance & Documentation
Before making architectural or code modifications, consult the project specifications:
- [README_PROJECT_DOCS.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/README_PROJECT_DOCS.md) — Documentation index and reading order.
- [AGENTS.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/AGENTS.md) — Non-negotiable engineering rules and agent contract.
- [PRD.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/PRD.md) — Product requirements, in-scope pages, and excluded features.
- [ROADMAP.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/ROADMAP.md) — Staged execution roadmap (Stages 0–7) and exit gates.
- [ARCHITECTURE.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/ARCHITECTURE.md) & [ARCHITECTURE_DECISIONS.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/ARCHITECTURE_DECISIONS.md) — System topology and binding decisions.
- [DATABASE_SCHEMA.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/DATABASE_SCHEMA.md) — Relational PostgreSQL schema specification.
- [STAGE_0_INVENTORY.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/STAGE_0_INVENTORY.md) — Repository baseline, design token extraction, and asset mapping.

---

## Local Development Setup

### 1. Prerequisites
- **Python:** 3.12+
- **PostgreSQL:** 15+ running locally or accessible via network (mandatory across development, test, and production). SQLite fallback is prohibited.

### 2. Virtual Environment Setup
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Upgrade pip and install pinned dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Environment Variables
Copy the template and configure your local PostgreSQL connection and secrets:
```powershell
cp .env.example .env
```
Ensure `.env` contains:
- `DATABASE_URL`: URI for local/dev PostgreSQL database (e.g., `postgresql://factbox_user:factbox_password@localhost:5432/factbox_consult_dev`)
- `TEST_DATABASE_URL`: URI for isolated test PostgreSQL database (e.g., `postgresql://factbox_user:factbox_password@localhost:5432/factbox_consult_test`)
- `SECRET_KEY`: Random high-entropy secret string

> **Warning:** Never commit `.env` or real API keys to version control.

---

## Dependency Policy
- All dependencies must be pinned in `requirements.txt`.
- Do not introduce frontend frameworks or build-heavy dependencies; UI uses semantic HTML5, CSS3, and vanilla JavaScript.
- Backend additions must be vetted against architecture constraints:
  - Database access: SQLAlchemy + Alembic / Flask-Migrate.
  - Driver: `psycopg2-binary` (or `psycopg[binary]`).
  - Forms / CSRF: `Flask-WTF`.
  - Media: Cloudinary Python SDK (server-side only).
  - Testing: `pytest`, `pytest-flask`.
