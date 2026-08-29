"""
Unit tests for Grounded LLM Generation, Prompting, and Response Parsing.
"""

import pytest
from rag.generation.llm_client import MockGroundedLLMClient
from rag.generation.response_parser import ResponseParser
from rag.generation.generator import GroundedGenerator
from rag.context.context_builder import ContextBuilder
from rag.retrieval.query import RetrievedSource


def test_response_parser_extracts_citations():
    text = "The Transformer architecture replaces recurrence [S1]. In Section 4, evaluation shows 28.4 BLEU [S1, S2]."
    parsed = ResponseParser.parse(text)
    assert parsed.cleaned_answer == text
    assert parsed.cited_source_ids == ["S1", "S2"]


def test_mock_grounded_llm_insufficient_evidence():
    client = MockGroundedLLMClient()
    output = client.generate(
        system_prompt="You are ResearchLens AI.",
        user_prompt="CONTEXT EVIDENCE:\n[NO RELEVANT EVIDENCE FOUND IN INDEXED PAPERS]\n\nQUESTION: What is BERT?",
    )
    assert "insufficient evidence" in output.lower()


def test_grounded_generator_qa():
    sources = [
        RetrievedSource(
            source_id="S1",
            chunk_id="c_01",
            paper_id="paper_1",
            document_id="d_1",
            page_start=1,
            page_end=1,
            section="Results",
            text="The model achieved a BLEU score of 28.4 on English-to-German translation.",
        )
    ]
    builder = ContextBuilder()
    ctx = builder.build_context(sources)

    generator = GroundedGenerator(llm_client=MockGroundedLLMClient())
    result = generator.generate_answer("What was the BLEU score?", ctx)

    assert "28.4" in result.answer
    assert "[S1]" in result.answer
    assert "S1" in result.parsed.cited_source_ids
