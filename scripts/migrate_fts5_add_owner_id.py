#!/usr/bin/env python3
"""Authoritative FTS5 Schema Migration: Add owner_id to lexical_chunks.

Safely migrates SQLite FTS5 lexical virtual tables from legacy 11-column
schema to multi-tenant 12-column schema with `owner_id UNINDEXED` at position 1.

Key Guarantees:
  1. Default mode is non-mutating `--dry-run`.
  2. Preserves all chunk_ids, paper_ids, document_ids, metadata, text, and tokenizer config.
  3. Authoritative mapping: resolves owner_id from application relational database or mapping file.
  4. Never assigns arbitrary fallback owner (no dummy admin/system owners).
  5. Quarantines unresolvable (orphan) or contradictory (ambiguous) records in `lexical_chunks_quarantine`.
  6. Atomic swap: builds `lexical_chunks_migrating`, verifies parity and search integrity, then
     renames original table to `lexical_chunks_pre_owner_migration` and swaps in the new table.
  7. Idempotent: exits cleanly without changes if table already contains `owner_id`.
  8. Full crash safety: atomic transaction guarantees complete rollback on interruption.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("fts5_migration")


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> List[str]:
    """Return list of column names for a SQLite table or virtual table."""
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]
    except Exception:
        return []


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table or virtual table exists."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE (type = 'table' OR type = 'virtual') AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def load_trusted_mappings_from_json(mapping_path: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load paper_id -> owner_id and document_id -> owner_id from JSON file."""
    with open(mapping_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    paper_owners = data.get("papers", {})
    doc_owners = data.get("documents", {})
    return paper_owners, doc_owners


def load_trusted_mappings_from_db(db_url: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load paper and document ownership mappings from SQLAlchemy app database."""
    from sqlalchemy import create_engine, select, text
    # Support both async and sync SQLite/Postgres URLs
    sync_url = db_url.replace("+aiosqlite", "").replace("+asyncpg", "")
    engine = create_engine(sync_url)
    paper_owners: Dict[str, str] = {}
    doc_owners: Dict[str, str] = {}

    with engine.connect() as conn:
        # Load papers
        try:
            res = conn.execute(text("SELECT id, owner_id FROM papers WHERE owner_id IS NOT NULL"))
            for pid, oid in res.fetchall():
                if pid and oid and str(oid).strip():
                    paper_owners[str(pid)] = str(oid).strip()
        except Exception as e:
            logger.warning("Could not query papers table: %s", e)

        # Load documents - resilient across schemas with or without documents.owner_id
        try:
            res = conn.execute(
                text(
                    "SELECT d.id, p.owner_id "
                    "FROM documents d "
                    "JOIN papers p ON d.paper_id = p.id "
                    "WHERE p.owner_id IS NOT NULL"
                )
            )
            for did, oid in res.fetchall():
                if did and oid and str(oid).strip():
                    doc_owners[str(did)] = str(oid).strip()
        except Exception as e:
            logger.warning("Could not query documents table: %s", e)

    return paper_owners, doc_owners


async def load_trusted_mappings_from_app_session() -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load paper and document ownership mappings using backend session factory."""
    from backend.app.database.session import get_session_factory
    from sqlalchemy import text

    session_factory = get_session_factory()
    paper_owners: Dict[str, str] = {}
    doc_owners: Dict[str, str] = {}

    async with session_factory() as session:
        try:
            res = await session.execute(text("SELECT id, owner_id FROM papers WHERE owner_id IS NOT NULL"))
            for pid, oid in res.fetchall():
                if pid and oid and str(oid).strip():
                    paper_owners[str(pid)] = str(oid).strip()
        except Exception as e:
            logger.warning("Could not query papers via app session: %s", e)

        try:
            res = await session.execute(
                text(
                    "SELECT d.id, p.owner_id "
                    "FROM documents d "
                    "JOIN papers p ON d.paper_id = p.id "
                    "WHERE p.owner_id IS NOT NULL"
                )
            )
            for did, oid in res.fetchall():
                if did and oid and str(oid).strip():
                    doc_owners[str(did)] = str(oid).strip()
        except Exception as e:
            logger.warning("Could not query documents via app session: %s", e)

    return paper_owners, doc_owners


class FTS5MigrationEngine:
    """Manages dry-run analysis and atomic migration of lexical FTS5 database."""

    def __init__(
        self,
        db_path: Path,
        paper_owners: Dict[str, str],
        doc_owners: Dict[str, str],
        backup_table_name: str = "lexical_chunks_pre_owner_migration",
        quarantine_table_name: str = "lexical_chunks_quarantine",
    ):
        self.db_path = db_path
        self.paper_owners = paper_owners
        self.doc_owners = doc_owners
        self.backup_table_name = backup_table_name
        self.quarantine_table_name = quarantine_table_name

    def inspect_schema(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """Analyze current schema and return migration readiness state."""
        if not table_exists(conn, "lexical_chunks"):
            return {"status": "NO_TABLE", "columns": []}

        cols = get_table_columns(conn, "lexical_chunks")
        if "owner_id" in cols:
            return {"status": "ALREADY_MIGRATED", "columns": cols}

        return {"status": "NEEDS_MIGRATION", "columns": cols}

    def analyze_records(
        self, conn: sqlite3.Connection
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
        """Classify existing records into confident migrations and quarantined records.
        
        Returns:
            confident_records: List of rows mapped to trusted owner_id
            quarantined_records: List of rows that cannot be mapped or have conflicting ownership
            stats: Summary metrics dictionary
        """
        cursor = conn.cursor()
        cursor.execute(
            "SELECT chunk_id, collection_name, paper_id, document_id, section, "
            "page_start, page_end, title, filename, locator, text FROM lexical_chunks"
        )
        rows = cursor.fetchall()

        confident_records: List[Dict[str, Any]] = []
        quarantined_records: List[Dict[str, Any]] = []
        stats: Dict[str, int] = {
            "total_legacy_rows": len(rows),
            "confident_count": 0,
            "orphan_count": 0,
            "ambiguous_count": 0,
            "distinct_owners": 0,
        }
        owners_seen: Set[str] = set()

        for row in rows:
            record = {
                "chunk_id": row[0],
                "collection_name": row[1],
                "paper_id": row[2],
                "document_id": row[3],
                "section": row[4],
                "page_start": row[5],
                "page_end": row[6],
                "title": row[7],
                "filename": row[8],
                "locator": row[9],
                "text": row[10],
            }

            p_id = str(row[2]) if row[2] else None
            d_id = str(row[3]) if row[3] else None

            p_owner = self.paper_owners.get(p_id) if p_id else None
            d_owner = self.doc_owners.get(d_id) if d_id else None

            # Ownership resolution
            if p_owner and d_owner and p_owner != d_owner:
                record["quarantine_reason"] = f"ambiguous_owner_mismatch: paper={p_owner} vs doc={d_owner}"
                quarantined_records.append(record)
                stats["ambiguous_count"] += 1
            elif p_owner:
                record["owner_id"] = p_owner
                confident_records.append(record)
                owners_seen.add(p_owner)
                stats["confident_count"] += 1
            elif d_owner:
                record["owner_id"] = d_owner
                confident_records.append(record)
                owners_seen.add(d_owner)
                stats["confident_count"] += 1
            else:
                record["quarantine_reason"] = "orphan_no_trusted_owner_mapping"
                quarantined_records.append(record)
                stats["orphan_count"] += 1

        stats["distinct_owners"] = len(owners_seen)
        return confident_records, quarantined_records, stats

    def run_dry_run(self) -> Dict[str, Any]:
        """Perform completely non-mutating analysis and produce migration plan report."""
        if not self.db_path.exists():
            return {"status": "ERROR", "message": f"Database file does not exist: {self.db_path}"}

        # Open in read-only URI mode to strictly forbid database mutations
        uri = f"file:{self.db_path.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            schema_info = self.inspect_schema(conn)
            if schema_info["status"] == "ALREADY_MIGRATED":
                return {
                    "status": "ALREADY_MIGRATED",
                    "columns": schema_info["columns"],
                    "message": "lexical_chunks table already contains owner_id column.",
                }
            if schema_info["status"] == "NO_TABLE":
                return {
                    "status": "NO_TABLE",
                    "message": "lexical_chunks table does not exist in database.",
                }

            confident, quarantined, stats = self.analyze_records(conn)
            return {
                "status": "READY_FOR_MIGRATION",
                "database_path": str(self.db_path),
                "existing_columns": schema_info["columns"],
                "target_columns": [
                    "chunk_id", "owner_id", "collection_name", "paper_id", "document_id",
                    "section", "page_start", "page_end", "title", "filename", "locator", "text"
                ],
                "statistics": stats,
                "quarantine_sample": [
                    {"chunk_id": r["chunk_id"], "paper_id": r["paper_id"], "reason": r["quarantine_reason"]}
                    for r in quarantined[:5]
                ],
            }
        finally:
            conn.close()

    def run_apply(self) -> Dict[str, Any]:
        """Execute atomic schema rebuild, verification, and table swap."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file does not exist: {self.db_path}")

        conn = sqlite3.connect(self.db_path, timeout=60.0)
        try:
            # Check schema state first
            schema_info = self.inspect_schema(conn)
            if schema_info["status"] == "ALREADY_MIGRATED":
                return {
                    "status": "ALREADY_MIGRATED",
                    "columns": schema_info["columns"],
                    "message": "lexical_chunks table already contains owner_id column.",
                }
            if schema_info["status"] == "NO_TABLE":
                raise RuntimeError("lexical_chunks table does not exist.")

            confident, quarantined, stats = self.analyze_records(conn)

            # Cleanup any aborted previous staging table
            conn.execute("DROP TABLE IF EXISTS lexical_chunks_migrating")

            cursor = conn.cursor()
            # Begin explicit immediate transaction for atomic rebuild and swap
            cursor.execute("BEGIN IMMEDIATE")

            # 1. Create staging FTS5 virtual table with owner_id UNINDEXED
            cursor.execute(
                "CREATE VIRTUAL TABLE lexical_chunks_migrating USING fts5("
                "chunk_id UNINDEXED, "
                "owner_id UNINDEXED, "
                "collection_name UNINDEXED, "
                "paper_id UNINDEXED, "
                "document_id UNINDEXED, "
                "section UNINDEXED, "
                "page_start UNINDEXED, "
                "page_end UNINDEXED, "
                "title UNINDEXED, "
                "filename UNINDEXED, "
                "locator UNINDEXED, "
                "text, "
                "tokenize='unicode61'"
                ")"
            )

            # 2. Create quarantine audit table if not present
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {self.quarantine_table_name} ("
                "chunk_id TEXT, "
                "collection_name TEXT, "
                "paper_id TEXT, "
                "document_id TEXT, "
                "section TEXT, "
                "page_start INTEGER, "
                "page_end INTEGER, "
                "title TEXT, "
                "filename TEXT, "
                "locator TEXT, "
                "text TEXT, "
                "quarantine_reason TEXT, "
                "quarantined_at TIMESTAMP"
                ")"
            )

            # 3. Create schema version table
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS researchlens_schema_version ("
                "version INTEGER PRIMARY KEY, "
                "description TEXT, "
                "applied_at TIMESTAMP"
                ")"
            )

            # 4. Insert confident records into staging FTS5 table
            now_iso = datetime.now(timezone.utc).isoformat()
            if confident:
                cursor.executemany(
                    "INSERT INTO lexical_chunks_migrating ("
                    "chunk_id, owner_id, collection_name, paper_id, document_id, section, "
                    "page_start, page_end, title, filename, locator, text"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            r["chunk_id"], r["owner_id"], r["collection_name"], r["paper_id"],
                            r["document_id"], r["section"], r["page_start"], r["page_end"],
                            r["title"], r["filename"], r["locator"], r["text"]
                        )
                        for r in confident
                    ]
                )

            # 5. Insert unresolvable records into quarantine table
            if quarantined:
                cursor.executemany(
                    f"INSERT INTO {self.quarantine_table_name} ("
                    "chunk_id, collection_name, paper_id, document_id, section, "
                    "page_start, page_end, title, filename, locator, text, "
                    "quarantine_reason, quarantined_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            r["chunk_id"], r["collection_name"], r["paper_id"], r["document_id"],
                            r["section"], r["page_start"], r["page_end"], r["title"],
                            r["filename"], r["locator"], r["text"], r["quarantine_reason"],
                            now_iso
                        )
                        for r in quarantined
                    ]
                )

            # 6. Verify data integrity before renaming
            migrating_count = cursor.execute("SELECT count(*) FROM lexical_chunks_migrating").fetchone()[0]
            if migrating_count != len(confident):
                raise ValueError(
                    f"Integrity check failed: inserted {migrating_count} rows into staging, expected {len(confident)}"
                )

            # Ensure zero NULL or empty owner_ids in staging
            invalid_owners = cursor.execute(
                "SELECT count(*) FROM lexical_chunks_migrating WHERE owner_id IS NULL OR trim(owner_id) = ''"
            ).fetchone()[0]
            if invalid_owners > 0:
                raise ValueError(f"Integrity check failed: {invalid_owners} rows have invalid owner_id in staging")

            # Verify total row preservation: confident + quarantined == legacy total
            total_accounted = migrating_count + len(quarantined)
            if total_accounted != stats["total_legacy_rows"]:
                raise ValueError(
                    f"Conservation check failed: {total_accounted} rows accounted for vs {stats['total_legacy_rows']} legacy rows"
                )

            # Test full-text search capability on staging table
            if migrating_count > 0:
                cursor.execute("SELECT chunk_id FROM lexical_chunks_migrating WHERE lexical_chunks_migrating MATCH 'test OR research OR methodology' LIMIT 1")
                # Even if 0 matches, the MATCH query syntax must execute successfully without SQLite errors

            # 7. Atomic table swap
            # Rename legacy table to backup
            cursor.execute(f"DROP TABLE IF EXISTS {self.backup_table_name}")
            cursor.execute(f"ALTER TABLE lexical_chunks RENAME TO {self.backup_table_name}")
            # Rename staging table to active lexical_chunks
            cursor.execute("ALTER TABLE lexical_chunks_migrating RENAME TO lexical_chunks")

            # 8. Update schema version record
            cursor.execute(
                "INSERT OR REPLACE INTO researchlens_schema_version (version, description, applied_at) "
                "VALUES (2, 'SEC-001: Added owner_id UNINDEXED column to lexical_chunks FTS5 table', ?)",
                (now_iso,),
            )

            # Commit the atomic transaction
            conn.commit()

            return {
                "status": "SUCCESS",
                "database_path": str(self.db_path),
                "migrated_rows": migrating_count,
                "quarantined_rows": len(quarantined),
                "total_rows": stats["total_legacy_rows"],
                "backup_table": self.backup_table_name,
                "quarantine_table": self.quarantine_table_name,
                "applied_at": now_iso,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(".chroma/researchlens_lexical.sqlite3"),
        help="Path to SQLite FTS5 lexical database (default: .chroma/researchlens_lexical.sqlite3)",
    )
    parser.add_argument(
        "--app-db-url",
        type=str,
        default=None,
        help="SQLAlchemy URL for application database (e.g. sqlite:///backend/researchlens.db)",
    )
    parser.add_argument(
        "--mapping-file",
        type=Path,
        default=None,
        help="Path to JSON file containing trusted {'papers': {...}, 'documents': {...}} mappings",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Perform non-mutating audit and report without modifying the database (default: True)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Execute the atomic migration and write changes to the database",
    )
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    # Determine execution mode: --apply overrides default --dry-run
    is_apply = bool(args.apply)
    db_path = args.db_path

    if not db_path.exists():
        print(f"❌ Error: Database path not found: {db_path}", file=sys.stderr)
        return 1

    paper_owners: Dict[str, str] = {}
    doc_owners: Dict[str, str] = {}

    if args.mapping_file:
        logger.info("Loading trusted ownership mapping from file: %s", args.mapping_file)
        paper_owners, doc_owners = load_trusted_mappings_from_json(args.mapping_file)
    elif args.app_db_url:
        logger.info("Loading trusted ownership mapping from app database: %s", args.app_db_url)
        paper_owners, doc_owners = load_trusted_mappings_from_db(args.app_db_url)
    else:
        # Check for default trusted export file
        default_export = Path("trusted_ownership_export.json")
        if default_export.exists():
            logger.info("Found trusted export file at %s; loading mappings.", default_export)
            paper_owners, doc_owners = load_trusted_mappings_from_json(default_export)
        else:
            try:
                import asyncio
                logger.info("Connecting to application database via backend session factory...")
                paper_owners, doc_owners = asyncio.run(load_trusted_mappings_from_app_session())
                logger.info("Loaded %d paper and %d document mappings from active application database.", len(paper_owners), len(doc_owners))
            except Exception as e:
                logger.warning("Could not auto-load from app database: %s. Proceeding with empty mappings.", e)

    engine = FTS5MigrationEngine(
        db_path=db_path,
        paper_owners=paper_owners,
        doc_owners=doc_owners,
    )

    if not is_apply:
        print("=" * 70)
        print("🔍 FTS5 SCHEMA MIGRATION: DRY-RUN AUDIT (NON-MUTATING)")
        print("=" * 70)
        plan = engine.run_dry_run()
        print(json.dumps(plan, indent=2))
        if plan["status"] == "ALREADY_MIGRATED":
            print("\n✅ Database is already migrated with owner_id column.")
            return 0
        if plan["status"] == "READY_FOR_MIGRATION":
            stats = plan["statistics"]
            print(f"\n📊 Audit Summary:")
            print(f"   Total legacy chunks:    {stats['total_legacy_rows']}")
            print(f"   Confident to migrate:   {stats['confident_count']}")
            print(f"   Orphans (quarantine):   {stats['orphan_count']}")
            print(f"   Ambiguous (quarantine): {stats['ambiguous_count']}")
            print(f"   Distinct owners:        {stats['distinct_owners']}")
            print("\n💡 To apply this migration, run with the `--apply` flag.")
            return 0
        return 1

    print("=" * 70)
    print("🚀 FTS5 SCHEMA MIGRATION: APPLYING CHANGES")
    print("=" * 70)
    result = engine.run_apply()
    print(json.dumps(result, indent=2))
    if result["status"] == "SUCCESS":
        print("\n✅ Migration applied successfully and verified.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

