#!/usr/bin/env python3
"""Export authoritative ownership mappings from the application database.

Generates a secure, versioned, checksummed JSON mapping containing:
  chunk_id -> document_id -> paper_id -> owner_id
without exposing database credentials or passwords.

Usage:
    python scripts/export_trusted_ownership_mapping.py --output-file trusted_ownership_export.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from backend.app.core.config import get_settings
from backend.app.database.session import get_session_factory

logger = logging.getLogger("export_mapping")


def sanitize_db_source(url_str: str) -> dict:
    """Extract non-sensitive connection metadata."""
    parsed = urlparse(url_str)
    return {
        "dialect": parsed.scheme.split("+")[0],
        "driver": parsed.scheme.split("+")[1] if "+" in parsed.scheme else "default",
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/"),
    }


async def export_ownership_mapping(output_path: Path) -> dict:
    settings = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as session:
        # Load papers
        paper_res = await session.execute(
            text("SELECT id, owner_id, title FROM papers WHERE owner_id IS NOT NULL")
        )
        papers = {}
        for pid, oid, _ in paper_res.fetchall():
            if pid and oid and str(oid).strip():
                papers[str(pid)] = str(oid).strip()

        # Load documents and join with papers for authoritative owner
        doc_res = await session.execute(
            text(
                "SELECT d.id, p.owner_id "
                "FROM documents d "
                "JOIN papers p ON d.paper_id = p.id "
                "WHERE p.owner_id IS NOT NULL"
            )
        )
        documents = {}
        for did, oid in doc_res.fetchall():
            if did and oid and str(oid).strip():
                documents[str(did)] = str(oid).strip()

        user_count = (await session.execute(text("SELECT count(*) FROM users"))).scalar() or 0

    export_data = {
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_database": sanitize_db_source(settings.database_url),
        "record_counts": {
            "papers": len(papers),
            "documents": len(documents),
            "users": user_count,
        },
        "papers": papers,
        "documents": documents,
    }

    # Calculate SHA-256 integrity checksum of the mapping payload
    payload_str = json.dumps({"papers": papers, "documents": documents}, sort_keys=True)
    checksum = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    export_data["integrity_checksum_sha256"] = checksum

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)

    logger.info("Successfully exported %d paper and %d document ownership mappings to %s", len(papers), len(documents), output_path)
    return export_data


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("trusted_ownership_export.json"),
        help="Target output path for the JSON export (default: trusted_ownership_export.json)",
    )
    args = parser.parse_args()

    data = asyncio.run(export_ownership_mapping(args.output_file))
    print(f"Export completed: {args.output_file}")
    print(f"  Papers mapped:    {len(data['papers'])}")
    print(f"  Documents mapped: {len(data['documents'])}")
    print(f"  Integrity SHA256: {data['integrity_checksum_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

