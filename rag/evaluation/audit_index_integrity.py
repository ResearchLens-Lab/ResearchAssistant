"""Read-only Chroma/FTS index audit; reports mismatches and never repairs either index."""

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

from rag.config.settings import settings
from rag.vectorstore.chroma_client import ChromaClientFactory


def audit(collection_name: str | None = None) -> dict:
    lexical_path = Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3"
    if collection_name is None:
        if not settings.chroma_use_http and not Path(settings.chroma_persist_dir).is_dir():
            return {"read_only": True, "automatic_repair": False, "collections": [], "errors": ["Configured local Chroma directory does not exist."]}
        if not lexical_path.is_file():
            return {"read_only": True, "automatic_repair": False, "collections": [], "errors": ["SQLite FTS5 index does not exist."]}
        client = ChromaClientFactory.get_client()
        uri = lexical_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            lexical_names = {row[0] for row in connection.execute("SELECT DISTINCT collection_name FROM lexical_chunks")}
        finally:
            connection.close()
        available_names = {item.name for item in client.list_collections()}
        selected_names = sorted(lexical_names.intersection(available_names))
        return {
            "read_only": True,
            "automatic_repair": False,
            "collections": [audit(name) for name in selected_names],
            "unmatched_lexical_collections": sorted(lexical_names - available_names),
            "unmatched_vector_collections": sorted(available_names - lexical_names),
            "errors": [],
        }
    name = collection_name
    report = {
        "collection": name,
        "lexical_index": str(lexical_path),
        "read_only": True,
        "automatic_repair": False,
        "chroma_count": None,
        "lexical_count": None,
        "missing_from_lexical": [],
        "orphaned_in_lexical": [],
        "duplicate_lexical_chunk_ids": {},
        "provenance_mismatches": [],
        "errors": [],
    }
    if not settings.chroma_use_http and not Path(settings.chroma_persist_dir).is_dir():
        report["errors"].append("Configured local Chroma directory does not exist.")
        return report
    if not lexical_path.is_file():
        report["errors"].append("SQLite FTS5 index does not exist.")
        return report

    try:
        client = ChromaClientFactory.get_client()
        collection = client.get_collection(name=name)
        vector_records: dict[str, str] = {}
        offset = 0
        while True:
            batch = collection.get(limit=1000, offset=offset, include=["metadatas"])
            ids = batch.get("ids", [])
            metadata = batch.get("metadatas", [])
            if not ids:
                break
            for chunk_id, meta in zip(ids, metadata):
                vector_records[str(chunk_id)] = str((meta or {}).get("document_id") or "")
            offset += len(ids)
            if len(ids) < 1000:
                break
        report["chroma_count"] = len(vector_records)

        uri = lexical_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            rows = connection.execute(
                "SELECT chunk_id, document_id, count(*) FROM lexical_chunks WHERE collection_name = ? GROUP BY chunk_id, document_id",
                (name,),
            ).fetchall()
        finally:
            connection.close()
        lexical_counts = Counter(str(row[0]) for row in rows)
        lexical_docs = {str(row[0]): str(row[1] or "") for row in rows}
        report["lexical_count"] = sum(lexical_counts.values())
        report["missing_from_lexical"] = sorted(set(vector_records) - set(lexical_counts))
        report["orphaned_in_lexical"] = sorted(set(lexical_counts) - set(vector_records))
        report["duplicate_lexical_chunk_ids"] = {key: count for key, count in lexical_counts.items() if count > 1}
        report["provenance_mismatches"] = sorted(
            chunk_id for chunk_id in set(vector_records).intersection(lexical_docs)
            if vector_records[chunk_id] and lexical_docs[chunk_id] and vector_records[chunk_id] != lexical_docs[chunk_id]
        )
    except Exception as exc:  # report type without leaking paths or document contents
        report["errors"].append(f"{type(exc).__name__}: audit could not complete.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", default=None, help="Chroma collection to compare; defaults to configured collection")
    parser.add_argument("--output", default=None, help="Optional JSON report path")
    args = parser.parse_args()
    result = audit(args.collection)
    rendered = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
