# Fact Box Consult — Architecture Decisions (Hosting Update)

**Date:** 18 October 2026

## ADR-001 — PostgreSQL is mandatory in every environment
**Decision:** PostgreSQL is used in local development, automated tests, staging, and production. SQLite fallback is prohibited.

**Reason:** Prevent environment-specific behaviour and ensure database-specific functionality is tested before deployment.

**Revisit only if:** The project owner explicitly changes the database requirement and approves the consequences.

## ADR-002 — Managed hosting is preferred
**Decision:** Use a managed Flask hosting service and managed PostgreSQL instead of self-managing a VPS at launch.

**Preferred candidate:** Render, subject to final pricing/region/checkout verification.

**Reason:** Reduces operational burden and provides a documented database recovery mechanism. A self-managed VPS might have a lower compute price but transfers patching, firewall, backup, monitoring, and recovery responsibilities to the project team.

## ADR-003 — Render is preferred over Railway for initial production, but not treated as irrevocable
**Decision:** Shortlist Render first. Railway remains an alternative if a workload-specific estimate proves cheaper and a tested independent backup/restore process is established.

**Evidence reviewed:** Render's published July 2026 snapshot estimates about US$13/month for an always-on Starter web service plus Basic-256mb PostgreSQL on Hobby, before usage growth. Render paid PostgreSQL offers a three-day PITR window on Hobby workspace. Railway Hobby has a US$5/month minimum with US$5 resource credits, but app and database resources are metered.

**Revisit criteria:** Recheck prices immediately before provisioning; compare the expected all-in cost, region availability, memory/CPU, storage, outbound bandwidth, backup/restore options, service sleep/cold-start behaviour, support, and tax/currency conversion.

## ADR-004 — Cloudinary is the media store
**Decision:** Portfolio photographs are stored and delivered by Cloudinary. PostgreSQL stores metadata and asset identifiers. Video is embedded from YouTube.

**Reason:** The Flask application filesystem is ephemeral in managed containers, and image delivery/optimization is a dedicated media concern. Cloudinary Free offers 25 monthly credits and a 10 MB maximum image size; storage, transformations, and image bandwidth consume the same credit pool.

**Controls:** Server-side upload validation, 10 MB initial file limit, no API secret in browser code, monitor credits, and review paid-tier need if usage grows.

## ADR-005 — Existing Gmail account is the initial notification sender
**Decision:** Integrate the existing account first; do not add a paid email provider without approval.

**Controls:** Verify account identity, account type, supported authentication, SMTP connectivity from the selected host, delivery, and spam handling. Keep credentials in secret configuration. Do not assume that app-password authentication is available for every account. If SMTP is unsuitable, document options and ask for approval before changing providers.

## ADR-006 — Enquiries are durable before email is attempted
**Decision:** Commit every valid enquiry to PostgreSQL before sending notification email. Track delivery status and allow retry.

**Reason:** SMTP outages or credential problems must not erase an enquiry or mislead the visitor into thinking a lost message was received.

## ADR-007 — Application containers are stateless
**Decision:** No user uploads or authoritative application data are stored on the web service's local filesystem.

**Reason:** Container filesystems may be ephemeral. Media belongs in Cloudinary; structured records belong in PostgreSQL.

## ADR-008 — No free-tier production database
**Decision:** Do not launch with Render Free PostgreSQL.

**Reason:** Render documents a 30-day expiry, no managed backup/PITR, and a limited recovery path after expiration. A business website needs durable production storage and tested recovery.

## ADR-009 — Scope changes require explicit approval
**Decision:** Blog, testimonials, team profiles, request-a-quote, individual project detail pages, a separate client/partner page, public registration, and social links are not initial-launch features. Social links are planned for future expansion.

**Reason:** Preserve the two-week launch target and prevent accidental scope growth.

## ADR-010 — Home Page Photos are dedicated assets distinct from Portfolio media
**Decision:** Home page hero slideshow imagery is stored in a dedicated `home_page_photo` table and managed through a dedicated "Home Page Photos" admin screen, rather than being queried from portfolio projects.

**Reason:** Keeps home page presentation assets isolated from client portfolio case studies, avoiding accidental leaks or confusion when non-technical administrators manage the site.

**Controls:** Uses the existing Cloudinary upload service, server-side MIME and size validation, CSRF protection, and non-negative ordering constraints. Scheduled for delivery in Stage 5.
