# Security Policy

## Reporting Vulnerabilities

If you discover a security issue or vulnerability in ResearchLens, do not open a public issue. Report it directly to the maintainers:

- Contact: `goravgumber@gmail.com`
- Target Response Window: Within 48 hours.

---

## Security Model and Multi-User Isolation

ResearchLens implements tenant isolation across local user accounts and project boundaries:

1. **Mandatory Owner Scoping**: All query pipeline calls, full-text searches, and vector store operations require an authenticated `owner_id`. Calls without an owner ID raise an error.
2. **Database Scoping**: The SQLite FTS5 table `lexical_chunks` includes an `owner_id` column. Queries enforce `WHERE owner_id = :user_id`.
3. **Session Credential Encryption**: The desktop application uses Windows DPAPI (`safeStorage` via Electron) to encrypt stored tokens on disk.
4. **Offline Boundary**: In desktop runtime mode, outbound network connections are blocked. The local application communicates exclusively over the loopback interface (`127.0.0.1`).
