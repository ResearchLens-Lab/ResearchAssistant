# Windows Installer, Updates and Uninstall

## Packaging recommendation

Use Electron with a signed Windows installer, evaluating NSIS first for per-user installation and a separate elevated “all users” option. WiX/MSI can be evaluated for managed IT deployment if repair/uninstall policy demands it. Build both installation scopes only after confirming Electron packaging tools support the process model, sidecar permissions, WebView/Chromium runtime and signed binaries. The all-users option installs binaries system-wide but never writes research data to a shared ProgramData location.

## Paths and scope

- Per-user binaries: `%LOCALAPPDATA%\Programs\ResearchLens` (installer-specific; confirm actual selected tooling).
- All-user binaries: `%ProgramFiles%\ResearchLens`.
- Per-user settings, local DB/runtime and keys: `%LOCALAPPDATA%\ResearchLens` with user-only ACLs.
- Default visible library suggestion: `%USERPROFILE%\Documents\ResearchLens Library`.
- User-selected backup destination remains independent.

Each Windows account gets independent database, library, documents, key wrapping, settings, feedback, datasets and backups. Do not place private runtime data in a shared install directory. Provide an explicit choice to open another library only under the current account’s permissions.

## WebView2 and offline installation

Electron packages Chromium, avoiding a separate WebView2 prerequisite at the cost of larger install size. Confirm the chosen distribution actually includes its runtime and native dependencies in offline installation. The installer must not download Python packages, models, OCR language packs or papers. Any optional OCR/model package is a separately described, user-initiated, checksummed installer with disk/resource estimate.

## Upgrade lifecycle

1. Verify installer signature and publisher; reject downgrade/unsigned updates unless an administrator-managed recovery path explicitly allows it.
2. Stop the app cleanly or ask the user to close it; snapshot and verify the user library before schema changes.
3. Install versioned binaries atomically; keep prior binaries available until health checks pass.
4. Run reviewed, versioned database migration with a journal. Never delete originals or rebuild indexes silently.
5. Validate API readiness, DB integrity, document manifest, FTS availability, and a read-only citation lookup.
6. On failure, restore prior binaries and the pre-migration DB snapshot. Do not attempt unsafe reverse migration automatically.
7. Keep app data after uninstall by default; upgrades and repair must preserve it.

## Signing and supply chain

Sign the installer and all executable components with a production code-signing certificate. Timestamp signatures. Publish hashes, release notes, SBOM and provenance. Pin dependencies, scan and review updates, generate reproducible build records, and test update integrity. Avoid auto-update on first release until signed update metadata, rollback protection, staged rollout and recovery are verified.

## Uninstall behavior

Uninstaller removes application binaries and registered shortcuts only. It does not delete library, backup, logs, settings, or key envelopes silently. Offer a separate opt-in cleanup screen that enumerates exact per-user app-data paths and explains that deleted keys may make encrypted data unrecoverable. If the app is installed for all users, uninstall must not touch another Windows account’s library.
