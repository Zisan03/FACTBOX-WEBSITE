# Fact Box Consult Website — Product Requirements Document (PRD)

**Status:** Updated with confirmed hosting decisions  
**Date:** 18 October 2026  
**Scope:** Initial public website, administrator content management, contact enquiries, and production hosting.

## 1. Product summary

Fact Box Consult needs a responsive, secure, content-managed company website that helps individuals, businesses, and organisations understand its services, explore its work, and contact the company. The website must be manageable by an administrator without editing source code.

The existing Google Stitch designs are visual references. They are not a mandate to implement every designed page or component.

## 2. Confirmed decisions

- Backend: Python + Flask.
- Templates: Jinja2.
- ORM and database: SQLAlchemy + PostgreSQL exclusively in development, tests, staging, and production. No SQLite fallback.
- Frontend: HTML, CSS, and vanilla JavaScript.
- Hosting: managed hosting; Render is the preferred candidate pending final account/checkout verification.
- Media: Cloudinary for uploaded portfolio images; YouTube embeds for video.
- Email: integrate the existing Gmail account first, subject to verification of the account, authentication method, sending limits, and provider SMTP/network support.
- Budget: low recurring cost, without sacrificing data persistence, security, or recoverability.
- Domain: `factboxconsult.com` is a pre-launch dependency and is not assumed to have been purchased.
- Target: launch within two weeks, subject to access to content, credentials, and timely testing.

## 3. Users and primary journeys

### Public visitors
The audience includes individuals and businesses/organisations.

Primary journeys:
1. Understand who Fact Box Consult is and what it does.
2. Explore services and completed work.
3. View portfolio photographs, project descriptions, categories, and embedded YouTube videos.
4. Submit an enquiry through the contact form.

### Administrator
One administrator is expected at launch. The administrator must be able to:
- Sign in securely and sign out.
- Create, edit, publish, unpublish, and delete portfolio entries.
- Add, reorder, replace, and remove portfolio images using Cloudinary.
- Add YouTube video URLs for embedded playback.
- Maintain project descriptions, categories, dates where relevant, and featured status.
- Manage service content and approved editable page content.
- Manage client/partner logos where they are included in portfolio or appropriate page sections.
- Review enquiries and their email-notification delivery status.
- Retry failed notification delivery without losing the original enquiry.

No public registration is required.

## 4. Initial public pages

1. Home
2. About Us
3. Services
4. Our Work — a single portfolio page with many projects, photos, YouTube embeds, descriptions, and category filters.
5. Contact Us

The Client & Partners Stitch screen may be used as a visual/content reference, but there will not be a separate Clients & Partners page at launch.

## 5. Explicitly out of scope for launch

- Blog or insights section.
- Testimonials and testimonial pages/sections.
- Request a Quote page.
- Individual project detail pages.
- Team member profiles.
- Public user registration or client portal.
- Social-media links (planned for a later expansion).
- Visitor auto-reply email.
- Self-hosted video storage or video transcoding.

These features must not be added by an agent or developer without an explicit scope change.

## 6. Functional requirements

### FR-01 — Public content
The five public pages must be responsive, navigable, and usable on mobile, tablet, and desktop. The design should preserve the supplied brand identity and Stitch direction where appropriate, but real approved business content must replace placeholder claims and imagery.

### FR-02 — Portfolio
- Portfolio content must be stored in PostgreSQL.
- Each entry must support a title, slug or stable identifier, description, category, publication status, optional featured flag, ordering, image references, and YouTube video URLs as appropriate.
- Public visitors can filter projects by category without requiring individual project pages.
- Draft/unpublished projects must not appear publicly.
- YouTube URLs must be validated and rendered using safe embed URL handling; arbitrary HTML from administrators must not be rendered.
- Image metadata and Cloudinary asset identifiers/URLs are stored in PostgreSQL. Image binary data is not stored in PostgreSQL.

### FR-03 — Media upload
- Images are uploaded to Cloudinary through a server-mediated flow or a properly signed upload flow.
- Cloudinary API secrets must never be exposed to browser code.
- Validate allowed image formats and file size server-side; do not trust filename extensions or client-supplied MIME types alone.
- Set a sensible initial upload limit (recommended: 10 MB per image to align with the Cloudinary Free plan), with configurable limits.
- Use Cloudinary transformations or optimized delivery URLs for responsive web images.
- Handle failed uploads, failed database writes, and media deletion deliberately; avoid orphaned assets where practical.
- Keep media storage outside the application container filesystem.

