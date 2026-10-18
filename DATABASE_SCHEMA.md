# Database Schema Specification — V1

**Status:** implementation baseline; review alongside PRD and architecture before the first migration. Use PostgreSQL only in every environment.

## General conventions
- Use SQLAlchemy models and Flask-Migrate/Alembic migrations.
- Use UUID primary keys for externally addressable records where convenient; internal integer IDs are acceptable only if applied consistently. Preferred V1: UUID for all domain tables to avoid exposing sequential IDs.
- Store timestamps as timezone-aware UTC (`created_at`, `updated_at` where relevant).
- Add database constraints as well as application validation. Normalize emails for lookup; do not assume case-sensitive uniqueness.
- Use `NOT NULL` for required fields, foreign keys with deliberate delete behavior, indexes for lookup/filter/order fields, and explicit ordering fields.
- Never persist media binary content in PostgreSQL. Store Cloudinary public ID and delivery metadata.
- Avoid a generic key/value content system. Use a small editable-page-content model only for specifically approved fields; never allow admin users to edit template code or arbitrary HTML.

## 1. AdminUser
Fields:
- `id` UUID PK
- `email` string, required, normalized, unique, indexed
- `password_hash` string, required
- `is_active` boolean, required, default true
- `last_login_at` timestamptz nullable
- `created_at`, `updated_at` timestamptz

Rules: no public registration; create the first account through a protected CLI command. No default password. Login throttling and session protections are implemented outside the model. Avoid adding roles until a real multi-role requirement exists; all authorized users are administrators in V1.

## 2. PortfolioProject
Fields:
- `id` UUID PK
- `title` string, required
- `slug` string, required, unique, indexed
- `summary` text, required (short card description)
- `description` text, required (plain text/limited Markdown only if deliberately sanitized; do not accept arbitrary HTML)
- `category_id` FK to `PortfolioCategory`, required unless approved uncategorized support is needed
- `client_name` string nullable (only if publication is authorized)
- `project_date` date nullable
- `is_featured` boolean, required, default false
- `status` enum/string constrained to `draft` or `published`, required, default `draft`
- `display_order` integer, required, default 0
- `published_at` timestamptz nullable
- `created_at`, `updated_at` timestamptz

Rules: only published projects appear publicly. Public Our Work page contains cards and in-page/category filtering; no individual project route. Do not publish confidential client information without approval.

## 3. PortfolioCategory
Fields: `id` UUID PK; `name` string required; `slug` string required unique; `display_order` integer default 0; `is_active` boolean default true; timestamps.

Rules: category names/slugs unique; inactive categories should not be offered as new assignments, but historical projects must remain manageable. Public filters only include categories with published projects.

## 4. PortfolioImage
Fields:
- `id` UUID PK
- `project_id` FK to `PortfolioProject`, required, indexed, `ON DELETE CASCADE`
- `cloudinary_public_id` string required, unique
- `secure_url` string required (or generated from validated stored metadata if implementation decision is recorded)
- `alt_text` string required
- `caption` string nullable
- `width`, `height` integers nullable
- `display_order` integer required, default 0
- `created_at` timestamptz

Rules: server-mediated or signed Cloudinary uploads; secret remains server-side. Restrict format/size, verify content, and use responsive optimized delivery. Deleting/replacing assets must handle Cloudinary and DB failures without silently losing the only reference. Do not delete an asset still referenced by another record.

## 5. PortfolioVideo
Fields: `id` UUID PK; `project_id` FK required, indexed, `ON DELETE CASCADE`; `youtube_video_id` string required; `title` string nullable; `display_order` integer default 0; `created_at` timestamptz.

Rules: accept recognized YouTube URL forms, parse and persist the video ID rather than arbitrary embed HTML; render only the trusted `youtube-nocookie.com` embed URL generated from the validated ID. Never render admin-supplied HTML as safe.

## 6. Service
Fields: `id` UUID PK; `title` string required; `slug` string required unique; `summary` text required; `description` text required; `icon_key` string nullable (from an allowlist, not arbitrary HTML); `display_order` integer default 0; `is_published` boolean default false; timestamps.

