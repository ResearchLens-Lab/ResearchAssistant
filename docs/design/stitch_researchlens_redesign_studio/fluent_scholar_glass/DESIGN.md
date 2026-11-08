---
name: Fluent Scholar Glass
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#3f4850'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#707881'
  outline-variant: '#bfc7d2'
  surface-tint: '#006398'
  primary: '#006194'
  on-primary: '#ffffff'
  primary-container: '#007bb9'
  on-primary-container: '#fdfcff'
  inverse-primary: '#93ccff'
  secondary: '#006591'
  on-secondary: '#ffffff'
  secondary-container: '#39b8fd'
  on-secondary-container: '#004666'
  tertiary: '#006387'
  on-tertiary: '#ffffff'
  tertiary-container: '#007da9'
  on-tertiary-container: '#fcfcff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cce5ff'
  primary-fixed-dim: '#93ccff'
  on-primary-fixed: '#001d31'
  on-primary-fixed-variant: '#004b73'
  secondary-fixed: '#c9e6ff'
  secondary-fixed-dim: '#89ceff'
  on-secondary-fixed: '#001e2f'
  on-secondary-fixed-variant: '#004c6e'
  tertiary-fixed: '#c4e7ff'
  tertiary-fixed-dim: '#7bd0ff'
  on-tertiary-fixed: '#001e2c'
  on-tertiary-fixed-variant: '#004c69'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.03em
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.025em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.005em
  label-lg:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  code-citation:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0em
  code-inline:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 0.75rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system establishes an atmospheric, hyper-focused research environment blending Windows 11 Fluent 2 design principles, Apple macOS floating chrome dynamics, and academic editorial rigor. Designed for principal investigators, doctoral researchers, and data-intensive intelligence analysts, the platform rejects enterprise clutter in favor of airy clarity, optical balance, and frictionless cognitive flow.

The aesthetic fuses modern **Fluent Glassmorphism** with soft structural depth:
- **Floating Island Architecture:** Total elimination of legacy full-height left navigation bars and bottom-pinned user cards. Chrome lives in detached, floating translucent islands, pill controls, and contextual overlays that let content breathe.
- **Atmospheric Luminosity:** Surfaces feature optical layering via subtle frosted materials (`Mica` and `Acrylic` abstractions), translucent borders, and pale sky-tinted ambient glows.
- **Precision Typography:** Technical exactness meets modern humanist editorial polish, balancing sweeping categorical overviews with dense, monospaced citations and algorithmic matrices.
- **Kinetic Polish:** Cards subtly lift on hover, interactive boundaries reveal sky-blue refraction glows, and modal panels glide into view over high-blur canvas scrims.

## Colors

The palette balances clean luminance with directional sky-blue accents to denote discovery, verification, and interactive depth.

### Core Role Assignments
- **Primary (`#0284C7`):** Direct visual anchors, primary action triggers, active tab indicators, and verified citation tokens.
- **Secondary (`#0EA5E9`):** Accent highlights, interactive hover elevations, and dynamic search filter fills.
- **Tertiary (`#38BDF8`):** Glow rings, focal emphasis underlines, and luminous border reflections.
- **Neutral Canvas (`#FFFFFF` to `#F8FAFC`):** Pure white base canvas layered with crisp off-white surface tiers (`#F1F5F9`, `#E2E8F0`).
- **Typography Tone:** Heading and high-priority data points render in deep slate black (`#0F172A`). Descriptive text, metadata, and structural chrome typography render in balanced slate (`#475569`), with muted helper text in `#64748B`.
- **Translucent Overlays:** Glass surfaces utilize `rgba(255, 255, 255, 0.72)` combined with borders tinted in `#BAE6FD` (30% to 50% opacity) to evoke frosted optical crystal.

## Typography

The type system blends the open, geometric personality of **Plus Jakarta Sans** for headers with the clarity and rhythm of **Inter** for dense synthesized abstracts, tables, and narrative texts. **JetBrains Mono** serves as the technical substrate, grounding DOI links, dataset matrices, citation anchors, and formulas.

- **Headlines:** Set with tightened tracking (`-0.015em` to `-0.03em`) to anchor floating cards with confident authority.
- **Academic Body:** Inter is set with balanced leading (1.6x) to preserve readability across split-view reading panes and multi-column paper comparative grids.
- **Technical Badges & Citations:** Formatted in JetBrains Mono using uppercase tracking or strict mono tabular figures to visually distinguish machine metadata from human synthesis.

## Layout & Spacing

The layout is grounded in a fluid modular architecture designed around multi-column analysis without sidebar lock-in:

- **Floating Glass Command Ribbon:** Anchored at the top viewport with dynamic margin offsets (`margin: 1.25rem 2rem`). It houses project switchers, search bars, and profile hubs inside an integrated acrylic pill array.
- **Grid Structure:** A 12-column dynamic fluid grid system with `1.5rem` gutters on desktop, adapting to a 4-column layout on mobile devices.
- **Card Clustering:** Primary modules (document viewer, graph explorer, literature table, synthesizer) sit on decoupled cards with internal padding of `space-lg` (24px) and element margins scaled on an 8pt modular rhythm.
- **Floating Contextual Dock:** An optional right-anchored or bottom-centered floating utility dock provides quick access to tools (e.g., citation export, highlighter, AI copilot) without eating horizontal canvas width.
- **Responsive Adaptation:**
  - **Desktop (>1280px):** Multi-pane split screen with side-by-side comparative views and hovering inspector panels.
  - **Tablet (768px - 1279px):** 2-column stacked flow with ribbon collapsing into a compact floating bar.
  - **Mobile (<768px):** Single-column stack with persistent floating glass bottom-control pill and bottom-sheet command drawer.

