# Source verification design and implementation

**Status:** DOI verification is implemented as an explicit, per-paper action. Reference-list extraction, duplicate detection, URL/domain checks and bibliography exports remain partial or planned.

## What is implemented

From a paper detail page, an authenticated user can choose **Verify DOI**. The backend checks ownership of the paper, normalizes the stored DOI, and makes one lookup each against Crossref and OpenAlex. Requests contain the DOI only; private abstracts, uploaded files and passages are not transmitted. Results are not written to the database, so existing paper records remain unchanged.

The response includes the registry title, authors, venue, year, publisher, ISSN/ORCID fields when available, OpenAlex open-access metadata, registry links, and comparisons against the stored title/authors/year/venue. It exposes missing metadata as missing; it does not invent values. Author matching compares normalized family names as a clearly heuristic rule. A mismatch is a reason to review, not a verdict of fraud.

Statuses include `VERIFIED METADATA`, `PARTIALLY VERIFIED`, `UNVERIFIED`, `METADATA MISMATCH`, `RETRACTION/CORRECTION FLAG`, and `EXTERNAL VERIFICATION UNAVAILABLE`. A missing result is explicitly not described as proof that a work is fake. Registry agreement is not a measure of scientific validity. Retraction and correction checks are best-effort signals from currently returned registry metadata; absence of a flag is not proof that no notice exists.

## External services and privacy

- Crossref's public REST API supports DOI work lookup without an API key. Crossref says deposited metadata can include licenses, post-publication updates and identifiers, while coverage depends on deposited records. [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api), [API access and limits](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication).
- OpenAlex provides a public Works endpoint and currently documents keyless basic API use. The implementation sends no API key and makes only an exact DOI work lookup; rate and access policies can change. [OpenAlex Works](https://help.openalex.org/data/works/), [OpenAlex API access](https://help.openalex.org/api/authentication/).
- Both checks require the user's explicit click. Offline users can continue using local RAG; the UI reports registry unavailability rather than blocking local research.

## Confidence must stay separated

This feature does not currently calculate a numeric source confidence score. The registry state and listed mismatches are observable metadata checks; they are not statistically calibrated probabilities. Future confidence presentation should keep separate: bibliographic match, answer evidence support, relevance and source provenance. Any score needs visible inputs and rules, plus manually reviewed evaluation before it is labelled calibrated.

## Remaining work

1. Extract references from imported PDFs and structured formats with exact page/section provenance; do not treat every reference-looking line as a verified work.
2. Add DOI resolution and candidate matching for references without DOI, with title/author/year confirmation.
3. Add duplicate detection and editable, provenance-preserving metadata reconciliation.
4. Expand Crossref update/retraction relation handling and OpenAlex retraction checks against official current schemas; present “no record” separately from “checked and clear.”
5. Add explicit citation exports (APA 7, IEEE, BibTeX), mark missing fields and avoid fabrication.
6. Add throttling, request-result cache with expiry, retry-after handling and user controls before using this across large libraries.
7. Add user-selected OpenAlex key support only if needed; no paid or keyed service is currently used.

## Verification tests

Tests cover matching metadata, mismatches, a retraction signal, DOI normalization, and confirmation that private abstract text is not sent. They use mocked HTTP responses and do not depend on live external services.
