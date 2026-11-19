"""Concept Graph Extractor for offline Knowledge Graph population.

Extracts canonical concepts, definition occurrences, and cross-references from
normalised section titles, defined terms, and structural citations.
Populates kg_nodes, kg_relationships, and kg_graph_evidence with zero network calls.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def normalize_term(term: str) -> str:
    cleaned = re.sub(r"[\W_]+", " ", term).strip().lower()
    return cleaned


class ConceptGraphExtractor:
    """Extracts concepts, occurrences, and relationships from text/sections."""

    # Patterns for definition extraction
    DEF_PATTERNS = [
        re.compile(
            r"(?:(?:A|An|The)\s+)?\b([A-Z][a-zA-Z0-9\-]+(?:\s+[a-zA-Z0-9\-]+){0,4})\s+(?:is|are|refers to|means)\s+(?:a|an|the|defined as|any|used to|a particular)\s+([^.\n]{10,250}\.)",
            re.MULTILINE,
        ),
        re.compile(
            r"\b([A-Z][a-zA-Z0-9\-]+(?:\s+[a-zA-Z0-9\-]+){0,4})\s+is\s+defined\s+as\s+([^.\n]{10,250}\.)",
            re.MULTILINE,
        ),
        re.compile(
            r"\b(?:Definition|Theorem|Lemma)\s+(\d+(?:\.\d+)*)[:.]\s*([A-Z][a-zA-Z0-9\-\s]{2,40}?)\b",
            re.MULTILINE,
        ),
        re.compile(
            r"\*\*([A-Z][a-zA-Z0-9\-]+(?:\s+[a-zA-Z0-9\-]+){0,4})\*\*[:\-]\s*([^.\n]{10,250}\.)",
            re.MULTILINE,
        ),
    ]

    # Patterns for cross-references
    XREF_PATTERNS = [
        re.compile(r"\b(?:see|in)\s+(?:Section|Chapter)\s+(\d+(?:\.\d+)*)", re.IGNORECASE),
        re.compile(r"\b(?:by|see)\s+(?:Theorem|Lemma)\s+(\d+(?:\.\d+)*)", re.IGNORECASE),
    ]

    # Specialization / Generalization pattern
    IS_A_PATTERN = re.compile(
        r"\b([a-zA-Z0-9\-\s]{3,35})\s+is\s+(?:a|an)\s+([a-zA-Z0-9\-\s]{3,35})\s+that\b",
        re.IGNORECASE,
    )

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def _ensure_tables_and_views(self, conn: sqlite3.Connection) -> None:
        """Ensure kg_ tables and compatibility views exist in the SQLite database."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                identity_key TEXT NOT NULL,
                description TEXT,
                identifiers TEXT DEFAULT '{}',
                metadata TEXT DEFAULT '{}',
                first_observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_confirmed_at TIMESTAMP,
                first_document_id TEXT,
                first_extraction_run_id TEXT,
                review_status TEXT DEFAULT 'approved',
                version INTEGER DEFAULT 1,
                merged_into_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_relationships (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                direction TEXT DEFAULT 'directed',
                assertion_status TEXT DEFAULT 'current',
                review_status TEXT DEFAULT 'approved',
                confidence REAL,
                first_observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_confirmed_at TIMESTAMP,
                first_document_id TEXT,
                first_extraction_run_id TEXT,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_graph_evidence (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                node_id TEXT,
                relationship_id TEXT,
                source_document_id TEXT NOT NULL,
                source_paper_id TEXT,
                extraction_run_id TEXT NOT NULL,
                record_id TEXT NOT NULL,
                source_block_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                section_id TEXT,
                exact_text TEXT NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                extraction_method TEXT NOT NULL,
                extraction_version TEXT NOT NULL,
                review_status TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                reviewed_at TIMESTAMP NOT NULL,
                private_source BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create compatibility views for kg_concepts, kg_relations, kg_occurrences
        conn.execute("""
            CREATE VIEW IF NOT EXISTS kg_concepts AS
            SELECT id, owner_id, canonical_name AS name, node_type AS type, description
            FROM kg_nodes
        """)
        conn.execute("""
            CREATE VIEW IF NOT EXISTS kg_relations AS
            SELECT id, owner_id, source_node_id, target_node_id, relationship_type AS type, confidence
            FROM kg_relationships
        """)
        conn.execute("""
            CREATE VIEW IF NOT EXISTS kg_occurrences AS
            SELECT id, owner_id, node_id, source_document_id AS document_id, source_paper_id AS paper_id, page_number, section_id, exact_text
            FROM kg_graph_evidence
        """)
        conn.commit()

    def extract_from_text(
        self,
        text: str,
        section_name: str = "",
        page_number: int = 1,
    ) -> Dict[str, Any]:
        """Extract concepts, definitions, and cross-references from a single text block."""
        concepts: List[Dict[str, Any]] = []
        relations: List[Dict[str, Any]] = []

        # 1. Section Title Concept
        clean_sec = re.sub(r"^(?:(?:Chapter|Section|Part)\s+)?[\d.]+\s*[:\-]?\s*", "", section_name).strip()
        clean_sec = re.sub(r"^(?:What\s+is\s+(?:an?\s+)?|Why\s+(?:the\s+)?|How\s+to\s+)", "", clean_sec, flags=re.I).strip()
        clean_sec = re.sub(r"\?$", "", clean_sec).strip()
        ignore_titles = ("main content", "preface", "title page", "copyright page", "acknowledgements", "other books by")
        if len(clean_sec) >= 3 and not any(clean_sec.lower().startswith(ign) for ign in ignore_titles):
            concepts.append({
                "name": clean_sec.title(),
                "type": "CONCEPT",
                "description": f"Topic: {section_name}",
                "page": page_number,
                "section": section_name,
                "text": section_name,
            })

        # 2. Defined Terms
        for pat in self.DEF_PATTERNS:
            for match in pat.finditer(text):
                groups = match.groups()
                term = groups[0].strip() if groups else ""
                snippet = groups[1].strip() if len(groups) > 1 else match.group(0)
                if len(term) >= 3 and not term.lower() in ("the", "this", "that", "these", "those"):
                    concepts.append({
                        "name": term.title(),
                        "type": "CONCEPT",
                        "description": snippet,
                        "page": page_number,
                        "section": section_name,
                        "text": match.group(0),
                    })

        # 3. Specializes / Generalizes (is-a relations)
        for match in self.IS_A_PATTERN.finditer(text):
            sub_concept = match.group(1).strip().title()
            super_concept = match.group(2).strip().title()
            if len(sub_concept) >= 3 and len(super_concept) >= 3:
                relations.append({
                    "source": sub_concept,
                    "target": super_concept,
                    "type": "specializes",
                    "confidence": 0.9,
                })

        # 4. Cross-references (references relations)
        for pat in self.XREF_PATTERNS:
            for match in pat.finditer(text):
                target_ref = f"Section {match.group(1)}"
                if clean_sec:
                    relations.append({
                        "source": clean_sec.title(),
                        "target": target_ref,
                        "type": "references",
                        "confidence": 0.85,
                    })

        return {"concepts": concepts, "relations": relations}

    def ingest_document_kg(
        self,
        owner_id: str,
        paper_id: str,
        document_id: str,
        chunks_or_sections: List[Any],
        db_path: Optional[Path] = None,
    ) -> Dict[str, int]:
        """Ingest extracted concepts and relationships into the SQLite database."""
        target_db = db_path or self.db_path
        if not target_db:
            raise ValueError("Target database path is required for KG ingestion")

        conn = sqlite3.connect(target_db)
        try:
            self._ensure_tables_and_views(conn)

            node_id_map: Dict[str, str] = {}
            node_counts: Dict[str, int] = {}

            # Read existing nodes for this owner to merge/dedup
            cur = conn.cursor()
            cur.execute(
                "SELECT id, canonical_name, identity_key FROM kg_nodes WHERE owner_id = ?",
                (owner_id,),
            )
            for nid, cname, ikey in cur.fetchall():
                node_id_map[ikey] = nid

            total_concepts = 0
            total_evidence = 0
            total_relations = 0

            pending_relations: List[Dict[str, Any]] = []

            now_str = datetime.utcnow().isoformat()
            for item in chunks_or_sections:
                text = getattr(item, "text", "") or ""
                meta = getattr(item, "metadata", None)
                section_name = ""
                page_num = 1
                if meta:
                    section_name = getattr(meta, "section", "") or ""
                    page_num = getattr(meta, "page_start", 1) or 1
                elif hasattr(item, "name"):
                    section_name = getattr(item, "name", "")
                    page_num = getattr(item, "page_start", 1) or 1

                extracted = self.extract_from_text(text, section_name, page_num)

                for c in extracted["concepts"]:
                    name = c["name"]
                    ikey = normalize_term(name)
                    if not ikey:
                        continue

                    node_counts[ikey] = node_counts.get(ikey, 0) + 1

                    if ikey not in node_id_map:
                        node_id = str(uuid.uuid4())
                        node_id_map[ikey] = node_id
                        cur.execute(
                            """
                            INSERT INTO kg_nodes (
                                id, owner_id, node_type, canonical_name, identity_key, description,
                                first_document_id, identifiers, metadata, first_observed_at, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?, ?)
                            """,
                            (
                                node_id,
                                owner_id,
                                c["type"],
                                name,
                                ikey,
                                c.get("description", ""),
                                document_id,
                                json.dumps({"paper_id": paper_id, "document_id": document_id}),
                                now_str,
                                now_str,
                                now_str,
                            ),
                        )
                        total_concepts += 1
                    else:
                        node_id = node_id_map[ikey]

                    # Record evidence / occurrence
                    ev_id = str(uuid.uuid4())
                    cur.execute(
                        """
                        INSERT INTO kg_graph_evidence (
                            id, owner_id, node_id, source_document_id, source_paper_id,
                            extraction_run_id, record_id, source_block_id, page_number,
                            section_id, exact_text, char_start, char_end, extraction_method,
                            extraction_version, review_status, reviewer, reviewed_at, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ev_id,
                            owner_id,
                            node_id,
                            document_id,
                            paper_id,
                            "run_offline_v1",
                            str(uuid.uuid4()),
                            f"page_{page_num}",
                            page_num,
                            section_name,
                            c.get("text", "")[:500],
                            0,
                            len(c.get("text", "")),
                            "regex_offline",
                            "1.0",
                            "approved",
                            "system",
                            now_str,
                            now_str,
                        ),
                    )
                    total_evidence += 1

                pending_relations.extend(extracted["relations"])

            # Link relationships
            for rel in pending_relations:
                src_key = normalize_term(rel["source"])
                tgt_key = normalize_term(rel["target"])
                src_id = node_id_map.get(src_key)

                # If target is not already a node, create it if valid
                if tgt_key not in node_id_map and len(rel["target"]) >= 3:
                    tgt_id = str(uuid.uuid4())
                    node_id_map[tgt_key] = tgt_id
                    cur.execute(
                        """
                        INSERT INTO kg_nodes (
                            id, owner_id, node_type, canonical_name, identity_key, description,
                            first_document_id, identifiers, metadata, first_observed_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', '{}', ?, ?, ?)
                        """,
                        (
                            tgt_id,
                            owner_id,
                            "CONCEPT",
                            rel["target"].title(),
                            tgt_key,
                            f"Referenced concept: {rel['target']}",
                            document_id,
                            now_str,
                            now_str,
                            now_str,
                        ),
                    )
                    total_concepts += 1
                else:
                    tgt_id = node_id_map.get(tgt_key)

                if src_id and tgt_id and src_id != tgt_id:
                    # Check if relationship already exists
                    cur.execute(
                        """
                        SELECT id FROM kg_relationships
                        WHERE owner_id = ? AND source_node_id = ? AND target_node_id = ? AND relationship_type = ?
                        """,
                        (owner_id, src_id, tgt_id, rel["type"]),
                    )
                    if not cur.fetchone():
                        rel_id = str(uuid.uuid4())
                        cur.execute(
                            """
                            INSERT INTO kg_relationships (
                                id, owner_id, source_node_id, target_node_id, relationship_type, confidence,
                                first_document_id, first_observed_at, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                rel_id,
                                owner_id,
                                src_id,
                                tgt_id,
                                rel["type"],
                                rel.get("confidence", 0.8),
                                document_id,
                                now_str,
                                now_str,
                                now_str,
                            ),
                        )
                        total_relations += 1

            conn.commit()
            return {
                "concepts": total_concepts,
                "evidence": total_evidence,
                "relationships": total_relations,
            }
        finally:
            conn.close()

    def get_1hop_neighbors(
        self,
        concept: str,
        owner_id: Optional[str] = None,
        db_path: Optional[Path] = None,
    ) -> List[str]:
        """Lookup 1-hop related concepts for query expansion."""
        target_db = db_path or self.db_path
        if not target_db or not Path(target_db).exists():
            return []

        conn = sqlite3.connect(target_db)
        try:
            cur = conn.cursor()
            norm = normalize_term(concept)
            # Find matching node(s)
            cur.execute(
                "SELECT id FROM kg_nodes WHERE identity_key = ? OR canonical_name LIKE ? LIMIT 5",
                (norm, f"%{concept}%"),
            )
            node_ids = [r[0] for r in cur.fetchall()]
            if not node_ids:
                return []

            placeholders = ",".join(["?"] * len(node_ids))
            # Find neighbors via incoming and outgoing relationships
            cur.execute(
                f"""
                SELECT DISTINCT n.canonical_name
                FROM kg_relationships r
                JOIN kg_nodes n ON (n.id = r.target_node_id OR n.id = r.source_node_id)
                WHERE (r.source_node_id IN ({placeholders}) OR r.target_node_id IN ({placeholders}))
                  AND n.id NOT IN ({placeholders})
                LIMIT 10
                """,
                node_ids + node_ids + node_ids,
            )
            neighbors = [r[0] for r in cur.fetchall()]
            return neighbors
        except Exception as exc:
            logger.warning("Error fetching 1-hop neighbors: %s", exc)
            return []
        finally:
            conn.close()
