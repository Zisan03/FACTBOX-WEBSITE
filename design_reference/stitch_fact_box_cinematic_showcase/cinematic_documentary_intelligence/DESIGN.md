---
name: Cinematic Documentary Intelligence
colors:
  surface: '#fcf9f8'
  surface-dim: '#dcd9d9'
  surface-bright: '#fcf9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f2'
  surface-container: '#f0edec'
  surface-container-high: '#ebe7e7'
  surface-container-highest: '#e5e2e1'
  on-surface: '#1c1b1b'
  on-surface-variant: '#3f493f'
  inverse-surface: '#313030'
  inverse-on-surface: '#f3f0ef'
  outline: '#6f7a6e'
  outline-variant: '#becabc'
  surface-tint: '#006d33'
  primary: '#005f2b'
  on-primary: '#ffffff'
  primary-container: '#177a3d'
  on-primary-container: '#a9ffb8'
  inverse-primary: '#7eda92'
  secondary: '#206c37'
  on-secondary: '#ffffff'
  secondary-container: '#a4f1af'
  on-secondary-container: '#25703b'
  tertiary: '#325c00'
  on-tertiary: '#ffffff'
  tertiary-container: '#427700'
  on-tertiary-container: '#b8ff74'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#9af7ac'
  primary-fixed-dim: '#7eda92'
  on-primary-fixed: '#00210b'
  on-primary-fixed-variant: '#005225'
  secondary-fixed: '#a7f4b1'
  secondary-fixed-dim: '#8cd897'
  on-secondary-fixed: '#00210a'
  on-secondary-fixed-variant: '#005323'
  tertiary-fixed: '#a1fa48'
  tertiary-fixed-dim: '#87dc2b'
  on-tertiary-fixed: '#0e2000'
  on-tertiary-fixed-variant: '#2b5000'
  background: '#fcf9f8'
  on-background: '#1c1b1b'
  surface-variant: '#e5e2e1'
typography:
  display-lg:
    fontFamily: Poppins
    fontSize: 64px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Poppins
    fontSize: 40px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-xl:
    fontFamily: Poppins
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.2'
  headline-lg:
    fontFamily: Poppins
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-md:
    fontFamily: Poppins
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.0'
    letterSpacing: 0.1em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  container-max: 1280px
  gutter: 24px
  margin-mobile: 20px
  margin-desktop: 64px
  section-gap: 120px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

This design system establishes a high-authority, cinematic presence for a media consultancy at the intersection of investigative journalism and premium documentary production. The aesthetic blends the intellectual rigor of global NGOs with the immersive, high-fidelity visual storytelling of modern streaming platforms.

The style is a sophisticated **Minimalism** infused with **Cinematic Depth**. It prioritizes high-impact imagery, expansive whitespace, and meticulous typographic hierarchy to evoke feelings of trust, transparency, and prestige. Transitions should feel intentional and rhythmic, mimicking the pacing of a well-edited documentary.

**Key Principles:**
- **Editorial Authority:** Every layout should feel like a curated feature story or a premium film pitch.
- **Visual Breathability:** Extensive use of "negative space" to focus the eye on critical data points and powerful photography.
- **Modern Luxury:** Subtle use of glassmorphism and soft shadows to provide a sense of physical quality without clutter.

## Colors

The palette is rooted in a deep, institutional green that represents growth, truth, and the Nigerian landscape. 

- **Primary Deep Green (#177A3D):** Used for primary brand moments, active states, and structural elements.
- **Secondary Dark Green (#0B5D2A):** Reserved for deep backgrounds, heavy footers, and high-contrast text to ensure an expensive, grounded feel.
- **Accent Lime Green (#A6FF4D):** A high-energy, "digital-first" neon used sparingly for calls-to-action, status indicators, and critical highlights. It provides the "cinematic spark" against dark backgrounds.
- **Neutral System:** Utilizes a true black for high-end photography backdrops and a pure white for report-style readability. Subtle dark gradients (Deep Green to Black) should be used to create depth in immersive sections.

## Typography

The typography strategy balances the bold, geometric impact of **Poppins** for headlines with the clinical, systematic clarity of **Inter** for body copy.

- **Headlines:** Must be set with tight letter-spacing to maintain a "poster" aesthetic. Large display sizes should be used for hero sections to mirror documentary title cards.
- **Body Text:** Inter is utilized for its exceptional readability in data-heavy reports and consultancy briefs. Maintain a generous line height (1.6) to prevent eye fatigue.
- **Labels:** Use the `label-caps` style for categories, metadata, and overlines. This adds a level of institutional "fact-box" precision to the UI.

## Layout & Spacing

The layout philosophy follows a **Fixed-Fluid Hybrid Grid**. Content is housed within a 12-column grid on desktop, but margins are intentionally wide (64px+) to create a "letterboxed" cinematic feel.

- **Vertical Rhythm:** Use a "Section-Gap" of 120px between major narrative blocks to allow the design to breathe.
- **The "Fact Box" Layout:** Key data points should be placed in 4-column containers with heavy internal padding, creating distinct "modules" of information.
- **Photography:** Images should frequently break the grid, either spanning 100% of the viewport width or bleeding off one side of the screen to suggest a larger world beyond the frame.

## Elevation & Depth

This design system uses **Tonal Layering** and **Ambient Shadows** to create a sophisticated sense of hierarchy.

- **Surface Tiers:** On light modes, use extremely subtle off-white (#F9F9F9) for secondary cards. In dark modes, use semi-transparent overlays (Black at 40% opacity) with a 20px backdrop blur (Glassmorphism) over imagery.
- **Shadows:** Avoid harsh, dark shadows. Use "Ambient Glows"—shadows with a large blur radius (30px+) and low opacity (5-8%), occasionally tinted with the Primary Deep Green to suggest light reflecting off surfaces.
- **Depth:** Elements representing "Consultancy Reports" or "Whitepapers" should have a higher elevation than standard UI buttons, suggesting they are physical objects to be picked up and read.

## Shapes

The shape language is refined and professional. 

- **Containers:** A `rounded-md` (0.5rem) or `rounded-lg` (1rem) standard is applied to cards and input fields to soften the "institutional" feel while remaining serious.
- **Buttons:** Use `rounded-lg` for a modern, tactile feel. Do not use full pills, as they appear too casual for high-end consultancy.
- **Media:** Photography and Video players should always use a consistent `16px` corner radius to match the overall UI container language.

## Components

- **Buttons:** 
  - *Primary:* Solid Deep Green with white text. High-contrast hover state using the Accent Lime Green.
  - *Secondary:* Ghost style with a Deep Green 2px border.
- **The "Fact Card":** A specialized card component with a 4px left-border of Accent Lime Green, used to highlight key statistics or pull-quotes from documentary research.
- **Interactive Timelines:** A vertical line element (Secondary Green) with soft-glow nodes to represent production phases or historical context in documentaries.
- **Inputs:** Minimalist bottom-border only or very light grey outlines. Focus states should trigger a subtle Primary Green glow.
- **Chips/Tags:** Used for "Industry Tags" (e.g., *Sustainability*, *Governance*). Small, uppercase Inter font, with a light green background and dark green text.
- **Navigation:** A transparent header that blurs and darkens on scroll, ensuring visibility over high-quality hero imagery.