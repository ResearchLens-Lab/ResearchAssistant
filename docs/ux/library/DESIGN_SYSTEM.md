# RESEARCHLENS — DESKTOP DESIGN SYSTEM & BRAND TOKENS
**Application:** ResearchLens  
**Platform:** Next.js 15, React 19, Tailwind CSS  
**Target Atmosphere:** Native Windows Desktop Academic Reference Manager  

---

## 1. Brand Tokens & Typography

### Logo: ResearchLens Optical Vector
- **Symbol**: A precision optical research lens enclosing an academic folded document with engraved research passage lines, angled with a 45° focal reticle.
- **Component**: `frontend/src/components/brand/ResearchLensLogo.jsx`
- **Scalability**: Sharp rendering from 16×16 favicon to 64×64 splash headers.
- **Tagline**: *"Find the evidence. Understand the research."*

### Color Palette: Academic Restraint
- **Primary Ink**: `var(--rl-ink)` (`#0f172a` / zinc-900) — high-contrast academic legibility.
- **Canvas / Neutral Background**: `var(--rl-canvas)` (`#f8fafc` / slate-50) — low-eyestrain reading surface.
- **Brand Blue Accent**: `var(--rl-primary)` (`#2678b8` / primary blue) — focal interactive element color.
- **Brand Tint**: `var(--rl-tint)` (`#f0f7fc` / sky-50/70) — subtle content grouping and information strips.
- **Border**: `var(--rl-border)` (`#e2e8f0` / zinc-200) — crisp architectural dividers.
- **Status Accents**:
  - Ready / Verified: `#047857` (emerald-700) / `#ecfdf5` (emerald-50)
  - Processing / Live: `#0284c7` (sky-600) / `#f0f9ff` (sky-50)
  - Warning / Attention: `#b45309` (amber-700) / `#fffbeb` (amber-50)
  - Failure: `#be123c` (rose-700) / `#fff1f2` (rose-50)

---

## 2. Tactile 3D Depth & Elevation System

To achieve the tactile feel of a premium desktop application without game-like distortion, the system uses a coordinated 4-tier elevation hierarchy:

### Tier 1: Rest Surface
- **Class**: `shadow-[0_2px_8px_-2px_rgba(0,0,0,0.05)] border border-zinc-200/90`
- **Application**: Cards, inputs, toolbar segments.

### Tier 2: Interactive Lift (Hover)
- **Class**: `hover:-translate-y-0.5 hover:shadow-[0_12px_28px_-6px_rgba(38,120,184,0.18)] hover:border-sky-300 transition-all duration-200`
- **Application**: Project cards, primary and secondary action buttons.

### Tier 3: Tactile Pressed State (Active)
- **Class**: `active:translate-y-0 active:shadow-xs transition-all duration-75`
- **Application**: Buttons, pills, interactive cards.

### Tier 4: Elevated Dialog Surface
- **Class**: `shadow-[0_24px_64px_-16px_rgba(0,0,0,0.22)] border border-zinc-200/90`
- **Application**: Modals, dropdown menus, context menus.

---

## 3. Reusable Component Inventory

| Component | Path | Responsibility |
|---|---|---|
| `ResearchLensLogo` | `components/brand/ResearchLensLogo.jsx` | Reusable SVG brand symbol across headers, footers, favicons |
| `TopNav` | `components/layout/TopNav.jsx` | Compact desktop application header with route indicators |
| `PaperCard` | `components/papers/PaperCard.jsx` | Tactile project card with descriptions, owner state, and real-time previews |
| `PaperGrid` | `components/papers/PaperGrid.jsx` | Responsive 3-column desktop layout container |
| `PaperTableView` | `components/papers/PaperTableView.jsx` | High-density tabular project overview with description snippets |
| `CreatePaperModal` | `components/papers/CreatePaperModal.jsx` | Reusable project creation dialog with mandatory title & description |
| `IngestDropzone` | `components/upload/IngestDropzone.jsx` | Professional multi-file upload, queue inspector, and stage tracker |
| `CitationBadge` | `components/citations/CitationBadge.jsx` | Inline citation badge with semantic `<span>` tooltip architecture |
| `Badge` | `components/ui/badge.jsx` | Semantic inline `<span>` badge supporting all UI indicators |