## Elevation & Depth

Visual hierarchy uses a refined Windows 11 Fluent material scheme featuring soft multi-layered shadows infused with cool sky undertones:

- **Level 0 (Base Canvas):** `#F8FAFC` to `#FFFFFF` matte surface with no elevation.
- **Level 1 (Modular Research Cards):** Crisp pure white `#FFFFFF` or semi-opaque `rgba(255, 255, 255, 0.85)` surface with a double drop shadow: `0 1px 3px rgba(15, 23, 42, 0.04), 0 8px 24px -4px rgba(2, 132, 199, 0.06)`. Surrounded by a 1px border of `rgba(224, 242, 254, 0.8)`.
- **Level 2 (Floating Command Ribbon & Hovered Cards):** Backdrop-filter blur of `16px` to `20px` saturation `140%`, surface `rgba(255, 255, 255, 0.78)`, elevation `0 12px 32px -4px rgba(2, 132, 199, 0.12), 0 4px 12px rgba(15, 23, 42, 0.03)`, border `1px solid rgba(186, 230, 253, 0.9)`. Hovering over a card activates an elevation transition, scaling the drop shadow and lifting the card by 2px on the Y axis.
- **Level 3 (Modal Sheets, Search Palettes & Floating Inspectors):** Surface `rgba(255, 255, 255, 0.92)`, blur `24px`, casting an atmospheric perimeter glow: `0 24px 48px -8px rgba(15, 23, 42, 0.14), 0 0 0 1px rgba(186, 230, 253, 0.5), 0 0 24px rgba(56, 189, 248, 0.15)`.

## Shapes

The design uses generous corner radii to create an organic, tactile feel:

- **Standard Cards & Modules:** Radius set to `1.25rem` (20px) to `1.5rem` (24px) (`rounded-2xl` and `rounded-3xl`), framing complex academic datasets within approachable panels.
- **Interactive Buttons & Chips:** Full pill radius (`9999px`) for segmented controllers, status pills, and interactive search filters.
- **Input Fields & Dropdowns:** Standardized at `0.75rem` (12px) to match the internal radius of parent container panels.
- **Modals & Command Palettes:** Softened with a `1.5rem` (24px) radius to maintain harmony with floating viewport borders.

## Components

### 1. Floating Command Ribbon (Navigation)
- **Structure:** Detached pill-shaped or continuous rounded ribbon (`height: 64px`, `border-radius: 9999px` or `20px`) floating 20px below the top viewport edge.
- **Styling:** Frosted acrylic glass (`rgba(255, 255, 255, 0.75)`, blur `16px`), micro-border `#BAE6FD`.
- **Contents:** Integrated circular workspace switcher on the left, centered dynamic omni-search input (`Cmd+K`), and segmented view pills with user profile anchor on the right.

### 2. Buttons & Actions
- **Primary Button:** Gradient-tinted solid fill (`#0284C7` transitioning slightly to `#0EA5E9`), pure white text, pill-shaped (`border-radius: 9999px`), glowing soft focus ring `0 0 0 3px rgba(56, 189, 248, 0.35)`.
- **Secondary Button:** Translucent off-white `rgba(240, 249, 255, 0.7)`, border `1px solid #BAE6FD`, text `#0284C7`, lifting subtly on hover with a sky-blue ambient shadow.
- **Ghost/Tertiary:** No fill, text `#475569`, turning into `#0F172A` with a subtle `#F1F5F9` pill background on hover.

### 3. Modular Research Cards
- **Construction:** Background `#FFFFFF` (or `rgba(255, 255, 255, 0.88)` on canvas `#F8FAFC`), corner radius `20px`, border `1px solid rgba(224, 242, 254, 0.7)`.
- **Micro-Interaction:** On cursor hover, transforms with `translateY(-2px)`, shadow increases from Level 1 to Level 2 with a sky-blue ambient tint.
- **Header:** Features an embedded label chip, high-contrast title in Plus Jakarta Sans, and top-right icon buttons for expand/fullscreen and citation export.

### 4. Interactive Chips & Metadata Pills
- **Academic Citation Chip:** Monospace text in JetBrains Mono (`11px`), background `#E0F2FE`, text `#0369A1`, border `1px solid rgba(56, 189, 248, 0.3)`, pill-shaped. Hover triggers an underlined tooltip preview of the author/year.
- **Topic Filter Chip:** Pill-shaped with a soft `#F1F5F9` base; when active, transitions into `#0284C7` with white text and an integrated dismiss cross icon.

### 5. Input Fields & Omni-Search
- **Omni-Search Bar:** Floating rounded pill with inset search icon, JetBrains Mono keyboard shortcut badge (`⌘K`), subtle placeholder `#64748B`.
- **Focus State:** Background shifts to `#FFFFFF`, border transitions to `#38BDF8`, enveloped by an ambient focus glow `0 0 0 4px rgba(14, 165, 233, 0.15)`.

### 6. Checkboxes & Selection Controls
- **Form Factors:** Checkboxes feature `6px` rounded corners; radio pills are fully circular.
- **Selected State:** Solid `#0284C7` background housing an optical crisp-white SVG checkmark, flanked by a slate label `#1E293B`.

### 7. Floating Action Dock / Contextual Inspector
- **Architecture:** Hovering vertical or horizontal capsule dock pinned 24px above the bottom viewport or resting as an anchored right rail.
- **Visuals:** Heavy frosted acrylic (`rgba(255, 255, 255, 0.8)`), containing icon actions (AI Synthesis, Cross-Reference, BibTeX Export) separated by hairline sky-blue dividers (`#E0F2FE`).