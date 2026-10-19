"""
End-to-End integration test for complete RAG flow:
Document -> Normalization -> Chunking -> Embeddings -> ChromaDB -> Query -> Retrieval -> LLM Generation -> Citations -> API Contract.
"""

import pytest
from types import SimpleNamespace
from rag.tests.conftest import SAMPLE_PAPER_TEXT
from backend.app.integrations.rag_client import RAGClient


def test_end_to_end_rag_flow(full_rag_pipeline):
    ingest_p, query_p = full_rag_pipeline

    # 1. Ingest paper
    ingest_res = ingest_p.ingest_text(
        content=SAMPLE_PAPER_TEXT,
        paper_id="paper_attention_2017",
        metadata={
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
            "year": 2017,
        },
    )

    assert ingest_res.success is True
    assert ingest_res.status == "indexed"
    assert ingest_res.chunk_count > 0

    # 2. Query specific question
    rag_result = query_p.answer_question(
        question="What is the BLEU score achieved on WMT 2014 English-to-German translation?",
        paper_ids=["paper_attention_2017"],
        top_k=3,
    )

    assert rag_result.answer != ""
    assert "28.4" in rag_result.answer
    assert len(rag_result.sources) > 0

    # 3. Verify Source Provenance
    top_source = rag_result.sources[0]
    assert top_source.paper_id == "paper_attention_2017"
    assert top_source.locator
    assert top_source.section != ""
    assert "BLEU" in top_source.text or "translation" in top_source.text.lower()


def test_backend_rag_client_integration(full_rag_pipeline):
    ingest_p, query_p = full_rag_pipeline
    client = RAGClient(ingest_pipeline=ingest_p, query_pipeline=query_p)

    # Ingest through backend client
    res = client.ingest_text_content(
        content=SAMPLE_PAPER_TEXT,
        paper_id="paper_backend_integration",
        metadata={"title": "Attention Paper"},
    )
    assert res["success"] is True

    # Query through backend client
    chat_resp = client.ask_question(
        question="Explain the Scaled Dot-Product Attention equation.",
        paper_ids=["paper_backend_integration"],
    )

    assert "answer" in chat_resp
    assert "sources" in chat_resp
    assert len(chat_resp["sources"]) > 0
    assert chat_resp["sources"][0]["paper_id"] == "paper_backend_integration"
    assert "page" in chat_resp["sources"][0]
    assert "section" in chat_resp["sources"][0]
    assert "text" in chat_resp["sources"][0]


def test_query_pipeline_performs_one_safe_repair(full_rag_pipeline, monkeypatch):
    ingest, query = full_rag_pipeline
    ingest.ingest_text(content=SAMPLE_PAPER_TEXT, paper_id="paper_repair", metadata={"title": "Attention"})
    monkeypatch.setattr(query.generator, "generate_answer", lambda **kwargs: SimpleNamespace(
        answer="The Transformer achieved 99 BLEU on English-to-German translation [S1]."))
    repairs = []
    def repair(question, answer, issues, context):
        repairs.append((answer, issues))
        return "The Transformer achieves 28.4 BLEU on English-to-German translation [S1]."
    monkeypatch.setattr(query.generator, "repair_answer", repair)
    result = query.answer_question("What BLEU score was reported?", paper_ids=["paper_repair"])
    assert len(repairs) == 1
    assert "28.4 BLEU" in result.answer
    assert "99 BLEU" not in result.answer
    assert result.metadata["research"]["claim_verification"]["repair_attempted"] is True


def test_unresolved_repair_never_returns_the_unverified_numeric_claim(full_rag_pipeline, monkeypatch):
    ingest, query = full_rag_pipeline
    ingest.ingest_text(content=SAMPLE_PAPER_TEXT, paper_id="paper_repair_failure", metadata={"title": "Attention"})
    monkeypatch.setattr(query.generator, "generate_answer", lambda **kwargs: SimpleNamespace(
        answer="The Transformer achieved 99 BLEU on English-to-German translation [S1]."))
    repairs = []
    def repair(*args):
        repairs.append(1)
        return "The Transformer achieved 100 BLEU on English-to-German translation [S1]."
    monkeypatch.setattr(query.generator, "repair_answer", repair)
    result = query.answer_question("What BLEU score was reported?", paper_ids=["paper_repair_failure"])
    assert len(repairs) == 1
    assert "99 BLEU" not in result.answer and "100 BLEU" not in result.answer
    assert "not reported as established" in result.answer
    # Keep the cited passage available in the evidence inspector with its failed
    # claim check, even though neither unverified numeric answer is returned.
    assert [source.source_id for source in result.sources] == ["S1"]
    claim_report = result.metadata["research"]["claim_verification"]
    assert claim_report["items"][0]["status"] in {"unsupported", "contradicted"}
