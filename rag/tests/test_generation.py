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


def test_gemini_generation_and_streaming_use_official_sdk_client():
    from types import SimpleNamespace
    from rag.generation.llm_client import GeminiLLMClient

    class Models:
        def generate_content(self, **kwargs):
            assert kwargs["model"] == "gemini-3.8-flash"
            assert kwargs["contents"] == "question"
            return SimpleNamespace(text="grounded answer [S1]")
        def generate_content_stream(self, **kwargs):
            return [SimpleNamespace(text="grounded "), SimpleNamespace(text="answer [S1]")]

    client = GeminiLLMClient(api_key="test-key", client=SimpleNamespace(models=Models()))
    assert client.generate("system instructions", "question") == "grounded answer [S1]"
    assert list(client.generate_stream("system instructions", "question")) == ["grounded ", "answer [S1]"]


def test_gemini_generation_fails_clearly_without_key(monkeypatch):
    from rag.config.settings import settings
    from rag.generation.llm_client import GeminiLLMClient

    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(ValueError, match="Set GEMINI_API_KEY"):
        GeminiLLMClient().generate("instructions", "question")


@pytest.mark.skip(reason="Legacy Chroma/Fastembed/Ollama generation path superseded by offline lexical research engine")
def test_query_pipeline_defers_unsupported_generation_until_answer_is_needed(monkeypatch):
    from types import SimpleNamespace
    from rag.config.settings import settings
    from rag.pipelines.query_pipeline import QueryPipeline
    from rag.retrieval.query import RetrievedSource

    monkeypatch.setattr(settings, "llm_provider", "local")

    class Planner:
        def plan(self, *_args):
            return SimpleNamespace(intent="direct", search_queries=["known fact"], max_retrieval_rounds=1)

    class Retriever:
        def retrieve(self, _request, *args, **kwargs):
            return [RetrievedSource(source_id="S1", chunk_id="chunk", paper_id="paper",
                                    document_id="doc", page_start=1, page_end=1,
                                    text="The known fact is 42.")]

    class Sufficient:
        def assess(self, *_args):
            return SimpleNamespace(status="adequate", missing_terms=[], model_dump=lambda: {})

    # Initializing the pipeline is safe for local ingestion/retrieval.
    pipeline = QueryPipeline(retriever=Retriever(), planner=Planner(), sufficiency_checker=Sufficient())
    result = pipeline.answer_question("What is the known fact?", user_id="test_user")
    assert result.metadata["answer_mode"] == "evidence_only"
    assert result.metadata["generation_reason"] == "direct_factual_lookup"
    assert result.metadata["model_calls"] == 0
    assert "The known fact is 42." in result.answer
    assert result.sources[0].page_start == 1


def test_gemini_generator_is_initialized_only_when_requested_without_live_api(monkeypatch):
    from rag.config.settings import settings
    from rag.generation.llm_client import LLMClientFactory
    from rag.pipelines.query_pipeline import QueryPipeline

    sentinel = object()
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(LLMClientFactory, "get_client", lambda **_kwargs: sentinel)
    pipeline = QueryPipeline()
    assert pipeline._generator is None
    assert pipeline.generator.llm_client is sentinel
