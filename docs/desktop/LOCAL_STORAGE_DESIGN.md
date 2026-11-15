# Local Library and Storage Design

## Directory layout

Suggested default user-selected library: `%USERPROFILE%\Documents\ResearchLens Library`. It is a suggestion, not a hard-coded path. App state and ephemeral files belong under `%LOCALAPPDATA%\ResearchLens`; backups are separate and user-selected.

```text
<LibraryRoot>/
  library.sqlite3
  documents/<document-id>/<version-id>/original.pdf
  attachments/<attachment-id>/...
  exports/                 # optional, user-visible output only
  backups/                 # only when user selects library as destination
  manifest.json            # format/version/IDs, no secrets
%LOCALAPPDATA%/ResearchLens/
  runtime/                 # ephemeral ports, readiness, locks; restrictive ACL
  cache/                    # disposable extraction/index caches
  logs/                     # rotating, content-redacted diagnostics
  keys/                     # protected key envelope only, DPAPI/user-bound
```

Do not keep the only copy of backups in the same failure domain as the live library. The user can choose a different local drive/location. A future remote backup target is a separate feature and permission.

## Core entities

Relational records include projects, documents, immutable document versions, extracted pages/blocks/sections, annotations, bookmarks, conversations/messages, evidence links, notes/notebooks, graph assertions/reviews, feedback approvals, dataset manifests and job state. Each derived record references a stable document ID and version ID, plus extraction/indexer version and a content fingerprint. Passage citations point to immutable block IDs and offsets/page locators; no citation should silently drift after document replacement.

Original files are immutable versions. Replacing a document creates a new version and preserves previous cited versions until the user explicitly removes them. Managed attachments include provenance and checksums. FTS5 and caches are derived artifacts; Chroma is optional and not required for deterministic desktop mode.

## Import modes

### Copy into managed storage (recommended default)

The app copies bytes into a generated, opaque path after user selection and validation, records SHA-256, size, source filename and import time, then indexes the managed copy. The original source path is not needed after import. This improves resilience when the original file moves, but consumes additional disk and means users must include the library in backups.

### Link to existing file

The app stores a canonical path plus file identity/fingerprint and reads it when indexing or opening. This saves space and preserves the user’s existing organization, but move/rename/delete breaks availability and backup completeness is not guaranteed. Show a broken-link state and never follow a replaced file silently; compare file identity/fingerprint and offer re-index/version creation. Windows reparse points/symlinks require canonicalization and target validation.

## Supported locations

Initially support local NTFS/ReFS volumes with normal per-user ACLs. Detect UNC/network paths, mapped drives, removable media, OneDrive/Dropbox/synchronized roots, FAT/exFAT and paths with reparse points; explain unsupported concurrent-write/locking or backup risks. Do not categorically prohibit a location without a documented probe; use local copy as safe alternative. Store the active SQLite database and WAL together on supported local storage.

## Backup, restore and export

- Use SQLite online backup/checkpoint APIs or a cleanly closed, consistency-checked snapshot; never copy only the main DB while WAL is live.
- Backup manifest includes schema version, app version, document/version IDs, filenames, file sizes, checksums, linked-file status, included derived data, and encryption envelope metadata—never authentication tokens or raw keys.
- Verify each archive entry path against traversal, size/count limits and checksum before restore. Restore into a new directory first; run DB integrity/FK checks and reconcile document files, FTS index and citations before offering activation.
- Encrypt backups with a user-controlled recovery credential if supported; DPAPI-only protection cannot restore on another Windows profile/device.
- Export plain user-requested records/documents through an explicit destination and preview; explain that export creates unprotected copies unless the user selects an encrypted archive.
- Uninstall preserves the library and backups. In-app delete-library is separate, explicit, irreversible, and includes a confirmation summary.
