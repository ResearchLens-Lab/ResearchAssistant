# Research Desk Layout Audit

## Existing structure

The Research Desk used a fixed top navigation, a desktop sidebar with a New Research action, Sessions/Sources tabs, a large active-scope card, a central message stream and composer, plus an optional evidence rail. The source tab and project scope duplicated navigation information. The chat composer showed five permanent slash-command chips. The answer header exposed implementation details such as “Local RAG · No LLM,” and the citation rail described retrieved passages as verified.

## UX defects addressed

- Sidebar consumed 300px by default and disappeared entirely when collapsed.
- Projects were hidden behind the Sources tab, and source filenames competed with session history.
- Active scope was represented by an oversized card.
- Citation state opened a drawer independently of the desktop evidence rail.
- Evidence cards used a serif face, prominent internal IDs, and unsupported verification language.
- The composer made optional presentation modes visually dominant.
- At medium desktop widths, two side panes could leave too little room for reading.

## Updated layout behavior

- Expanded navigation defaults to 268px, persists user resizing, and can be adjusted from 250–320px. Collapsed state becomes a 64px icon rail.
- Projects are a compact list above the separate recent-session list. Source management remains available through the scope tab and each project menu.
- Evidence uses a 320–368px desktop rail at wide sizes and an overlay at medium widths. At mobile widths it uses the existing drawer.
- The center conversation and composer scroll/size independently; answer content is kept in a readable max-width column.
- Existing top-level Library, Research Desk, and Compare & Reports routes are untouched.

## Data and behavior boundaries

The research answer and retrieval data were not modified. The UI still renders the exact stored answer and source references. The unrelated “Linear Algebra” evidence visible in the supplied screenshot is a retrieval/answer quality issue; this UX-only change does not rewrite or conceal the evidence. Time formatting continues to use the existing Asia/Kolkata utility.
