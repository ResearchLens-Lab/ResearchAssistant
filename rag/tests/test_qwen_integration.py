import json
import pytest

import httpx

from rag.config.settings import settings
from rag.generation import llm_client
from rag.generation.llm_client import OllamaLLMClient
from rag.pipelines import query_pipeline
from rag.research.orchestrator import QueryPlanner


def test_ollama_chat_disables_thinking_and_returns_content_only(monkeypatch):
    seen = {}

    def respond(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {
            "content": "### Definition\nAn algorithm is a finite sequence of steps.",
            "thinking": "private reasoning that must never be shown",
        }})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(llm_client, "_OLLAMA_HTTP", client)
    monkeypatch.setattr(settings, "ollama_model", "qwen3.5:0.8b")
    result = OllamaLLMClient().generate("system", "question")
    assert seen["model"] == "qwen3.5:0.8b"
    assert seen["think"] is False
    assert seen["stream"] is False
    assert seen["options"]["num_ctx"] == 4096
    assert seen["keep_alive"] == "10m"
    assert "thinking" not in result
    assert result.startswith("### Definition")
    client.close()


def test_ollama_streams_only_final_content_and_never_thinking(monkeypatch):
    def respond(request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, content=(
            b'{"message":{"content":"Grounded ","thinking":"private"},"done":false}\n'
            b'{"message":{"content":"answer [S1]","thinking":"private"},"done":true}\n'
        ))

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(llm_client, "_OLLAMA_HTTP", client)
    model = OllamaLLMClient()
    assert model.supports_streaming is True
    assert list(model.generate_stream("system", "question")) == ["Grounded ", "answer [S1]"]
    client.close()


def test_ollama_status_distinguishes_missing_loaded_and_active_model(monkeypatch):
    responses = {
        "/api/tags": {"models": [{"name": "qwen3.5:0.8b"}]},
        "/api/ps": {"models": [{"name": "qwen3.5:0.8b"}]},
    }

    class FakeResponse:
        status_code = 200
        def json(self): return responses[self.path]

    class FakeClient:
        def __init__(self, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def get(self, url):
            response = FakeResponse()
            response.path = url.rsplit("/", 2)[-2:]
            response.path = "/" + "/".join(response.path)
            return response

    monkeypatch.setattr(httpx, "Client", FakeClient)
    status = OllamaLLMClient().status()
    assert status["state"] == "ready_loaded"
    assert status["runtime_available"] and status["model_installed"] and status["model_loaded"]
    assert "api_key" not in status


@pytest.mark.skip(reason="Legacy Chroma/Fastembed/Ollama generation path superseded by offline lexical research engine")
def test_general_knowledge_is_separate_and_has_no_document_citations(monkeypatch):
    class EmptyRetriever:
        def retrieve(self, _request, *args, **kwargs):
            return []

    class FakeOllama:
        model = "qwen3.5:0.8b"

        def is_available(self):
            return True

        def generate(self, *_args, **_kwargs):
            return "### Explanation\nAn algorithm is a finite procedure for solving a problem."

    monkeypatch.setattr(query_pipeline, "OllamaLLMClient", FakeOllama)
    result = query_pipeline.QueryPipeline(retriever=EmptyRetriever()).answer_question(
        "What is an algorithm?", user_id="test_user", paper_ids=["p1"], answer_mode="DOCUMENTS_GENERAL"
    )
    assert "not located in selected documents" in result.answer.lower() or "not found in your selected documents" in result.answer.lower()
    assert "### General knowledge (not from your documents)" in result.answer
    assert result.sources == []
    assert result.metadata["answer_mode"] == "general_knowledge"


def test_documents_only_abstains_without_calling_ollama(monkeypatch):
    class EmptyRetriever:
        def retrieve(self, _request, *args, **kwargs):
            return []

    def should_not_load():
        raise AssertionError("Documents-only mode must not invoke local generation")

    monkeypatch.setattr(query_pipeline, "OllamaLLMClient", should_not_load)
    result = query_pipeline.QueryPipeline(retriever=EmptyRetriever()).answer_question(
        "What is missing?", user_id="test_user", paper_ids=["p1"], answer_mode="DOCUMENTS_ONLY"
    )
    assert "not located in selected documents" in result.answer.lower() or "not found in your selected documents" in result.answer.lower()
    assert result.sources == []


@pytest.mark.skip(reason="Legacy Chroma/Fastembed/Ollama generation path superseded by offline lexical research engine")
def test_algorithm_definition_uses_verified_passage_without_model(monkeypatch):
    from rag.retrieval.query import RetrievedSource

    passage = ("An algorithm is any well-defined computational procedure that takes some value, "
               "or set of values, as input and produces some value, or set of values, as output. "
               "It is thus a sequence of computational steps that transform the input into the output.")

    class Retriever:
        def retrieve(self, _request, *args, **kwargs):
            return [RetrievedSource(source_id="S1", chunk_id="definition", paper_id="clrs",
                document_id="clrs-doc", page_start=20, page_end=20, section="1.1 Algorithms",
                text=passage, score=.99, filename="Introduction to Algorithms.pdf")]

    def should_not_load():
        raise AssertionError("A complete source definition should not wait for CPU generation")

    monkeypatch.setattr(query_pipeline, "OllamaLLMClient", should_not_load)
    result = query_pipeline.QueryPipeline(retriever=Retriever()).answer_question(
        "What is an algorithm? Explain with a practical example.", user_id="test_user", paper_ids=["clrs"]
    )
    assert "well-defined computational procedure" in result.answer
    assert "[S1]" in result.answer
    assert "Illustrative example (not from your documents)" in result.answer
    assert result.sources[0].page_start == 20


def test_short_follow_up_resolves_to_the_immediately_previous_topic():
    context = (
        "user: Who is the author of this book?\nassistant: Thomas H. Cormen and others.\n"
        "user: What is an algorithm?\nassistant: An algorithm is a computational procedure."
    )
    plan = QueryPlanner().plan("Explain in more depth", retrieval_scope=context)
    assert plan.intent == "follow_up"
    assert "What is an algorithm?" in plan.resolved_question
    assert all("algorithm" in query.casefold() for query in plan.search_queries)
    assert all("author" not in query.casefold() for query in plan.search_queries)


def test_follow_up_reranking_demotes_reference_pages():
    from rag.retrieval.query import RetrievedSource
    from rag.retrieval.reranker import IntentAwareReranker

    reference = RetrievedSource(source_id="S1", chunk_id="refs", paper_id="clrs",
        document_id="clrs-doc", page_start=1300, section="References",
        text="Algorithm Analysis references, connected components, exponential search tree.", score=.9)
    definition = RetrievedSource(source_id="S2", chunk_id="chapter", paper_id="clrs",
        document_id="clrs-doc", page_start=20, section="1.1 Algorithms",
        text="An algorithm is a well-defined computational procedure that transforms input into output.", score=.65)
    ranked = IntentAwareReranker().rerank(
        "What is an algorithm? Explain in more depth", [reference, definition],
        top_k=2, intent="follow_up",
    )
    assert ranked[0].chunk_id == "chapter"
