# Fact Box Consult — Project Documentation Index

This package is the agreed starting contract for a fresh build. It is not application code and does not claim that the project has been implemented or deployed.

## Read in this order

1. **`PRD.md`** — product scope, users, requirements, acceptance criteria, exclusions.
2. **`ARCHITECTURE.md`** — components, boundaries, deployment shape, security, data flows.
3. **`ARCHITECTURE_DECISIONS.md`** — binding technology and scope decisions, including why they were chosen.
4. **`DATABASE_SCHEMA.md`** — starting relational schema and constraints to review before the first migration.
5. **`ROADMAP.md`** — staged implementation order and exit gates.
6. **`TESTING_AND_RELEASE_CHECKLIST.md`** — verification and production go/no-go gates.
7. **`AGENTS.md`** — general coding-agent contract.
8. **`CLAUDE.md`** — Claude Code entry point that refers to `AGENTS.md`.

## Document authority

PRD defines _what_. Architecture defines _how_. Architecture decisions record why and what cannot change silently. Database schema specifies the initial data model. Roadmap controls order. Tests and release checklist prove behaviour. Agent instruction files enforce working discipline.

If a conflict appears, do not code around it. Raise it and update the relevant documents together. Approved scope changes must update PRD, architecture/ADRs, schema, roadmap, and tests as relevant.

## Approved V1 summary

- Flask + Jinja2 + SQLAlchemy + PostgreSQL; PostgreSQL only in every environment, including tests.
- HTML/CSS/vanilla JavaScript frontend.
- Public pages: Home, About Us, Services, Our Work, Contact Us.
- Secure, single-admin content dashboard; no public registration.
- Cloudinary images; YouTube videos embedded from validated video IDs.
- Contact submissions persisted before notification email; failed notifications remain retryable.
- Managed hosting candidate: Render, pending live price/configuration verification. Railway is a reviewed alternative, not a simultaneous deployment target.
- Social links, blog, testimonials, team profiles, request-a-quote, individual project detail pages, public portal, and separate Clients & Partners page are out of launch scope.

## Not yet confirmed; do not invent

- Final production hosting plan and region.
- Domain purchase, DNS access, and registrar.
- Actual sender and recipient email addresses, Gmail account type, SMTP authentication method, and whether outbound SMTP works from chosen host.
- Final business copy, approved portfolio assets, publication permissions, and client-logo permissions.
- Whether partner logos need their own admin-managed table in V1 or can be attached to portfolio content.
- Exact Cloudinary account/plan and media usage forecast.

## Fresh-build instruction

When the user uploads these documents into the coding environment, inspect the workspace, install no paid services, and begin at Roadmap Stage 0/1. Do not generate all application features in one uncontrolled pass.
