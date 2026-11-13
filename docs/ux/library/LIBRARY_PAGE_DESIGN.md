# RESEARCHLENS — LIBRARY PAGE DESIGN SPECIFICATION
**Route:** `/papers`  
**Brand Identity:** ResearchLens · *"Find the evidence. Understand the research."*  
**Architecture:** Desktop-Style Academic Project Workspace  

---

## 1. Executive Summary & Design Rationale

The ResearchLens Library page (`/papers`) has been re-architected from a generic dashboard into a high-density, professional desktop research environment. Rather than presenting sparse cards with repetitive labels, the redesigned interface emphasizes project titles, research descriptions, verified local ownership, and real-time source indexing status.

```
+----------------------------------------------------------------------------------------------------+
|  [Logo] ResearchLens  Find the evidence. Understand the research.     [Library] [Desk] [Compare]   (User) |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  Your research projects  [03 Projects]                                  [+ Create project] [Add sources]
|  [Keep your research organized. Create a project for each study, then add the papers you need. ]   |
|                                                                                                    |
|              [  🔍 Search projects by title, description or source...  ]    [Sort ▾] [⊞][☰]         |
|                                                                                                    |
|  +---------------------------+  +---------------------------+  +---------------------------+       |
|  | Project Title             |  | Project Title             |  | Project Title             |       |
|  | Short research description|  | Short research description|  | Short research description|       |
|  | 👤 Just you · Private     |  | 👤 Just you · Private     |  | 👤 Just you · Private     |       |
|  | 4 sources · 3 ready       |  | 1 source · 1 ready        |  | 0 sources attached        |       |
|  | 📄 paper1.pdf       Ready |  | 📄 dataset.pdf      Ready |  |                           |       |
|  | 📄 paper2.pdf  Processing |  |                           |  |                           |       |
|  | Created Nov 12   Open →   |  | Created Nov 4    Open →   |  | Created Nov 3    Open →   |       |
|  +---------------------------+  +---------------------------+  +---------------------------+       |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Layout Structure & Visual Hierarchy

### A. Compact Application Header (`TopNav.jsx`)
- **Brand Mark**: Custom geometric ResearchLens logo featuring an optical lens ring with an embedded academic document geometry and 45° precision focal reticle.
- **Brand Tagline**: Replaced legacy "Evidence-first research" with `"Find the evidence. Understand the research."`
- **Navigation Controls**: Restrained pill tabs (`Library`, `Research Desk`, `Compare & Reports`) with subtle hover elevation and active state indicators.
- **User Control**: Compact profile pill displaying initials and active session status.

### B. Library Header & Actions
- **Heading**: `"Your research projects"` in bold 24px typography (`text-2xl font-bold tracking-tight text-zinc-900`).
- **Project Count Badge**: Embedded counter badge (`03 Projects`) where the two-digit number is rendered in bold primary blue (`var(--rl-primary)`).
- **Human-Readable Information Strip**: A softly tinted callout (`bg-[var(--rl-tint)]/80 border border-sky-100`) directly beneath the title stating:
  > *"Keep your research organized. Create a project for each subject or study, then add the papers you need."*
- **Action Group**:
  - Secondary: `+ Create project` (tactile outline button, plus icon, subtle elevation).
  - Primary: `Add sources` (tactile deep blue `#2678b8` with upload icon, layered shadow, hover lift `-0.5px`, active state).

### C. Balanced Search & Organization Toolbar
- **Centered Search Bar**: Max-width 480px, centered in the container with an integrated search icon and instant `X` clear button.
- **Multi-Field Instant Filtering**: Filters client-side across:
  - Project titles
  - Project descriptions / research abstracts
  - Attached document filenames and author lists
- **Sort Dropdown**:
  - `Recently created` (default chronological order)
  - `Project title (A–Z)` (alphabetical sorting)
  - `Most sources` (density-based ordering)
- **View Switcher**: Quick toggle between compact 3-column Card Grid (`PaperGrid`) and dense tabular list (`PaperTableView`).

---

## 3. Project Cards Specification (`PaperCard.jsx`)

Each card is constructed with layered elevation:
- **At Rest**: Subtle border `border-zinc-200/90` and micro-shadow `shadow-[0_2px_8px_-2px_rgba(0,0,0,0.05)]`.
- **Hover**: Smooth lift `hover:-translate-y-0.5`, boundary highlight `hover:border-sky-300`, and deep optical shadow `hover:shadow-[0_12px_28px_-6px_rgba(38,120,184,0.18)]`.
- **Active / Click**: Pressed feedback `active:translate-y-0`.

### Card Elements:
1. **Title**: Prominent 16px semibold text (`line-clamp-2`), transitioning to primary blue on card hover. The redundant `"RESEARCH PROJECT"` label has been eliminated.
2. **Description**: 2-line truncated summary (`line-clamp-2`). For legacy records without stored descriptions, displays clean italicized fallback: *"No description added yet"*.
3. **Collaborators / Ownership**: Displays authentic SEC-001 multi-tenant status (`"Just you · Private workspace"`). Never fabricates imaginary members.
4. **Source Counts & Status**:
   - Total sources count (e.g., `4 sources`).
   - Granular breakdown: `3 ready · 1 processing · 0 failed`.
5. **Source Previews**: Up to 2 compact rows rendering real filenames with real-time status badges (`Ready` in emerald, `Processing` in sky with micro-spinner, `Failed` in rose). Displays `+N more sources` when queue exceeds 2 files.
6. **Card Footer**: Formatted creation date and an interactive `"Open project →"` link with directional transition.

---

## 4. Desktop Resolution Grid Specifications

| Breakpoint | Column Count | Card Min Width | Spacing | Behavior |
|---|---|---|---|---|
| **1440 × 900** | 3 Columns | ~420px | 20px (`gap-5`) | Optimal reference management layout, 0 empty dead-space |
| **1366 × 768** | 3 Columns | ~390px | 16px (`gap-4`) | Compact desktop mode, zero horizontal overflow |
| **1024 × 768** | 2 Columns | ~460px | 16px (`gap-4`) | Tablet / small laptop format |
| **< 768px** | 1 Column | 100% | 16px (`gap-4`) | Responsive vertical stack |

