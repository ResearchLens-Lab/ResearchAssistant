# Desktop Release Acceptance Plan

Each gate requires an evidence bundle tied to a build hash, test environment and reviewer. A failed privacy/security/recovery criterion blocks promotion; a green UI smoke test does not substitute for data-integrity verification.

## Technical prototype

- Packaged UI, FastAPI and local SQLite/FTS5 start on a clean Windows profile without installed Node/Python or network.
- Dynamic chat/project/PDF routes work through direct cold-start navigation.
- Sidecars bind only to loopback, use random per-launch authentication and terminate with the application.
- Renderer cannot read arbitrary files or execute shell/process commands.
- Spike report compares Electron with Tauri on actual package, memory, startup and route compatibility.

## Desktop alpha

- Copy/link imports work with permission and path/reparse checks; document ownership, version and fingerprint persist.
- Deterministic question, citation, PDF open, highlight/fallback and cross-project comparison are traceable to exact document versions.
- Local-only network audit confirms no document upload, external AI, analytics, cloud sync or crash upload.
- User can cancel import, close during work, restart after crash, and retain a consistent previous index.
- Local backup restores into a separate folder with validated manifest; uninstall preserves all data.

## Desktop beta

- Representative user-authorized corpus, synthetic hostile corpus, large documents and duplicates pass parser/index limits.
- Retrieval, answer support, citation fidelity, comparison coverage, latency and resource baselines are reviewed and reproducible.
- Second Windows account isolation, API-origin protections, path traversal, malicious document, key recovery and signed update tests pass.
- Onboarding and all permission-centre switches correspond to observed behavior; external lookup discloses exact metadata.
- Feedback is opt-in and review-gated; no normal interaction trains a model.

## Release candidate

- Signed installer/update and offline install tested on clean supported Windows versions; WebView2/Chromium dependencies verified.
- Upgrade from each supported schema version creates and validates backup; forced interruption and restore tested.
- Uninstall, repair and per-user/all-users install never delete or share another user’s library.
- Security review closes critical/high issues or documents formally accepted residual risk; SBOM and provenance shipped.
- Accessibility, keyboard navigation, screen reader, DPI/scaling, laptop window sizes and reduced motion pass.

## Stable release

- Zero open critical/high security or data-loss defects; all P0/P1 acceptance items signed off by product, desktop, security and data owners.
- Recovery drill succeeds from encrypted backup using recovery credential on a separate Windows profile/device.
- Upgrade, rollback, export, delete-library and uninstall instructions are published and match tested behavior.
- Offline core workflow remains functional after clean install; optional features remain off until individually authorized.
- Support diagnostics redact query/document contents by default and can be previewed before user export.

## Required reporting

For every gate retain test cases/results, Windows build, CPU/RAM/disk profile, installer hash, DB schema and parser/index versions, packet capture or equivalent egress evidence, recovery checksums and known limitations. Do not claim pass where a path was only statically inspected.
