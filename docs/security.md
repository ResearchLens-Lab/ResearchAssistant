# Security Policy & SEC-001 Isolation Architecture

## Reporting Security Vulnerabilities

We take security seriously. If you discover a vulnerability or potential security risk in ResearchLens, please **do not open a public issue**. Instead, report it directly to the maintainers:

- **Email**: `goravgumber@gmail.com`
- **Response Target**: Within 48 business hours.

---

## SEC-001: Multi-User Security & Tenant Isolation

ResearchLens implements **SEC-001**, a comprehensive multi-user isolation architecture designed to ensure zero data leakage across local user accounts and project boundaries.

### Key Security Invariants

1. **Owner ID Mandatory on Retrieval & Ingestion**
   Every query pipeline call, lexical search, and vector operation requires an authenticated `user_id` / `owner_id`. Any attempt to query without an owner ID raises a strict `ValueError`.

2. **Database Scoping**
   - **Lexical Index (`researchlens_lexical.sqlite3`)**: The `lexical_chunks` FTS5 table stores an explicit `owner_id` column. Searches execute with an enforced `WHERE owner_id = :user_id` constraint.
   - **Relational Tables**: All project, document, paper, and session tables in SQLite/PostgreSQL are keyed by owner foreign keys.

3. **Desktop Session Encryption**
   The desktop application uses Windows DPAPI (`safeStorage` via Electron) to encrypt access tokens and user credentials stored on disk. Plaintext authentication tokens are never written to application logs or stored unencrypted in local files.

4. **100% Strict Offline Operation**
   When running in desktop/independent mode, ResearchLens blocks external outbound network requests. Verified by automated testing (`test_offline_strict.py`), zero network requests leave the local loopback interface.
