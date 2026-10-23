# Coding Agent Contract — Fact Box Consult

Read `docs/README_PROJECT_DOCS.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/ARCHITECTURE_DECISIONS.md`, `docs/DATABASE_SCHEMA.md`, and `docs/ROADMAP.md` before making changes. These documents are the project contract.

## Authority and scope
1. `docs/PRD.md` governs what the product must and must not do.
2. `docs/ARCHITECTURE.md` governs system boundaries and technical structure.
3. `docs/ARCHITECTURE_DECISIONS.md` records binding decisions and approved exceptions.
4. `docs/DATABASE_SCHEMA.md` is the starting data model specification; migrations and tests must match it.
5. `docs/ROADMAP.md` governs sequencing and stage acceptance criteria.
6. If documents conflict, stop and report the conflict. Do not choose silently. Ask for an explicit decision or update the documents consistently before coding.

## Non-negotiable rules
- Backend: Python + Flask, application factory, blueprints, Jinja2, SQLAlchemy, Flask-Migrate/Alembic.
- PostgreSQL only in local development, tests, staging, and production. Never add SQLite, SQLite fallback, or a test configuration that silently switches databases.
- Use HTML, CSS, and vanilla JavaScript. Do not introduce a frontend framework or a large dependency without approval.
- Use Cloudinary for portfolio images; use YouTube embeds for video. Do not persist user media on the app's local filesystem or store image binaries in PostgreSQL.
- Do not add blog, testimonials, team profiles, a Request a Quote page, individual project pages, public registration, or a separate Clients & Partners page in the launch scope. Social profile links are deferred.
- Contact enquiries must be committed to PostgreSQL before email notification is attempted. Email failure must never discard an enquiry; notification failures need visible status and a retry path.
- Never hard-code credentials, API keys, passwords, production URLs with secrets, or real personal data. `.env.example` contains placeholders only.
- Never weaken authentication, CSRF, validation, rate limits, cookie settings, authorization, upload restrictions, or database constraints to make a test pass.
- Never use `db.create_all()` as the production migration strategy. Schema changes require reviewed migrations.
- No default admin password, public admin registration, arbitrary HTML/template editing, or unsanitized embed URLs.
- Keep changes small, explain the reason, and add or update tests for behavior changes.
- Do not claim a command, test, security check, deployment, backup, or restore succeeded unless you actually ran it and observed the result.
- Do not purchase services, create paid resources, change DNS, or send real emails without explicit user authorization.

## Required workflow
1. Inspect the existing repository and relevant files before editing; preserve useful work unless the user explicitly authorizes replacement.
2. State the stage and acceptance criteria being addressed.
3. Implement the smallest coherent change.
4. Run relevant formatting/static checks and tests; test against PostgreSQL, not SQLite. If PostgreSQL or credentials are unavailable, state exactly what could not be verified.
5. Review security, migrations, error handling, and unintended scope changes.
6. Summarize files changed, decisions made, commands run, actual test results, risks, and next step.

## Security and operations
- Validate on the server even when browser validation exists.
- Escape user-authored content in templates; do not mark it safe unless it is controlled and sanitized.
- Use CSRF protection for state-changing browser forms and rate-limit public submissions and login attempts.
- Use least-privilege PostgreSQL credentials, secure session cookies in production, HTTPS, security headers, safe error pages, and privacy-conscious logs.
- Restrict admin endpoints with authorization checks on every route/action.
- Verify uploaded files by content and allowed format, enforce size limits, and handle Cloudinary/database partial failures deliberately.
- Never log secrets or full enquiry contents unnecessarily.
- Treat production database backup and a demonstrated restore as release blockers.

## Scope-change procedure
A requested scope or technology change must be reflected in the PRD, architecture/decision record, schema if relevant, roadmap, and tests before implementation. Explain impacts on cost, security, schedule, and migration/recovery. Do not silently reinterpret an approved requirement.