### FR-04 — Services and page content
The administrator can update approved service descriptions and designated editable page content without editing templates. Layout, navigation, security-sensitive configuration, and arbitrary template/code editing are not exposed through the admin panel.

### FR-04a — Home Page Photos (Cinematic Gallery)
- The home page hero features an auto-advancing cinematic background photo gallery.
- Transitions every 30 seconds with a smooth CSS cross-fade, pauses on hover and keyboard focus, and respects `prefers-reduced-motion`.
- Managed in the admin panel under a dedicated, clearly labeled "Home Page Photos" page (completely separated from portfolio projects to avoid confusion).
- Administrators can upload photos to Cloudinary, set required alt text, optional captions, reorder display order, and toggle active status.

### FR-05 — Contact enquiries
- The form collects only necessary contact and enquiry information.
- Validate input on the server, escape displayed content, apply CSRF protection, and rate-limit submissions.
- Persist the enquiry to PostgreSQL **before** attempting email notification.
- A successful database save must not be undone if email delivery fails.
- Store a notification state (for example: pending, sent, failed), timestamps, and a safe error summary for administrator troubleshooting.
- Provide an authenticated admin action to retry failed notification delivery.
- Show a clear success message only after the enquiry has been persisted.
- Do not send visitor auto-replies in the initial release.

### FR-06 — Email notification
- Use the existing Gmail account if the account owner confirms access and the chosen sending method works from the selected host.
- Do not store the account password or app password in source code or commit it to version control.
- Keep SMTP host, port, sender, recipient, username, and secret in environment configuration.
- Test delivery, spam-folder behaviour, and failure handling before launch.
- Gmail's published sending limits and authentication policies can change; this website's low-volume notification use should remain modest, but the exact account type and current limits must be verified.
- If Gmail SMTP is blocked or unsuitable, stop and propose a separately approved transactional email provider; do not silently switch providers or introduce an unapproved recurring cost.

### FR-07 — Admin authentication
- No public admin registration.
- Provision the initial administrator through a controlled CLI/one-time setup process, not a hard-coded default password.
- Hash passwords using a modern framework-supported password hashing method.
- Enforce login-required authorization for every admin route and every content mutation.
- Use CSRF protection, secure session cookie settings, login throttling, and safe logout.
- Do not expose secrets, stack traces, database details, or internal paths in public error pages.
- Keep an auditable record of relevant administrative actions where proportionate.

### FR-08 — Search/social features
SEO essentials (titles, descriptions, canonical URLs where appropriate, sitemap, robots rules, Open Graph metadata, accessible image alt text) are in scope. Social-media profile links are deferred.

## 7. Non-functional requirements

### Security
- Use environment variables for secrets and a committed `.env.example` containing placeholders only.
- Enforce HTTPS in production and secure cookies.
- Use least-privilege database credentials and private database networking where supported.
- Use SQLAlchemy parameterized operations; never build SQL from untrusted strings.
- Validate and normalize inputs server-side.
- Add security headers appropriate to the application.
- Keep dependencies pinned or constrained and update them deliberately.
- Never log passwords, tokens, full credentials, or unnecessary personal data.
- Avoid public directory listings and untrusted file serving.
- Keep security controls in place throughout development, not as a final-stage patch.

### Reliability and recovery
- PostgreSQL is the system of record for content, users, enquiries, and media metadata.
- Production database backups and documented restore steps are mandatory.
- Verify a restore before launch and periodically thereafter.
- Application containers must be treated as ephemeral. User-uploaded media belongs in Cloudinary, not local disk.
- Monitor application errors and availability with low-cost tools.

### Performance and accessibility
- Use responsive images and lazy loading for below-the-fold portfolio images.
- Avoid unnecessary JavaScript and heavy client libraries.
- Support keyboard navigation, visible focus, meaningful alt text, semantic HTML, and readable contrast.
- Test responsive behaviour and key flows in current desktop and mobile browsers.
- Performance targets should be measured rather than claimed without evidence.

