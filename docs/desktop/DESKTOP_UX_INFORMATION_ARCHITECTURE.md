# Desktop UX Information Architecture

## Primary navigation

1. **Library** — projects, collections, tags, documents, import status, duplicate review and search.
2. **Research Desk** — scope picker, current conversation, evidence-grounded answer, citations and follow-up questions.
3. **Compare & Reports** — select individual indexed documents; choose comparison focus and format; review gaps and cited findings.
4. **Research Map** — expandable conversation or project map; nodes link to claims and passages, with source/version identity.
5. **Notebook** — project journal, notes, saved findings and source-passage backlinks.
6. **Evidence Ledger** — claim, passage, citation, review status, researcher note and export history.
7. **Settings / Privacy Centre** — location, permissions, resource profile, backup, recovery, import defaults and diagnostics.

Keep document reading as a full workspace view with a source rail and an annotation panel, not an unrelated browser window. Global navigation remains fixed and responsive. Project/source labels stay visible as compact context; avoid oversized blank states, clipped file cards, redundant buttons and persistent panels that obscure the question or answer.

## Main desktop shell

- Left navigation rail is resizable/collapsible and remembers width per window.
- Main pane owns the current task; panels are dockable or collapsible with keyboard-accessible handles.
- Evidence inspector is a right dock, not a modal that covers the question; selecting a citation opens the exact document version and passage.
- Composer stays compact, grows to a bounded height, supports visible research tools and scope chips, and never hides the answer tail.
- Preserve scroll position per conversation; new research always creates an explicit blank session, not an implicit restore of yesterday’s chat.

## Core flows

### Import

Add sources → choose/create project → choose copy or link → review selected file names and destination → start local parse/index → show per-document progress and cancel → report ready/partial/error with recover action.

### Ask and verify

Choose project/document scope → ask question → show deterministic answer with support state → every citation links to a stable passage → inspect evidence → open reader at page and highlight exact span when offsets are available; otherwise show page-level locator with an honest “text highlight unavailable” state.

### Compare and report

Select two or more distinct ready documents, even from one project → choose a shared focus → select table, side-by-side or detailed report → generate from retrieved evidence → mark missing dimensions → inspect each cell’s citations and export with provenance.

### Backup and recovery

Show last verified backup/time/destination → run backup with progress/cancel → validate manifest → restore into a new location → inspect proposed library identity and missing linked files → activate only after integrity checks.

## Accessibility and convenience

Keyboard-first navigation, visible focus, high-contrast citation state, resizable text, semantic headings, screen-reader descriptions for charts/maps, reduced-motion preference, accessible drag alternatives and confirmation for destructive actions. Responsive layouts support laptop windows; essential actions must not depend on hover.
