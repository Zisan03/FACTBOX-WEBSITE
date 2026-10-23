# Testing and Release Checklist

This is a release gate, not a statement that these checks have already passed.

## Local foundation
- [ ] Python version and dependency lock/constraints documented.
- [ ] `.env` ignored by Git; `.env.example` has placeholders only.
- [ ] PostgreSQL is used locally and for tests; test DB is isolated and never production.
- [ ] App factory, blueprints, configuration validation, logging, and safe error pages work.
- [ ] First migration applies to an empty PostgreSQL database and can be upgraded from the previous migration.
- [ ] CI can provision PostgreSQL and run the full test suite.

## Authentication and authorization
- [ ] Admin account is provisioned through a protected CLI flow; no default password/public signup.
- [ ] Passwords are hashed with a modern supported method.
- [ ] Anonymous requests cannot access admin pages or mutation endpoints.
- [ ] CSRF blocks invalid state-changing form requests.
- [ ] Login rate limiting, safe logout, session expiry, secure cookie settings in production, and session rotation are verified.
- [ ] Admin access and critical changes are logged without secrets.

## Portfolio and media
- [ ] Draft projects are not publicly visible; published projects are.
- [ ] Category filters and ordering work on mobile and desktop.
- [ ] Invalid YouTube URLs and arbitrary embed markup are rejected.
- [ ] Upload tests cover permitted formats, MIME/content mismatch, oversized files, malformed images, empty files, and unauthorized upload attempts.
- [ ] Cloudinary credentials never appear in browser assets or logs.
- [ ] Upload/database failure and asset deletion failure do not silently break references.
- [ ] Image alt text, responsive sizes, lazy loading, and accessible controls are checked.

## Contact and email
- [ ] Server-side validation, CSRF, length limits, rate limiting, and abuse controls work.
- [ ] Enquiry is committed to PostgreSQL before email is attempted.
- [ ] Simulated SMTP failure leaves the enquiry intact and marks notification pending/failed.
- [ ] Admin can retry a failed notification and the attempt/status timestamps update correctly.
- [ ] Real email test is performed only after the user authorizes use of the account; verify delivery and spam folder.
- [ ] No visitor auto-reply is sent in V1.

## Public website quality
- [ ] All five pages are responsive and have working navigation/footer.
- [ ] No excluded features have slipped into the release.
- [ ] Keyboard navigation, focus visibility, contrast, semantic headings, form labels, reduced motion, and meaningful image alt text are checked.
- [ ] Titles, descriptions, canonical URLs where appropriate, Open Graph, sitemap, robots rules, favicon, and 404/500 pages are checked.
- [ ] No unapproved claims, placeholder text, AI placeholder imagery, or confidential client material is published.
- [ ] Check current browsers and at least one narrow mobile viewport.

## Production readiness
- [ ] Hosting/database pricing, region, size, resource limits, bandwidth, taxes, and currency conversion verified at checkout.
- [ ] Production secrets configured through host secret manager; none committed.
- [ ] PostgreSQL is private/restricted to the application where supported; least-privilege credentials used.
- [ ] Migrations run as a controlled release step and rollback/recovery plan is documented.
- [ ] HTTPS and secure headers/cookies verified.
- [ ] Domain purchase, DNS, canonical host, redirects, and TLS configured after user authorizes purchase/access.
- [ ] Cloudinary credentials and usage alerts configured; upload/delivery tested.
- [ ] Gmail/SMTP authentication, outbound network availability, sender identity, and limits verified.
- [ ] Production database backup policy documented and a restore has been demonstrated in a separate environment.
- [ ] Enquiry and email-failure paths tested in staging before live traffic.
- [ ] Health checks, error visibility, dependency updates, incident contact, and rollback procedure documented.
- [ ] No live deployment or paid resource is created without explicit authorization.

## Go/no-go rule
Do not launch if admin authorization, CSRF, PostgreSQL persistence, enquiry durability, upload validation, HTTPS, secrets handling, or verified database recovery is incomplete. Record any accepted non-critical limitation and its owner; do not hide it.
