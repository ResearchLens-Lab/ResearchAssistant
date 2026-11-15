# Evidence Inspector Specification

## Presentation

- Header: **Evidence & sources**, with the count of cited passage references.
- Passages are grouped by document ID, then paper ID, filename, title, or source ID fallback, in that order. Group headings use the available paper title, title, or filename.
- Each source card presents the best available paper/document title, filename when distinct, author metadata and year only when supplied, and the actual page locator.
- Passage text uses the product sans-serif typography and a compact excerpt region.
- Internal `S1` identifiers are retained internally for source resolution but are not the primary displayed label or copied citation.
- Evidence language says “Retrieved passage”; the interface does not claim verification based only on retrieval.

## Interaction

- Evidence toolbar toggles the inspector.
- Inline citation selects the matching source and opens the same inspector.
- Selecting a passage highlights it in the inspector without unexpectedly opening the PDF.
- “Open PDF at page” calls the existing authenticated document viewer service.
- Copy actions use the available citation label, title, filename, and page; they do not expose internal chunk IDs as citation labels.
- Closing the desktop inspector does not clear source selection. Existing mobile drawer behavior remains.

## Limits

The citation schema includes page and author/title fields but does not guarantee every field. Missing metadata is omitted or falls back to filename/document wording. The UX does not invent page numbers, authors, or publication years. Citation count reflects the source references retained by the existing conversation source aggregation.
