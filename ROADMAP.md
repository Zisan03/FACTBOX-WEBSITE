# Fact Box Consult — Reconciled Development Roadmap

**Status:** agreed V1 plan for a fresh build; no implementation status is implied. Read `README_PROJECT_DOCS.md` first.

## Operating rules
- Backend-first, with a working vertical slice at every stage.
- PostgreSQL exclusively in local development, tests, staging, and production. Never use SQLite as a shortcut.
- Security controls are built into each stage, not postponed until launch.
- Preserve the Stitch design direction where it fits the approved pages; do not blindly copy static prototype HTML or placeholder content.
- Do not add excluded features without a documented and approved scope change.
- Each stage must meet its exit gate before the next stage starts. The two-week target is aggressive; access delays, real content, email auth, and provider limits may move the date.

## Stage 0 — Project contract and workspace inspection
**Goal:** establish a clean, understood repository and consistent documentation before application coding.

Tasks:
- Put the documentation package at repository root.
- Inspect the uploaded Stitch ZIP and its `DESIGN.md`; inventory page HTML and image assets.
- Record confirmed public pages and excluded screens; identify shared design tokens, fonts, components, breakpoints, and assets.
- Create a clean Python environment and Git repository if not already present; inspect `.gitignore`.
- Create `.env.example`, README setup notes, and dependency policy; never create real secrets in docs.
- Confirm local PostgreSQL is installed/running or provide a clear setup route; obtain a dedicated development DB and isolated test DB.

**Exit gate:** docs are in root; repo tree and Stitch inventory are documented; no credentials or accidental secrets are committed; PostgreSQL connection approach is confirmed.

## Stage 1 — Secure Flask foundation and PostgreSQL
**Goal:** establish the maintainable application skeleton.

Deliverables:
- Flask application factory, config validation, extensions, blueprints, Jinja template structure, static assets, error handlers, logging, WSGI entry point.
- SQLAlchemy, Flask-Migrate/Alembic, PostgreSQL URL parsing and connection handling.
- Environment-specific configuration with fail-closed production checks; no SQLite fallback.
- Test setup that requires an isolated PostgreSQL database.
- Basic health/readiness endpoint that does not disclose secrets or database internals.
- CI workflow that provisions PostgreSQL and runs tests.

**Tests:** app starts with valid configuration; fails safely with missing critical production config; PostgreSQL connects; migrations apply to empty DB; health route is safe; tests cannot connect to production DB.

**Exit gate:** clean checkout can set up and run foundation using documented steps; migration and PostgreSQL integration tests pass.

## Stage 2 — Schema, migrations, and administrator authentication
**Goal:** establish data model and secure admin access before content CRUD.

Deliverables:
- Review `DATABASE_SCHEMA.md`; confirm minimal V1 entities before generating first migration.
- Models and constraints for admin, portfolio/category/media metadata, services/page content if needed, enquiries, notification state, and minimal audit events as approved.
- First reviewed migration and seed/CLI provisioning command for initial administrator.
- Login/logout, password hashing, CSRF, rate limiting, authorization decorators, session protections, safe error handling.
- No public registration and no default credentials.

**Tests:** unauthorized admin access denied; login success/failure; password not stored in plaintext; CSRF enforcement; session behavior; migration upgrade path; constraints/indexes.

**Exit gate:** administrator can sign in securely; protected routes are protected; schema migrations and PostgreSQL tests pass.

## Stage 3 — Admin content management and Cloudinary media
**Goal:** allow approved content to be managed without editing code.

Deliverables:
- Admin CRUD for portfolio projects/categories, images, validated YouTube IDs, services, and only the approved editable page fields.
- Draft/published workflow, featured/order controls, image alt text and captions.
- Cloudinary integration with server-side secrets, signed/server-mediated upload flow, size/type/content validation, and safe cleanup/recovery logic.
- Client/partner logos only in approved contexts; do not create a separate public page. Decide whether a dedicated logo entity is necessary before implementation.

**Tests:** draft/public visibility, ordering/category filters, invalid video URL rejection, malicious upload cases, oversize file rejection, unauthorized upload attempts, provider failure, and orphan/reference handling.

**Exit gate:** administrator can publish a project with images/videos and safely unpublish/edit it; media does not depend on local disk.

