# Database Portability and Migration Plan

## Decision

SQLite + FTS5 is the preferred single-user desktop relational store, but adoption is **conditional on an isolated migration rehearsal and full service-level verification**. Existing tests create SQLAlchemy metadata using `sqlite+aiosqlite`, which is useful evidence that models can run on SQLite. It does not prove that all Alembic revisions, concurrency assumptions, JSON queries, foreign-key semantics, or current PostgreSQL user data are portable.

Keep the future server edition separate: PostgreSQL remains the appropriate multi-user/server option, with a shared service boundary and its own operational/security profile. Do not make the desktop and server silently share a database file.

## Observed model/migration features

- IDs are generally `String(36)` UUID values generated in Python; this avoids native UUID-column dependence.
- Models use SQLAlchemy generic JSON with a PostgreSQL JSONB variant (`backend/app/database/base.py` and migration revisions). JSON storage is broadly portable, but JSON operators/indexing and query semantics must be audited.
- Common columns include strings, text, integer, boolean, floating point, naive UTC datetimes, foreign keys, unique constraints and ordinary indexes.
- Migrations include initial schema, usernames, document progress fields, graph, research intelligence, memory, and paper descriptions. Some revisions import PostgreSQL dialect types explicitly for JSONB variants.
- RAG independent retrieval already writes SQLite FTS5 to a separate lexical index file. Legacy vector mode uses ChromaDB and an additional lexical database. These are separate stores today, not one transaction with the relational database.
- Backend test fixtures create all current ORM tables in SQLite, but do not establish that the historical Alembic chain upgrades a blank SQLite database or converts a populated PostgreSQL instance losslessly.

## Portability matrix

| Feature | SQLite assessment | Required proof/change |
|---|---|---|
| String UUID primary/foreign keys | Compatible | Validate lengths, collation and all cascades. |
| Generic JSON / JSONB variant | Basic JSON likely portable | Replace/avoid PostgreSQL-only JSONB operators; test null, arrays, containment, serialization and indexes. |
| Foreign keys / cascade | Supported but connection-dependent | Enable `PRAGMA foreign_keys=ON` for every connection and test deletion graph. |
| Boolean, text, integer, float, date-time | Compatible with affinity differences | Add range/normalization checks where correctness depends on exact type. |
| Alembic `server_default` strings/booleans | Usually portable | Exercise every upgrade and downgrade on target SQLite versions; inspect batch table rebuilds. |
| Indexes and uniqueness | Supported | Check duplicate legacy rows before adding constraints; test case sensitivity/collation. |
| FTS5 | Available only if SQLite build includes FTS5 | Verify the bundled Python SQLite build at startup; fail clearly rather than silently switching search behavior. |
| Async SQLAlchemy / SQLite | Supported through aiosqlite | Measure serialized writes, lock handling, WAL/checkpoint behavior and cancellation. |
| PostgreSQL JSONB variant imports | Dialect-aware type declarations | Verify SQLite compilation for every Alembic revision in a clean throwaway database. |
| Chroma and lexical RAG artifacts | Not part of relational DB | Version separately; preserve, back up, validate and restore them independently. |

Static inspection found no `ARRAY`, native `UUID`, `ENUM`, `TSVECTOR`, raw `ON CONFLICT`, or PostgreSQL-only full-text SQL in the main backend model/service source searched. That is a scoped search, not proof there are no dialect-specific runtime dependencies elsewhere.

## Migration rehearsal (never against developer data)

1. Provision disposable copies/synthetic fixtures under a temporary directory, outside `.chroma`, existing SQLite files, and user library.
2. For blank database portability, run every Alembic revision from base to head against the exact bundled SQLite runtime; compare resulting schema to ORM metadata and run backend suites against that isolated DB.
3. For PostgreSQL conversion, export a sanitized synthetic PostgreSQL dataset covering every table, null/JSON shape, cascade, unique edge, timestamp, large text and migration revision. Import through an explicit versioned converter; compare row counts and canonical hashes. Do not infer PostgreSQL conversion from changing `DATABASE_URL`.
4. Exercise interrupted migration at each transaction/rebuild boundary, disk-full, locked DB, process kill and restart. Keep originals immutable.
5. Restore the preflight backup to a separate location and run read-only integrity checks, FK checks, FTS5 checks and citation identity checks.
6. Only after evidence is reviewed, implement a migration with dry-run summary, explicit confirmation, durable backup, journal, resumable steps, idempotency and rollback by restoring backup (not assumed reverse SQL).

## Desktop data model and write policy

One SQLite relational database per Windows user/library; no shared multi-user writable DB. Enable foreign keys, WAL, a bounded busy timeout and a single bounded writer queue. Readers use short-lived transactions. Do not place the live DB on unsupported network/removable/synchronized locations; offer a documented warning or require copying into a supported local folder. FTS5 is derived and rebuildable from canonical document/page/block records.

## Rollback and server edition

Before each versioned schema update, create and verify a closed/consistent backup manifest. If migration fails, preserve the failed copy for diagnostics and restore the untouched prior backup into the active location only through an explicit recovery flow. Server edition continues on PostgreSQL behind the same repository/service contract, with separate migrations and deployment. Cross-edition export/import is a versioned interchange format, not shared live DB files.
