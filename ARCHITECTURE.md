# Fact Box Consult — Hosting and System Architecture

**Status:** Updated with confirmed hosting decisions  
**Date:** 18 October 2026  
**Preferred production candidate:** Render + managed PostgreSQL + Cloudinary Free + existing Gmail account.

## 1. Architecture goals

- Keep recurring costs low and predictable.
- Use PostgreSQL exclusively across all environments.
- Keep user-generated media out of the application container and database binary fields.
- Preserve enquiries even when email delivery fails.
- Make content manageable by one administrator without exposing application code.
- Keep providers replaceable behind small service interfaces where this is practical.

## 2. Deployment topology

```text
Public visitor / Administrator
             |
          HTTPS
             |
      Render Web Service
      Flask + Gunicorn
       /      |       \
      /       |        \
PostgreSQL  Cloudinary  Gmail SMTP
(content,   (image      (enquiry
users,      originals,  notification)
enquiries,  transforms)
metadata)

YouTube videos are embedded from YouTube; video files are not hosted by the Flask app.
```

### Responsibilities

**Render web service**
- Runs the Flask application under Gunicorn.
- Serves HTML and static CSS/JavaScript.
- Uses environment variables or the host's secret-management mechanism.
- Does not persist uploads to its local filesystem.
- Sends outbound email only after the enquiry is committed to PostgreSQL.

**Render PostgreSQL**
- Source of truth for admin users, services, editable page content, portfolio records, image metadata/Cloudinary identifiers, YouTube references, enquiries, notification states, and migration state.
- Access the database over private networking when available.
- Use a least-privilege application database user.
- Apply schema changes using Flask-Migrate/Alembic migrations; never rely on `create_all()` as the production migration strategy.

**Cloudinary**
- Stores uploaded portfolio images and delivers optimized variants.
- PostgreSQL stores stable asset identifiers, secure delivery URLs where needed, alt text, ordering, captions, and related project references.
- API secrets remain on the server.
- Uploads use a signed server-mediated flow or another explicitly reviewed secure flow. Never expose the Cloudinary API secret to the browser.
- Add file-size/type validation and upload limits. Initial maximum: 10 MB per image, configurable and aligned with the Free plan.
- Monitor credits across storage, transformations, and image bandwidth.
- Define deletion behaviour so removing an image reference from a project does not accidentally remove an asset still used elsewhere.

**Gmail**
- The application sends internal enquiry notifications to the confirmed company recipient.
- The enquiry is committed before SMTP is attempted.
- If SMTP fails, the enquiry remains in PostgreSQL with a pending/failed status and can be retried by the administrator.
- Keep the sender, recipient, host, port, TLS settings, username, and secret in environment configuration.
- Verify account type, supported authentication, SMTP egress, sending limits, and deliverability before production launch. Do not assume app-password authentication will be available or appropriate for every Google account.

## 3. Provider cost and capability comparison

| Component | Preferred | Alternative | Decision basis |
|---|---|---|---|
| Flask hosting | Render Starter-class web service | Railway Hobby | Render's published July 2026 cost snapshot estimated about $13/month for an always-on Starter web service plus Basic-256mb PostgreSQL on Hobby workspace, before usage growth. Railway Hobby starts at $5/month including $5 resource credits, but final cost depends on app and database consumption. |
| PostgreSQL | Paid Render PostgreSQL | Railway PostgreSQL service | Render paid PostgreSQL offers PITR (3-day window on Hobby workspace) and logical backup exports. Railway can be cost-competitive, but a tested independent backup/restore process must be part of the deployment design. |
| Images | Cloudinary Free | Paid Cloudinary tier only if limits are exceeded | Free plan includes 25 credits/month and 10 MB maximum image file size. Storage, transformations, and delivery bandwidth draw from the same credits. |
| Email | Existing Gmail account | Separately approved transactional email service | No new paid email provider until the existing account is tested. Switch only if SMTP/authentication/deliverability requirements cannot be met. |

### Cost guardrails

- Budget for the web service and PostgreSQL together; do not compare only web hosting subscription prices.
- The Render $13/month figure is a vendor-published snapshot, not a fixed quote or guaranteed current total.
- Add costs for bandwidth, extra database storage, Cloudinary overages or paid tiers, domain renewal, taxes, and currency conversion where applicable.
- Do not use Render Free PostgreSQL for production: it expires after 30 days and has no managed backup/PITR.
- Do not use a sleeping/free web service for a business-critical production launch unless the owner explicitly accepts cold starts and limitations.
- Check provider billing alerts/usage dashboards before launch and monthly after launch.
- If Railway is selected after rechecking prices, provision a backup process that exports PostgreSQL off-platform, encrypts it, retains multiple dated copies, and periodically tests restore. A backup that has never been restored is not a verified recovery plan.

## 4. Application structure and boundaries

Use a Flask app factory and focused blueprints. Exact module names can be adjusted during repository inspection, but boundaries should remain clear.

```text
factbox-consult/
├── app/
│   ├── __init__.py             # create_app(), blueprint registration
│   ├── config.py               # dev/test/prod configuration
│   ├── extensions.py           # SQLAlchemy, Migrate, CSRF, LoginManager
│   ├── models/                 # User, Service, PageContent, Project, ProjectImage, Enquiry
│   ├── blueprints/
│   │   ├── public/             # Home, About, Services, Our Work
│   │   ├── contact/            # Enquiry submission and validation
│   │   └── admin/              # Authenticated content and enquiry management
│   ├── services/
│   │   ├── media.py            # Cloudinary boundary
│   │   └── email.py            # notification send/retry boundary
│   ├── templates/
│   └── static/
├── migrations/
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py
└── wsgi.py
```

