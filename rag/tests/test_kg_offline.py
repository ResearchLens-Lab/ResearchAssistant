import os
import socket
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch

from rag.intelligence.concept_graph_extractor import ConceptGraphExtractor, normalize_term


class MockChunk:
    def __init__(self, text: str, section: str, page: int):
        self.text = text
        self.metadata = type("Metadata", (), {"section": section, "page_start": page})()


def test_concept_extraction_from_text():
    extractor = ConceptGraphExtractor()

    text = (
        "Chapter 13: Red-Black Trees\n\n"
        "A red-black tree is a binary search tree that satisfies five red-black properties.\n"
        "A binary search tree is defined as an ordered node-based binary tree.\n"
        "For details on node deletion, see Section 13.4.\n"
        "Theorem 13.1: A red-black tree with n internal nodes has height at most 2 lg(n + 1).\n"
    )

    res = extractor.extract_from_text(text, section_name="Chapter 13: Red-Black Trees", page_number=308)

    concepts = res["concepts"]
    relations = res["relations"]

    # 1. Verify concept extraction
    concept_names = [c["name"].lower() for c in concepts]
    assert any("red-black tree" in name or "red-black trees" in name for name in concept_names)
    assert any("binary search tree" in name for name in concept_names)

    # 2. Verify relation extraction
    # Specializes (is a binary search tree)
    spec_rels = [r for r in relations if r["type"] == "specializes"]
    assert len(spec_rels) >= 1
    assert any("binary search tree" in r["target"].lower() for r in spec_rels)

    # Cross references (see Section 13.4)
    ref_rels = [r for r in relations if r["type"] == "references"]
    assert len(ref_rels) >= 1
    assert any("section 13.4" in r["target"].lower() for r in ref_rels)


def test_kg_ingestion_and_relation_linking(tmp_path: Path):
    db_file = tmp_path / "test_kg.sqlite3"
    extractor = ConceptGraphExtractor(db_path=db_file)

    chunks = [
        MockChunk(
            text="A red-black tree is a binary search tree that satisfies five properties. For deletion, see Section 13.4.",
            section="Section 13.1 Properties of Red-Black Trees",
            page=308,
        ),
        MockChunk(
            text="Section 13.4 Deletion describes how to remove a node while preserving the black-height invariant.",
            section="Section 13.4 Deletion",
            page=323,
        ),
    ]

    stats = extractor.ingest_document_kg(
        owner_id="test_user_kg",
        paper_id="paper_cormen_kg",
        document_id="doc_cormen_kg",
        chunks_or_sections=chunks,
    )

    assert stats["concepts"] >= 2
    assert stats["evidence"] >= 2
    assert stats["relationships"] >= 1

    # Verify tables directly in SQLite
    conn = sqlite3.connect(db_file)
    try:
        nodes = conn.execute("SELECT canonical_name, node_type FROM kg_nodes").fetchall()
        assert len(nodes) >= 2

        rels = conn.execute("SELECT relationship_type FROM kg_relationships").fetchall()
        assert len(rels) >= 1

        # Check views
        concepts_view = conn.execute("SELECT name FROM kg_concepts").fetchall()
        assert len(concepts_view) == len(nodes)

        # 1-hop neighbors check
        neighbors = extractor.get_1hop_neighbors("Red-Black Tree")
        assert len(neighbors) >= 1
    finally:
        conn.close()


def test_kg_offline_operation_zero_network(tmp_path: Path):
    db_file = tmp_path / "test_kg_offline.sqlite3"
    extractor = ConceptGraphExtractor(db_path=db_file)

    chunks = [
        MockChunk(
            text="Breadth-first search is an algorithm that visits all vertices of a graph at distance k before k+1.",
            section="Section 22.2 Breadth-first search",
            page=594,
        ),
    ]

    def _fail_network(*args, **kwargs):
        raise RuntimeError("Network call attempted during offline KG extraction!")

    with patch.object(socket.socket, "connect", side_effect=_fail_network):
        stats = extractor.ingest_document_kg(
            owner_id="offline_user",
            paper_id="paper_offline",
            document_id="doc_offline",
            chunks_or_sections=chunks,
        )
        neighbors = extractor.get_1hop_neighbors("Breadth-first search")

    assert stats["concepts"] >= 1
    assert isinstance(neighbors, list)