## 8. Hosting budget and provider decision

### Confirmed preferences
- Low monthly budget.
- Cloudinary for photography.
- Existing email account integration.

### Provider comparison and decision rule
- **Render (preferred candidate):** official pricing currently describes a July 2026 snapshot of roughly US$13/month for an always-on Starter web service plus Basic-256mb PostgreSQL on Hobby, before usage growth. Paid PostgreSQL includes point-in-time recovery; Hobby workspace recovery window is three days. Free PostgreSQL expires after 30 days and has no managed backups, so it is not acceptable for production.
- **Railway (alternative):** Hobby is US$5/month minimum and includes US$5 of resource usage. Additional usage is billed by RAM, CPU, storage, and egress. It may be cheaper for a small workload, but US$5 is not a guaranteed all-in cost for an always-on app and database; an independent backup/restore plan must be tested.
- **Cloudinary Free:** US$0/month with 25 monthly credits. Storage, transformations, and image bandwidth consume the same credit allowance; the Free plan's image file-size limit is 10 MB.
- **Gmail:** use the existing account only after checking account type, authentication, SMTP connectivity, sending limits, and spam handling. App passwords require 2-Step Verification where supported and are not Google's preferred method where a safer supported authentication method exists.

**Selection:** retain Render as the preferred production host for the initial architecture because its costs are easier to budget and paid PostgreSQL has documented recovery capabilities. Before creating paid services, verify current checkout prices, region, database storage, service size, bandwidth assumptions, tax/currency conversion, and backup needs. Railway can replace Render only after a cost estimate and recovery test demonstrate a real advantage. This is a preferred selection, not a claim that a live account or service has already been created.

## 9. Acceptance criteria for launch

- [ ] Five public pages work and are responsive.
- [ ] No excluded launch feature is accidentally exposed.
- [ ] PostgreSQL is used in local, test, staging, and production environments.
- [ ] Schema changes are tracked through migrations.
- [ ] Administrator login, authorization, CSRF protection, and session settings are tested.
- [ ] Admin can manage services, approved page content, portfolio projects, image references, YouTube links, and enquiries.
- [ ] Cloudinary uploads are validated; secrets remain server-side; no uploaded media depends on the application filesystem.
- [ ] Contact enquiries persist before email attempts.
- [ ] Email failures do not lose enquiries and can be retried.
- [ ] Tests cover success, validation errors, unauthorized access, upload errors, database failures, and email failures.
- [ ] HTTPS, production configuration, safe error pages, logging, and basic monitoring are active.
- [ ] A PostgreSQL backup can be restored successfully.
- [ ] Domain and DNS are configured after domain ownership is confirmed.
- [ ] Final content and portfolio media are approved by the business.
- [ ] No claim that tests, backups, or delivery work unless it has actually been executed and verified.

## 10. Dependencies and unresolved items

Before production:
1. Confirm whether `factboxconsult.com` has been purchased and who controls DNS.
2. Confirm the exact Gmail account to send from and the official enquiry recipient.
3. Confirm access to Cloudinary and set usage alerts/monitoring.
4. Verify provider checkout prices and region availability.
5. Obtain approved copy, project descriptions, photographs, client/partner logo permissions, and YouTube URLs.
6. Set the initial administrator credential securely.
7. Complete a backup-and-restore rehearsal.

## 11. Official pricing and technical references

Prices and limits should be rechecked at provisioning because vendors can change them.

- Render pricing: https://render.com/pricing
- Render free-tier limitations: https://render.com/docs/free
- Render PostgreSQL: https://render.com/docs/postgresql
- Render PostgreSQL backups and recovery: https://render.com/docs/postgresql-backups
- Render compute plans: https://render.com/docs/compute-plans
- Railway pricing: https://railway.com/pricing
- Railway resource pricing: https://docs.railway.com/pricing/plans
- Cloudinary pricing: https://cloudinary.com/pricing
- Cloudinary plan comparison: https://cloudinary.com/pricing/compare-plans
- Cloudinary billing and credits: https://cloudinary.com/documentation/billing_and_plans
- Google Workspace Gmail SMTP: https://knowledge.workspace.google.com/admin/gmail/send-email-from-a-printer-scanner-or-app
- Google app passwords: https://support.google.com/mail/answer/185833