Do not create modules for blog, testimonials, team profiles, request-a-quote, individual project pages, or public registration unless the product scope is explicitly changed.

## 5. Data flow

### Portfolio image upload
1. Authenticated administrator submits an image and associated project fields.
2. Server checks authorization, CSRF, file size, allowed format, and content-type/signature where possible.
3. Server uploads through a secure Cloudinary flow.
4. Server records the Cloudinary asset ID, delivery URL/metadata, alt text, caption, ordering, and project relationship in PostgreSQL.
5. If the database write fails after upload, log the failure and attempt cleanup or record a reconciliation task to avoid an orphaned asset.
6. Public page requests retrieve published project records and render responsive Cloudinary URLs.

### Contact enquiry
1. Visitor submits the contact form over HTTPS.
2. Server validates and normalizes fields, checks CSRF and rate limits, and rejects invalid submissions.
3. Server commits the enquiry with notification status `pending`.
4. After commit, server attempts to send the internal notification.
5. On success, update status and sent timestamp.
6. On failure, keep the enquiry and mark the attempt failed with a safe diagnostic message. Do not expose SMTP details to the visitor.
7. Administrator can inspect and retry the notification. Retry must not create a duplicate enquiry.

### Admin access
1. Administrator submits credentials.
2. Server verifies the password hash and applies login throttling.
3. Session cookie uses Secure, HttpOnly, and appropriate SameSite settings in production.
4. Every admin endpoint enforces authentication and authorization; state-changing requests require CSRF validation.
5. Admin account creation/reset is controlled; no public registration and no hard-coded default credentials.

## 6. Configuration

Required environment variables should be documented in `.env.example` with placeholders only. The real `.env` must be ignored by version control.

Example variable names (names may be refined during implementation):
- `FLASK_CONFIG`
- `SECRET_KEY`
- `DATABASE_URL`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `MAIL_SERVER`
- `MAIL_PORT`
- `MAIL_USE_TLS` / `MAIL_USE_SSL`
- `MAIL_USERNAME`
- `MAIL_PASSWORD` or an approved authentication token
- `MAIL_DEFAULT_SENDER`
- `ENQUIRY_RECIPIENT`
- `PUBLIC_BASE_URL`

Production configuration must fail closed when critical secrets or the PostgreSQL URL are missing. Never silently fall back to SQLite or insecure defaults.

## 7. Database and recovery

- PostgreSQL in development, tests, staging, and production.
- Use a dedicated test database or isolated test schema/database, never production data.
- Apply migrations in CI/staging before production rollout.
- Use transactions for multi-step database writes.
- Establish a production backup schedule and retention policy.
- Render paid PostgreSQL has vendor-managed PITR: three days on Hobby workspace, seven days on Pro or higher. Render also documents logical exports retained for seven days after creation.
- Before launch, create an export and successfully restore it to a separate database, then verify core tables and records.
- For important data, consider an additional encrypted off-platform backup; managed recovery alone should not be the only recovery path if the business requires longer retention.
- Test recovery after schema changes and periodically thereafter.

## 8. Security and operational controls

- HTTPS only in production; redirect HTTP to HTTPS.
- Secret management via environment variables/host secret store.
- No secrets in Git, logs, browser bundles, screenshots, or issue reports.
- CSRF protection for forms and admin mutations.
- Password hashing, login throttling, secure cookies, authorization checks.
- Server-side validation, output escaping, safe URL validation for YouTube embeds.
- Upload size/type restrictions and Cloudinary secret isolation.
- Security headers and safe generic error pages.
- Rate limiting on public contact and authentication endpoints.
- Database access restricted to the application and authorized operators.
- Structured logs without credentials or unnecessary personal information.
- Dependabot or an equivalent dependency review process; upgrades tested before deployment.
- Low-cost uptime and error monitoring; review alerts and usage dashboards.
- Maintain a clear rollback path for application deploys and a documented database recovery process.

## 9. Deployment sequence

1. Confirm repository and current working tree; reconcile the existing `ROADMAP.md` with the approved scope.
2. Implement app factory, config, extensions, PostgreSQL connection, migrations, and test setup.
3. Implement schema and secure admin access.
4. Implement Cloudinary media service and portfolio content management.
5. Implement enquiry persistence and email notification/retry.
6. Integrate the approved Stitch design references into Jinja templates.
7. Test locally against PostgreSQL; do not substitute SQLite.
8. Create staging deployment and run migrations and integration tests.
9. Verify Cloudinary uploads, Gmail delivery, error handling, usage monitoring, and database restore.
10. Verify production checkout costs and create paid services.
11. Configure secrets, domain/DNS, HTTPS, monitoring, backup policy, and deploy.
12. Run a launch checklist and keep a rollback plan.

## 10. Official references

- Render pricing: https://render.com/pricing
- Render free service limitations: https://render.com/docs/free
- Render PostgreSQL: https://render.com/docs/postgresql
- Render backups/recovery: https://render.com/docs/postgresql-backups
- Render compute plans: https://render.com/docs/compute-plans
- Railway pricing: https://railway.com/pricing
- Railway resource pricing: https://docs.railway.com/pricing/plans
- Cloudinary pricing: https://cloudinary.com/pricing
- Cloudinary plan comparison: https://cloudinary.com/pricing/compare-plans
- Cloudinary billing/credits: https://cloudinary.com/documentation/billing_and_plans
- Gmail SMTP configuration: https://knowledge.workspace.google.com/admin/gmail/send-email-from-a-printer-scanner-or-app
- Google app passwords: https://support.google.com/mail/answer/185833
