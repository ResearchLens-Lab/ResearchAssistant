# ResearchLens Windows Desktop Product Vision

## Product promise

ResearchLens Desktop is a private, local-first academic research workspace. A researcher chooses a library location, imports or links documents, then researches them with deterministic retrieval and traceable citations. The core product works without a generative model, account with an external provider, or document upload to a cloud service. “Local-first” describes the target and must not be advertised as encrypted, fully offline, or isolated until the corresponding controls are implemented and verified.

## Product principles

1. **Evidence before prose.** Answers and comparisons show their source passage, document version, page/section locator, and review state. Missing support is visible.
2. **Local by default.** Parsing, indexing, querying, annotations, notes, graph and feedback are local. Optional network features are separately permissioned and disclose their exact metadata payload.
3. **Researcher control.** Documents can be copied into managed storage or linked in place. Memory, background work, OCR, external lookup, export and feedback are explicit controls.
4. **No hidden learning.** Feedback enters a review queue. Only approved, permitted examples may become immutable training dataset versions. Normal use never triggers automatic generative-model training.
5. **Recoverable work.** Backups include a manifest and integrity checks. Restore is testable and version-aware. Uninstall preserves the library unless a separate, explicit deletion action is chosen.
6. **Honest capability claims.** A citation resolving to a chunk is not by itself proof that every answer claim is entailed. Deterministic ranking and extraction limitations remain visible.

## Audience and core jobs

- Undergraduate and graduate researchers organizing papers by project.
- Researchers tracing a claim back to an exact passage and opening its page in the reader.
- Users comparing methods, findings, definitions, and evidence gaps across individually selected documents.
- Users maintaining a project notebook and a reviewed evidence ledger.

## Desktop scope

The first stable desktop release includes the project library, managed import and linked-file modes, document indexing, local deterministic Research Desk, citation-linked PDF reader, source-level comparison/reporting, notes/notebooks, evidence ledger, and encrypted backup only if encryption is implemented and reviewed. Knowledge maps, reviewed feedback, and memory are staged behind explicit review and opt-in gates. External bibliographic lookup is off until asked. There is no mandatory model download, remote inference, analytics, cloud sync, or background processing while closed.

## Product boundaries

The existing repository has local FTS5 retrieval and deterministic answer composition on its default path. It also contains optional legacy embedding/provider routes, standalone document-intelligence artifacts, graph and memory subsystems, and public-metadata lookup code. The desktop product must make those boundaries explicit and must not infer that a feature is integrated merely because code or a report exists. Current implementation is not yet the complete desktop product described here.

## Success measures

- A clean Windows user profile can install, start, import a representative PDF, ask a question, inspect a cited passage, close, restart, and retain the project without network access.
- Every displayed source pointer resolves to the same document version and passage after restart and backup/restore.
- A second Windows account cannot read the first account’s database, key material, documents, feedback, or backups through default ACLs.
- Permission settings correspond to observable network and filesystem behavior.
- Cancellation, crash recovery, upgrade, rollback, and uninstall-preservation scenarios pass release gates.

## Non-goals

This is not a website-in-a-window wrapper, cloud collaboration service, general-purpose chatbot, automatic paper downloader, or automatic model trainer. A future server edition may exist, but it has separate deployment, tenancy, security and data policies.
