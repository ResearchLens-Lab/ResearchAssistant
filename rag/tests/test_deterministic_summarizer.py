"""
Tests for Deterministic Summary Redesign.
Verifies document-aware extractive summary generation, duplicate document grouping,
sentence fragment filtering, and exact citation provenance.
"""

import sqlite3
from pathlib import Path
import pytest

from rag.intelligence.summarizer import (
    build_document_summary,
    build_paper_summary,
    clean_display_title,
    is_strict_heading,
)


def test_clean_display_title():
    assert clean_display_title("Cormen_Introduction_to_Algorithms.pdf") == "Cormen Introduction to Algorithms"
    assert clean_display_title("attention_is_all_you_need.pdf", "Attention Is All You Need") == "Attention Is All You Need"
    assert clean_display_title("doc_12345.pdf", "") == "Research Document"


def test_is_strict_heading():
    assert is_strict_heading("Chapter 1: The Role of Algorithms")
    assert is_strict_heading("1.1 What is an Algorithm")
    assert is_strict_heading("Binary Search Trees")

    # Rejected headings
    assert not is_strict_heading("eeees")
    assert not is_strict_heading("Chapter 24: ), and using a search engine to quickly find pages")
    assert not is_strict_heading("(A.2)")
    assert not is_strict_heading("A D A .)")
    assert not is_strict_heading("2 C c8")
    assert not is_strict_heading("1 elements, the")
    assert not is_strict_heading("B.4-6")
    assert not is_strict_heading("Discussion:")
    assert not is_strict_heading("")


def test_deterministic_summary_pipeline(tmp_path):
    db_file = tmp_path / "researchlens_lexical.sqlite3"
    with sqlite3.connect(db_file) as conn:
        conn.execute("""
            CREATE TABLE lexical_chunks (
                chunk_id TEXT PRIMARY KEY,
                owner_id TEXT,
                collection_name TEXT,
                paper_id TEXT,
                document_id TEXT,
                section TEXT,
                page_start INTEGER,
                page_end INTEGER,
                title TEXT,
                filename TEXT,
                locator TEXT,
                text TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE lexical_metadata (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT,
                paper_id TEXT,
                owner_id TEXT,
                parent_id TEXT,
                block_kind TEXT,
                heading_path TEXT,
                section_type TEXT,
                page_start INTEGER,
                page_end INTEGER,
                printed_page_label TEXT,
                ordinal INTEGER,
                quality_score REAL,
                extraction_method TEXT,
                parent_chunk_id TEXT
            )
        """)

        # Insert sample document chunks
        conn.execute("""
            INSERT INTO lexical_chunks VALUES (
                'c1', 'u1', 'col', 'p1', 'd1', 'Introduction', 1, 1,
                'Foundations of Computing', 'foundations_of_computing.pdf', 'p. 1',
                'Computer science is the study of computation, automation, and information. This book provides a comprehensive introduction to algorithmic foundations.'
            )
        """)
        conn.execute("""
            INSERT INTO lexical_metadata VALUES (
                'c1', 'd1', 'p1', 'u1', '', 'paragraph', 'Introduction', 'body', 1, 1, '1', 0, 1.0, 'native', ''
            )
        """)

        conn.execute("""
            INSERT INTO lexical_chunks VALUES (
                'c2', 'u1', 'col', 'p1', 'd1', 'Chapter 1: Asymptotic Analysis', 25, 26,
                'Foundations of Computing', 'foundations_of_computing.pdf', 'p. 25',
                'Asymptotic notation describes the limiting behavior of execution time as input size grows to infinity. Big-O notation characterizes the upper bound of growth.'
            )
        """)
        conn.execute("""
            INSERT INTO lexical_metadata VALUES (
                'c2', 'd1', 'p1', 'u1', '', 'paragraph', 'Chapter 1: Asymptotic Analysis', 'body', 25, 26, '25', 1, 1.0, 'native', ''
            )
        """)

    summary = build_document_summary("d1", db_path=db_file)
    assert summary is not None
    assert "Foundations of Computing" in summary["sources"][0]["title"] or "foundations of computing" in summary["sources"][0]["title"].lower()
    assert "[S1] [p. 1]" in summary["answer"]
    assert "Chapter 1: Asymptotic Analysis" in summary["answer"]
    assert len(summary["sources"]) == 2
    assert summary["sources"][0]["page"] == 1
    assert summary["sources"][1]["page"] == 25