Rules: only published services appear publicly. Editable text must be escaped/sanitized according to the approved content format.

## 7. PageContent
Fields: `id` UUID PK; `page_key` string required; `content_key` string required; `content_value` text required; `updated_by_id` FK to AdminUser nullable; `updated_at` timestamptz.

Constraints: unique (`page_key`, `content_key`). Only explicitly allowlisted content keys can be edited. Do not store template fragments, scripts, arbitrary HTML, secrets, or layout configuration here. If the first release only needs a few fields, seed them via migrations or code defaults and expand after review rather than building an unrestricted CMS.

## 8. PartnerLogo (optional, only if confirmed needed on approved pages/portfolio)
Fields: `id` UUID PK; `name` string required; `logo_cloudinary_public_id` string required; `logo_secure_url` string required; `website_url` string nullable; `alt_text` string required; `display_order` integer default 0; `is_published` boolean default false; timestamps.

This is not a separate public Clients & Partners page. Use only in an approved page section or related portfolio context. If logos can be adequately represented as project-linked assets in the initial content, defer this table rather than build unused functionality.

## 9. Enquiry
Fields:
- `id` UUID PK
- `full_name` string required
- `organization` string nullable
- `email` string required, normalized for comparison
- `phone` string nullable
- `subject` string required (or controlled enquiry topic)
- `message` text required
- `status` enum/string constrained to `new`, `in_review`, `closed`, required default `new`
- `notification_status` enum/string constrained to `pending`, `sent`, `failed`, required default `pending`
- `notification_attempts` integer required default 0
- `notification_last_attempt_at` timestamptz nullable
- `notification_sent_at` timestamptz nullable
- `notification_error_code` string nullable (safe short code; never persist credentials or raw provider secrets)
- `created_at`, `updated_at` timestamptz

Rules: validate length and format server-side, CSRF protect, rate-limit, and use a honeypot or other proportionate abuse control. Save and commit before attempting notification. On failure, retain the enquiry and provide authenticated retry. Do not expose enquiries publicly. Limit admin-visible message rendering to escaped text.

## 10. AdminAuditEvent (recommended, minimal)
Fields: `id` UUID PK; `admin_user_id` FK nullable; `event_type` string required; `entity_type` string nullable; `entity_id` UUID nullable; `occurred_at` timestamptz; `safe_metadata` JSONB nullable.

Rules: record key events such as login success/failure aggregates where appropriate, publish/unpublish, media changes, and enquiry notification retry. Do not store passwords, session tokens, full message bodies, or secrets. Define retention/access policy before production.

## Relationships and deletion policy
- Category -> projects: prevent deleting a category with projects until reassigned, or implement an explicit reassignment flow.
- Project -> images/videos: cascade DB metadata deletion only after the UI/service handles external asset cleanup safely.
- Admin user -> audit events: retain audit history if the account is deactivated; avoid cascading away audit records.
- Enquiries: no public deletion. Admin close/archive status is preferred over destructive deletion; any purge policy requires explicit approval.

## Required indexes and constraints
- Unique: admin email, project slug, category slug, service slug, page-content (`page_key`, `content_key`), Cloudinary public ID.
- Index: project status/category/display order, published date, enquiry created/status/notification status, media project/order.
- Add check constraints for enumerated statuses, non-negative order/attempt counters, and sensible string lengths.
- Use database-level foreign keys and transactions for multi-record edits.

## Before creating the first migration
1. Review whether `PartnerLogo` and `PageContent` are truly required for initial launch; do not overbuild.
2. Confirm contact form fields and whether project client names may be public.
3. Decide whether portfolio descriptions are plain text or a narrowly defined sanitized Markdown subset. Default: plain text with paragraph breaks.
4. Confirm UUID strategy and enum implementation for PostgreSQL.
5. Implement model constraints and tests, then generate and review the first migration. Do not use `create_all()` as the schema-management mechanism.
