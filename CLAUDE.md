# Claude Code Instructions

This file is a short entry point. `AGENTS.md` is the general coding-agent contract and must be followed.

Before coding, read:
- `docs/README_PROJECT_DOCS.md`
- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- `docs/DATABASE_SCHEMA.md`
- `docs/ROADMAP.md`

Use these as the project source of truth. Do not invent missing business requirements or override a decision silently. If two documents conflict, stop and report the conflict before implementing.

Non-negotiables: Flask + Jinja2 + SQLAlchemy; PostgreSQL in every environment including tests; Cloudinary for images; YouTube embeds for videos; no SQLite; no blog/testimonials/team profiles/quote page/project-detail pages/public registration/separate clients-and-partners page at launch. Persist contact enquiries before email notification and support retry on delivery failure.

Work in small stages. Inspect before editing, add tests, run them, and report exact commands/results. Never claim tests or deployment steps succeeded if they were not run. Never expose secrets or make paid infrastructure changes without explicit authorization.
