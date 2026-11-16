import pytest
from rag.retrieval.query import RetrievedSource
from rag.intelligence.confidence_evaluator import ConfidenceLevel, ConfidenceReport
from rag.generation.evidence_validator import EvidenceValidator, ValidatedAnswerPayload


def test_validator_clean_and_repair_json():
    # 1. Standard JSON with code fences
    raw1 = """```json
    {
      "direct_answer": "Algorithms are classified by design and architecture.",
      "sections": [
        {
          "heading": "Divide and Conquer",
          "explanation": "Breaks problems into subproblems.",
          "evidence_ids": ["S1"]
        }
      ]
    }
    ```"""
    parsed1 = EvidenceValidator.clean_and_repair_json(raw1)
    assert parsed1 is not None
    assert parsed1["direct_answer"] == "Algorithms are classified by design and architecture."
    assert len(parsed1["sections"]) == 1

    # 2. JSON with unquoted source IDs e.g. [S1, S2] and trailing commas
    raw2 = """
    {
      "direct_answer": "Test answer",
      "sections": [
        {
          "heading": "Greedy Method",
          "explanation": "Selects local optimal choices.",
          "evidence_ids": [S1, S2],
        },
      ],
    }
    """
    parsed2 = EvidenceValidator.clean_and_repair_json(raw2)
    assert parsed2 is not None
    assert parsed2["sections"][0]["evidence_ids"] == ["S1", "S2"]


def test_validator_rejects_hallucinated_citations():
    sources = [
        RetrievedSource(source_id="S1", chunk_id="c1", document_id="d1", paper_id="p1",
                        page_start=10, page_end=10, section="Intro", text="Sample text 1"),
        RetrievedSource(source_id="S2", chunk_id="c2", document_id="d1", paper_id="p1",
                        page_start=20, page_end=20, section="Methods", text="Sample text 2"),
    ]
    raw = """
    {
      "direct_answer": "Summary text",
      "sections": [
        {
          "heading": "Valid Section",
          "explanation": "Grounded text",
          "evidence_ids": ["S1", "S99", "INVALID_ID"]
        }
      ]
    }
    """
    validator = EvidenceValidator()
    is_valid, payload, reasons = validator.validate(raw, sources)
    assert is_valid is True
    assert payload is not None
    assert payload.sections[0].evidence_ids == ["S1"]
    assert any("S99" in r for r in reasons)


def test_validator_format_to_markdown():
    sources = [
        RetrievedSource(source_id="S1", chunk_id="c1", document_id="d1", paper_id="p1",
                        page_start=10, page_end=10, section="Intro", text="Sample text 1", title="Cormen"),
    ]
    conf = ConfidenceReport(
        level=ConfidenceLevel.STRONG,
        overall_confidence_score=0.95,
        is_definitive_answer=True,
        evidence_signals=["explicit definition confirmed"],
        justification="Strong match"
    )
    raw = """
    {
      "direct_answer": "Algorithms are step-by-step procedures.",
      "sections": [
        {
          "heading": "Divide and Conquer",
          "explanation": "Divides into subproblems.",
          "key_points": ["Recursive", "Independent subproblems"],
          "evidence_ids": ["S1"]
        }
      ],
      "conclusion": "These techniques form the core of algorithmic design."
    }
    """
    validator = EvidenceValidator()
    is_valid, payload, _ = validator.validate(raw, sources)
    assert is_valid is True
    md = validator.format_to_markdown(payload, sources, conf)
    assert "Divide and Conquer [S1]" in md
    assert "- Recursive" in md
    assert "**Confidence Tier:** STRONG (95%)" in md
    assert "**Grounding Status:** 100% verified" in md
