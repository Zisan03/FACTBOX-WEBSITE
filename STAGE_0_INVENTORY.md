# Stage 0 — Repository Tree, Stitch Inventory & Environment Report

**Date:** 18 October 2026  
**Status:** Completed Stage 0 Inspection Baseline  
**Governing Documents:** [ROADMAP.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/ROADMAP.md), [PRD.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/PRD.md), [ARCHITECTURE.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/ARCHITECTURE.md), [DESIGN.md](file:///c:/Users/user/Desktop/FACTBOX%20WEBSITE/design_reference/stitch_fact_box_cinematic_showcase/cinematic_documentary_intelligence/DESIGN.md)

---

## 1. Repository Structure Inventory

```text
FACTBOX WEBSITE/
├── .agents/                               # Customizations and skills
├── .env.example                           # Committed environment configuration template
├── .git/                                  # Git version control repository
├── .gitignore                             # Ignore rules for python, secrets, venv
├── ABOUT FACT BOX CONSULT.docx             # Client company profile, RC 7592601, official copy
├── AGENTS.md                              # Coding agent binding contract
├── ARCHITECTURE.md                        # Target architecture & deployment topology
├── ARCHITECTURE_DECISIONS.md              # ADR-001 through ADR-009
├── CLAUDE.md                              # Agent entry point
├── DATABASE_SCHEMA.md                     # V1 relational database schema
├── PRD.md                                 # Product requirements, scopes, and exclusions
├── README_PROJECT_DOCS.md                 # Index of project specifications
├── ROADMAP.md                             # Staged roadmap & exit gates (Stage 0 to Stage 7)
├── START_HERE.md                          # Initial bootstrap instructions
├── TESTING_AND_RELEASE_CHECKLIST.md       # Pre-launch and release gates
├── requirements.txt                       # Baseline Python package requirements
├── design_reference/                      # Visual reference assets and Stitch output
│   ├── fact_box_logo_reference.jpg        # Brand logo asset
│   └── stitch_fact_box_cinematic_showcase/ # Google Stitch prototype screens & design tokens
└── factbox-consult/                       # Scaffold folder (data, instance, static, templates, venv)
```

---

## 2. Google Stitch Reference Inventory

Source location: `design_reference/stitch_fact_box_cinematic_showcase/`

### A. Design Tokens & Brand System
Documented in: `cinematic_documentary_intelligence/DESIGN.md`

* **Aesthetic Direction:** Editorial Authority, Cinematic Depth, Minimalist luxury with dark accents and institutional credibility.
* **Palette:**
  * **Primary Deep Green:** `#177a3d` (active states, brand accents, structural lines) / `#005f2b`
  * **Secondary Dark Green:** `#0b5d2a` / `#206c37` (deep footers, high-contrast dark sections)
  * **Accent Lime Green:** `#a6ff4d` / `#a9ffb8` / `#b8ff74` (high-visibility interactive highlights, tags, fact-card left accents)
  * **Neutrals & Surfaces:**
    * Surface light: `#fcf9f8`, container `#f0edec`, pure white `#ffffff`
    * Inverse/Dark surface: `#1c1b1b` (pure photography backgrounds), `#313030`
* **Typography:**
  * Headlines / Display: **Poppins** (Bold/SemiBold, 700/600, tight tracking)
  * Body & Metadata: **Inter** (Regular/SemiBold, line-height 1.6)
  * Overlines & Chips: `label-caps` in uppercase Inter (12px, letter-spacing 0.1em)
* **Layout & Spacing:**
  * Container max width: `1280px`
  * Section gap: `120px` (generous narrative breathing space)
  * Desktop gutter: `64px+` (cinematic letterboxed feel)
  * Mobile margin: `20px`
  * Card radius: `8px` to `16px` (media/player containers: `16px`)

### B. Confirmed V1 Public Pages vs Excluded Screens

| Screen / Prototype Directory | V1 Scope Status | Mapping in Target Architecture |
| :--- | :--- | :--- |
| `fact_box_consult_home` & `fact_box_consult_home_1` | **APPROVED** | `/` (Home blueprint) |
| `fact_box_consult_about_us` | **APPROVED** | `/about` (Public blueprint) |
| `fact_box_consult_services` | **APPROVED** | `/services` (Public blueprint) |
| `fact_box_consult_our_work` | **APPROVED** | `/work` (Public blueprint, category filter + YouTube modal/embed) |
| `fact_box_consult_contact_us` (variants 1 & 2) | **APPROVED** | `/contact` (Contact blueprint, DB persistence before SMTP) |
| `fact_box_consult_clients_partners` & `..._updated` | **EXCLUDED** | No separate page in V1; approved logos may appear in Home/Portfolio sections |
| `fact_box_consult_our_team` | **EXCLUDED** | Team profiles deferred beyond V1 |
| `fact_box_consult_request_a_quote` | **EXCLUDED** | Quote request merged into standard `/contact` enquiry flow |
| Blog / Articles / Insights | **EXCLUDED** | Deferred beyond V1 |
| Testimonials / Case Studies | **EXCLUDED** | Deferred beyond V1 |
| Individual Project Detail Pages | **EXCLUDED** | Single `/work` page with filtering, descriptions, and media |
| Public User Registration | **EXCLUDED** | Single administrator provisioned via CLI |

---

## 3. Environment & Workspace Status

1. **Operating System:** Windows (PowerShell shell environment).
2. **Version Control:** Git repository initialized; branch `master`; clean working tree; baseline commit `bb30d1a`.
3. **Secrets & Security:**
   * `.env.example` verified: uses dummy placeholders; no real secrets committed.
   * `.gitignore` verified: ignores `.env`, `*.db`, `*.sqlite`, `venv/`, `__pycache__/`, test caches.
4. **Python Version:** Python 3.12.9 detected.
5. **PostgreSQL Check:**
   * Neither `psql` command, Windows PostgreSQL service, nor Docker was found in active PATH/services.
   * **Mandate (ADR-001):** PostgreSQL is required in all environments (development, tests, staging, production); SQLite fallback is strictly prohibited.
   * **Action Required:** Provision a dedicated development PostgreSQL database and an isolated test database.
