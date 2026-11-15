# First-Run Onboarding and Privacy & Permissions Centre

## First run

1. **Welcome and local-processing explanation.** Core answers use local documents and deterministic processing; explain that parsing/indexing consumes CPU, memory and disk.
2. **Library location.** Suggest `%USERPROFILE%\Documents\ResearchLens Library`; show free space, local/network/sync detection, ACL caveat and “choose another folder.” Create only after confirmation.
3. **Document handling.** Default to copy into managed storage; explain linked files’ move/backup risks and require an explicit selection for linking.
4. **Resource profile.** Offer Low-resource (single indexing job, restrained retrieval) and Standard (bounded concurrency) modes. Do not promise supported minimum specs until measurements exist.
5. **Backup.** Offer a reminder/setup flow for another local destination, frequency and retention; no backup starts until destination, encryption mode and schedule are explained.
6. **Privacy defaults.** External AI absent; cloud sync, analytics, crash upload, closed-app background processing off; external bibliographic lookup asks each time.
7. **Readiness.** Verify writable library, SQLite/FTS5 runtime, key protection, backup state, and sidecar/API readiness. Show actionable errors without resetting existing data.

Onboarding can be skipped and revisited. No document content is sent during onboarding.

## Permission Centre controls

| Permission | Safe default | Disclosure/behavior |
|---|---|---|
| Local document access | Only selected files/folders | Show active paths and copy/link status; revoke link or remove managed copy through a clear workflow. |
| Folder access | Per action / native picker | Explain whether access is one-time or retained; enforce allowlisted roots server-side. |
| External DOI/title lookup | Ask every time | Before request show exact DOI/title/author/year fields and destination; never send passage text or full PDF. |
| External AI | Absent / disabled | No provider integration by default. If ever added, separate opt-in with a per-query disclosure and policy review. |
| Cloud sync | Off | No background transfer; future provider permissions and conflict rules separately specified. |
| Analytics | Off | No product usage events leave device. |
| Crash reporting | Off | Local rotating logs only; user previews and explicitly sends a redacted bundle. |
| Background processing | While app open only | Closed-app work requires a clear toggle, Windows startup/background indication, resource cap and stop control. |
| Backup/export | User-selected destination | Show included records/documents and whether output is encrypted. |
| Local reviewed learning | Explicit review/approval | Show examples, provenance, privacy scope and dataset version before export/training. |

Settings must reflect effective behavior, not merely a stored toggle. Permission revocation stops future access; document and index cleanup is separately described and confirmed. Keep an auditable local history of permission changes without recording file contents.

## External metadata disclosure

When a user authorizes a scholarly lookup, show provider name and exact fields sent (for example DOI, title, author names, publication year), state that document text/PDF is not sent, and give a one-time or future-use choice. The existing source includes Crossref/OpenAlex lookup code, so the desktop build must either gate that path or disable it until the consent UX is implemented.