## Stage 4 — Contact enquiry workflow and email
**Goal:** capture enquiries reliably and notify the organisation.

Deliverables:
- Responsive contact form with server validation, CSRF, length limits, rate limiting and proportionate abuse protection.
- Commit enquiry to PostgreSQL before attempting email.
- Email adapter configured through environment variables; Gmail SMTP only after account/auth/host support is verified.
- Notification state, attempt timestamps/count, safe error state, admin enquiry list/detail and retry action.
- Clear visitor success/error feedback; no visitor auto-reply in V1.

**Tests:** valid and invalid submissions; repeated/spam submissions; DB failure; email success; email failure after DB commit; retry; no secrets in logs; escaped enquiry display.

**Exit gate:** no enquiry is lost due to email failure; administrator can identify and retry failed notifications; authorized real delivery test succeeds before production.

## Stage 5 — Public pages and Stitch design implementation
**Goal:** implement the five approved pages with responsive, accessible, real content.

Pages: Home, About Us, Services, Our Work, Contact Us.

Tasks:
- Extract design tokens and reusable components from the supplied Stitch pages and `DESIGN.md`.
- Implement shared navigation/footer and consistent typography, palette, spacing, cards, buttons, form controls, responsive breakpoints, and motion preferences.
- Build pages with Jinja2 using database-managed portfolio/services and approved page content.
- Our Work remains a single page with project cards, category filters, photo galleries and validated YouTube embeds; no individual project-detail route.
- Replace generated placeholder images and unsupported business claims with approved material before launch.
- Implement SEO essentials and accessibility checks.

**Tests/review:** responsive layout, navigation, focus/keyboard, forms, reduced motion, image alt text, headings, contrast, no broken media, no excluded pages/sections, no console errors, metadata and 404/500 pages.

**Exit gate:** all five pages work end-to-end and align with the approved design direction on desktop and mobile.

## Stage 6 — Integration, content, and hardening
**Goal:** verify the entire user journey and prepare release candidate.

Tasks:
- Seed only approved services and content; load approved portfolio assets with client permissions checked.
- Run complete automated tests and manual end-to-end checks.
- Check CSRF, authorization, upload restrictions, rate limiting, input/output handling, security headers, cookies, secrets, dependency issues, error handling and logs.
- Test image optimization/lazy loading, category filtering, keyboard navigation and performance on representative mobile widths.
- Validate contact notification delivery, failure simulation and retry.
- Complete `TESTING_AND_RELEASE_CHECKLIST.md` and record unresolved issues honestly.

**Exit gate:** no unresolved critical/high security issues; all release-blocking tests pass; approved content is available; user accepts any documented non-critical limitations.

## Stage 7 — Production deployment and handover
**Goal:** deploy safely on the selected managed platform.

Dependencies: domain purchase/access, final host and price approval, Cloudinary credentials, confirmed sender/recipient email configuration, approved content.

Tasks:
- Verify current Render and Railway costs/limits before selecting the production host. Render is preferred, not yet purchased or provisioned.
- Provision paid managed PostgreSQL with suitable persistence/recovery; never use expiring free DB for production.
- Configure production environment secrets, private DB access, migrations, health checks, HTTPS, domain/DNS, canonical redirects and safe headers.
- Configure Cloudinary and usage monitoring; verify Gmail authentication/outbound SMTP or request approval for an alternative.
- Set up database backups and **demonstrate a restore in a separate environment**.
- Deploy, run smoke tests, test real contact flow, monitor logs, and document rollback/incident procedures.
- Provide handover notes: deploy/update process, admin use, content management, backup/restore, secret rotation, provider costs and renewal reminders.

**Exit gate:** all release gates in `TESTING_AND_RELEASE_CHECKLIST.md` pass; user explicitly approves production deployment and any paid resources.

## Schedule guidance
A two-week launch is possible only if the scope stays fixed, repository setup is straightforward, approved content is ready, and domain/email/provider access arrives promptly. Prioritize Stages 0–4 as the backend-first foundation, then implement the public UI in parallel only after the core data contracts are stable. Do not skip database recovery, security or contact durability to meet the date.

## Deferred scope (requires a new decision)
Blog/insights; testimonials; team profiles; Request a Quote page; individual project pages; public registration/client portal; separate Clients & Partners page; social profile links; visitor auto-reply. Do not add these as “small extras” during V1.
