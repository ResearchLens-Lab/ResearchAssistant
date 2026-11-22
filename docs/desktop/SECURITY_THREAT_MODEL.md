# Windows Desktop Security Threat Model

## Assets and trust boundaries

Assets: originals, linked document paths, extracted text, citations, notes, graph/memory, credentials, DB, FTS/vector indexes, feedback/training data, encryption keys, backups and update signing keys. Boundaries: Windows user account; installer/admin boundary; Electron main process; sandboxed renderer; Next server; FastAPI sidecar; library root; local SQLite; optional external metadata endpoint; update channel.

## Threat analysis

| Threat | Main risk | Required control and verification |
|---|---|---|
| Two Windows users | Shared install mistaken for shared trust/data | User-profile-specific paths/ACLs and keys; test access from a second standard account. |
| Malicious PDF/document | Parser exploit, decompression bomb, crafted links or resource exhaustion | Pinned patched parsers, size/page/object limits, subprocess isolation where practical, no automatic external links, cancellation and corpus fuzzing. |
| Path traversal / symlink / reparse point | Read/write outside chosen library | Opaque IDs, canonical path resolution, no client path concatenation, reparse-point policy, open-handle identity checks, backend enforcement. |
| Local API port exposure | Other local process or website calls private API | Ephemeral loopback bind, per-launch high-entropy secret, strict Origin/Host, CSRF protections, no wildcard CORS; test DNS rebinding and cross-origin requests. |
| Renderer/IPC abuse | Web content obtains file or process authority | Context isolation, sandbox, no Node integration, narrow typed IPC, navigation allowlist, CSP, schema validation, dependency audit. |
| Database theft | Extracted text and notes disclosed | Default user-only ACLs; optional authenticated encryption design; distinguish ACL protection from encryption. Verify locked-at-rest behavior and key lifecycle before claiming encryption. |
| Backup theft | Full library disclosure | User-selected recovery credential or key escrow model, authenticated encryption, integrity manifest, no silent DPAPI-only portability claim, restore test. |
| CSRF / CORS / DNS rebinding | Malicious page triggers local service | Random per-launch token, Origin and Host validation, request method/content-type restrictions, no browser ambient credential, hostile-origin test suite. |
| Untrusted external URLs | Phishing or local scheme abuse | Allow https only for external opening, show destination, no embedded remote page, block file/javascript/custom schemes. |
| Update compromise | Signed malicious installer or downgrade | Code signing, signed update metadata, pinned trust, rollback controls, SBOM, release provenance, staged update/recovery. |
| Dependency supply chain | Vulnerable or compromised native packages | Pin/lock, SBOM, vulnerability review, reproducible artifacts, signed release and parser update policy. |
| Permission escalation | Installer/service runs elevated unnecessarily | Standard-user runtime; elevation only for all-users install, no persistent privileged service, least-privilege ACLs. |
| Local feedback leakage | Private passages included in training data/export | Owner-scoped consent, review queue, provenance, exclude by default, inspectable dataset export and deletion cascade. |

## Encryption design questions

Windows DPAPI can protect a random data-encryption key bound to the current Windows user. It does not encrypt a SQLite database, PDF, WAL, cache or backup by itself. Proposed design: encrypt per-library data keys with DPAPI for same-user convenience; encrypt database/files/backups with vetted authenticated encryption; support a recovery key or passphrase for migration to another Windows profile/device; separate key rotation from data conversion; never store plaintext keys in config/logs. Evaluate SQLite encryption library licensing, native packaging, FTS compatibility, WAL behavior and backup integration before selection. Until implemented and penetration-reviewed, state only “Windows user ACL protected,” not “encrypted at rest.”

## Acceptance tests

Security review must include second-user access, direct endpoint probing from LAN and hostile browser origin, port scanning, invalid bootstrap secret, symlink/path traversal, malicious PDF, renderer navigation/IPC fuzzing, token/log inspection, DB/backup theft scenario, restore after key recovery, update tamper/downgrade, and least-privilege install. Record evidence, remediation owner and residual risk for every failed control.
