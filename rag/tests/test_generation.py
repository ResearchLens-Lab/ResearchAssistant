"""
Unit tests for Grounded LLM Generation, Prompting, and Response Parsing.
"""

import pytest
from rag.generation.llm_client import MockGroundedLLMClient, OpenAILLMClient
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


def test_generator_forwards_only_real_provider_stream_deltas():
    class StreamingClient:
        supports_streaming = True
        def generate(self, **kwargs):
            raise AssertionError("streaming path should be used")
        def generate_stream(self, *args, **kwargs):
            yield "Draft "
            yield "answer [S1]."

    sources = [RetrievedSource(source_id="S1", chunk_id="c", paper_id="p", document_id="d",
                               page_start=1, page_end=1, locator="page:1", text="A supported answer.")]
    ctx = ContextBuilder().build_context(sources)
    events = []
    result = GroundedGenerator(StreamingClient()).generate_answer("Question?", ctx, on_token=events.append)
    assert result.answer == "Draft answer [S1]."
    assert [event["text"] for event in events] == ["Draft ", "answer [S1]."]
    assert all(event["provisional"] for event in events)


def test_mock_provider_uses_nonstreaming_fallback():
    sources = [RetrievedSource(source_id="S1", chunk_id="c", paper_id="p", document_id="d",
                               page_start=1, page_end=1, locator="page:1", text="A supported answer.")]
    ctx = ContextBuilder().build_context(sources)
    events = []
    GroundedGenerator(MockGroundedLLMClient()).generate_answer("Question?", ctx, on_token=events.append)
    assert events == []


def test_openai_sse_protocol_parser_yields_incremental_content(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"first "}}]}'
            yield 'data: {"choices":[{"delta":{"content":"second"}}]}'
            yield 'data: [DONE]'
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, method, url, json, headers):
            assert method == "POST" and json["stream"] is True
            return Response()
    monkeypatch.setattr("rag.generation.llm_client.httpx.Client", Client)
    client = OpenAILLMClient(api_key="test-only", model="fixture")
    assert client.supports_streaming is True
    assert list(client.generate_stream("system", "question")) == ["first ", "second"]
