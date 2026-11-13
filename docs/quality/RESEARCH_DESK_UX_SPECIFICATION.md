# ResearchLens: Research Desk UX Specification
**Document Reference:** `RL-SPEC-UX-004`  
**Status:** Approved & Enforced  
**Classification:** Frontend Interface & Information Architecture  

---

## 1. Overview & Inspiration

The Research Desk is engineered as an academic research workspace inspired by professional desktop reference managers (Mendeley, Zotero) and reading environments (Readwise, Notion). Unlike conversational consumer chatbots that prioritize chat bubbles, ResearchLens prioritizes **reading legibility, evidence traceability, and deep document context**.

```
+─────────────────+───────────────────────────────────────────────+─────────────────+
| Pane 1: Sidebar | Pane 2: Central Research Canvas               | Pane 3: Rail    |
| (240px, w-60)   | (Maximized width, responsive reading layout)   | (320px, w-80)   |
|                 |                                               |                 |
| [Sessions][Srcs]| Header: Document Scope | Active Evidence      | Verified Excerpt|
|                 | ───────────────────────────────────────────── |                 |
| Session 1       | Grounded Research Answers                     | Passage Text    |
| Session 2       | - Clear typography (14px serif/sans)          | Exact Page No.  |
| Session 3       | - Citation Badges [Author et al., Year, p. X] | Section Header  |
|                 | - Thematic Markdown Tables                    | [Open in PDF]   |
|                 |                                               |                 |
| [Collapse <]    | Persistent Input Bar (Evidence-First Default) | [Close Rail >]  |
+─────────────────+───────────────────────────────────────────────+─────────────────+
```

---

## 2. Layout Structure & Dimensions

### 2.1 Pane 1: Left Compact Navigation Sidebar
- **Width:** Exactly 240px (`w-60`), reducing horizontal space consumption by 32% compared to legacy 352px layouts.
- **Top Tab Switcher:**
  - `Sessions`: Lists chronologically grouped research inquiries (Today, Yesterday, Older) with quick rename and delete.
  - `Sources`: Allows multi-select checkboxes across all indexed library documents to set the active inquiry scope.
- **Collapsible Toggle:** Accessible via top header button (`<PanelLeft />`) with smooth CSS transition.

### 2.2 Pane 2: Central Research Thread Canvas
- **Dominant Workspace:** Automatically claims all available screen real estate (typically 800px–1200px on modern laptops/monitors).
- **Header Ribbon:**
  - Current session title with inline rename modal.
  - Active document scope badge with chunk count.
  - Evidence Inspector toggle showing live cited passage count: `Evidence (N)`.
  - `+ New Research` primary action button.
- **Message Rendering:**
  - `GroundedAnswer`: Clean academic typography with LaTeX KaTeX support and remark GFM tables.
  - `CitationBadge`: Interactive blue badge `[Author et al., 2025, p. 2]` with hover card and one-click PDF jumping.
  - Contextual follow-up suggestions rendered as sleek pills (`"Present findings in a concise table"`, `"Explain in more depth"`).
- **Persistent Input Composer:**
  - Fixed at canvas bottom.
  - Answer mode defaults to `Evidence-First · Deterministic`.
  - Placeholder dynamically indicates scope: *"Ask an evidence-backed inquiry across N selected documents…"*.

### 2.3 Pane 3: Right Evidence Inspector Rail
- **Width:** 320px (`w-80`) desktop rail or slide-over drawer on smaller screens.
- **Content:**
  - Source chunk card displaying paper title, authors, publication year, physical page range, and section name.
  - Direct passage excerpt highlighted in italic quote.
  - One-click button: `Open PDF Page X` launching the authenticated PDF viewer.

---

## 3. Responsive Breakpoints
- **Desktop ($\ge 1024$px):** 3-pane workbench with independent scrolling for canvas and side rails.
- **Tablet / Mobile ($< 1024$px):** Center canvas displays full-width; left sidebar and right evidence rail toggle into smooth overlay drawers with backdrop dismissal.

