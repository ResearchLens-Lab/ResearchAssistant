from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.skip(reason="Legacy Chroma/Fastembed/Ollama generation path superseded by offline lexical research engine")

from rag.config.settings import settings
from rag.generation.budgeted_client import BudgetedLLMClient
from rag.generation.generator import GroundedGenerator
from rag.generation.llm_client import BaseLLMClient
from rag.generation.local_state import LLMUsageBudgetExceeded, SQLiteLLMState
from rag.generation.provider_errors import LLMProviderError, classify_provider_error
from rag.context.context_builder import AssembledContext
from rag.research.claim_verifier import LLMClaimJudge
from rag.pipelines.query_pipeline import QueryPipeline
from rag.research.orchestrator import ResearchPlan
from rag.retrieval.query import RetrievedSource


class _FakeGeneratorClient(BaseLLMClient):
    supports_streaming = False
    api_key = "test-only"

    def __init__(self):
        self.calls = 0

    def generate(self, system_prompt, user_prompt, temperature=None, max_tokens=None):
        self.calls += 1
        return "The paper used an amber graph method for evaluation. [S1]"


class _FixedPlanner:
    def plan(self, question, *_args):
        return ResearchPlan(question=question, intent="summary", search_queries=[question], max_retrieval_rounds=1)


class _FixedSufficiency:
    def assess(self, *_args):
        return type("Assessment", (), {"status": "adequate", "missing_terms": [], "model_dump": lambda self: {"status": "adequate"}})()


class _MutableRetriever:
    def __init__(self, text):
        self.text = text

    def retrieve(self, _request):
        return [RetrievedSource(source_id="S1", chunk_id="chunk-one", paper_id="paper-one", document_id="doc-one",
            page_start=2, page_end=2, section="Results", text=self.text, score=.9,
            filename="known-paper.pdf", title="Known paper")]


def test_direct_fact_is_verbatim_cited_and_skips_generation(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    source = _MutableRetriever("The cobalt protocol reached 91 percent accuracy.")
    pipeline = QueryPipeline(retriever=source, planner=type("Planner", (), {"plan": lambda self, q, *_: ResearchPlan(
        question=q, intent="direct", search_queries=[q], max_retrieval_rounds=1)})(), sufficiency_checker=_FixedSufficiency())
    pipeline._generator = type("ForbiddenGenerator", (), {"generate_answer": lambda *_a, **_kw: pytest.fail("generation called")})()
    result = pipeline.answer_question("What accuracy was reported?", paper_ids=["paper-one"], user_id="user-one")
    assert result.metadata["answer_mode"] == "evidence_only"
    assert result.metadata["generation_reason"] == "direct_factual_lookup"
    assert result.metadata["model_calls"] == 0
    assert "91 percent accuracy" in result.answer
    assert result.sources[0].filename == "known-paper.pdf"
    assert result.sources[0].page_start == 2


def test_generated_response_cache_is_scoped_and_invalidated_by_source(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "gemini-test-model")
    monkeypatch.setattr(settings, "llm_daily_call_budget", 10)
    client = _FakeGeneratorClient()
    retriever = _MutableRetriever("The paper used an amber graph method for evaluation.")
    pipeline = QueryPipeline(retriever=retriever, planner=_FixedPlanner(), sufficiency_checker=_FixedSufficiency(),
                             generator=GroundedGenerator(client))
    args = {"question": "Summarize the method", "paper_ids": ["paper-one"], "user_id": "user-one"}
    first = pipeline.answer_question(**args)
    same = pipeline.answer_question(**args)
    other_user = pipeline.answer_question(**{**args, "user_id": "user-two"})
    retriever.text = "The paper used a violet graph method for evaluation."
    changed_source = pipeline.answer_question(**args)
    assert first.metadata["answer_mode"] == "generated"
    assert same.metadata["cache_hit"] is True and same.metadata["model_calls"] == 0
    assert other_user.metadata["cache_hit"] is False
    assert changed_source.metadata["cache_hit"] is False
    assert client.calls == 3
    assert all(result.sources[0].page_start == 2 for result in (first, same, other_user, changed_source))


def test_daily_budget_reservations_are_atomic_under_concurrency(tmp_path):
    state = SQLiteLLMState(tmp_path / "budget.sqlite3")

    def reserve(_):
        try:
            return state.reserve_call("gemini-test", 4)
        except LLMUsageBudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        reservations = list(pool.map(reserve, range(24)))
    successful = [value for value in reservations if value is not None]
    assert len(successful) == 4
    assert sorted(successful) == [1, 2, 3, 4]


def test_budgeted_client_applies_to_generation_and_stream(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "embedding_cache_path", str(tmp_path / "calls.sqlite3"))
    monkeypatch.setattr(settings, "llm_daily_call_budget", 2)

    class Client(BaseLLMClient):
        api_key = "test-only"
        supports_streaming = True
        def generate(self, *_args, **_kwargs): return "ok"
        def generate_stream(self, *_args, **_kwargs): yield "ok"

    client = BudgetedLLMClient(Client(), "gemini")
    assert client.generate("system", "user") == "ok"
    assert list(client.generate_stream("system", "user")) == ["ok"]
    generator = GroundedGenerator(client)
    context = AssembledContext(formatted_context="known evidence", selected_sources=[], total_sources=0, estimated_tokens=2)
    with pytest.raises(LLMUsageBudgetExceeded):
        generator.repair_answer("question", "draft", [], context)
    with pytest.raises(LLMUsageBudgetExceeded):
        LLMClaimJudge(client).judge("supported claim", [])


def test_missing_credentials_and_zero_budget_return_evidence_without_call(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_daily_call_budget", 0)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    client = _FakeGeneratorClient()
    client.api_key = ""
    retriever = _MutableRetriever("The paper used an amber graph method for evaluation.")
    pipeline = QueryPipeline(retriever=retriever, planner=_FixedPlanner(), sufficiency_checker=_FixedSufficiency(),
                             generator=GroundedGenerator(client))
    result = pipeline.answer_question("Summarize the method", paper_ids=["paper-one"], user_id="user-one")
    assert result.metadata["answer_mode"] == "evidence_fallback"
    assert result.metadata["generation_reason"] == "missing_credentials"
    assert result.metadata["model_calls"] == 0
    assert result.sources[0].filename == "known-paper.pdf"
    assert "page 2" in result.answer.lower()
    assert client.calls == 0


def test_quota_failure_is_reported_and_counted_as_one_real_attempt(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_daily_call_budget", 5)

    class QuotaClient(_FakeGeneratorClient):
        def generate(self, *_args, **_kwargs):
            self.calls += 1
            error = RuntimeError("quota exhausted")
            error.code = 429
            error.message = "RESOURCE_EXHAUSTED: quota exhausted"
            raise error

    client = QuotaClient()
    pipeline = QueryPipeline(retriever=_MutableRetriever("The paper used an amber graph method for evaluation."),
        planner=_FixedPlanner(), sufficiency_checker=_FixedSufficiency(), generator=GroundedGenerator(client))
    result = pipeline.answer_question("Summarize the method", paper_ids=["paper-one"], user_id="user-one")
    assert result.metadata["answer_mode"] == "evidence_fallback"
    assert result.metadata["generation_reason"] == "quota_exhausted"
    assert result.metadata["model_calls"] == 1
    assert client.calls == 1


def test_quota_errors_are_separate_from_transient_rate_limits():
    class ProviderFailure(Exception):
        def __init__(self, message):
            self.code = 429
            self.message = message
            super().__init__(message)

    assert classify_provider_error(ProviderFailure("RESOURCE_EXHAUSTED quota exceeded")).kind == "quota_exhausted"
    assert classify_provider_error(ProviderFailure("try again later")).kind == "rate_limited"


def test_gemini_sdk_usage_is_reported_as_measured(monkeypatch):
    from rag.generation.budgeted_client import start_call_tracking, stop_call_tracking
    from rag.generation.llm_client import GeminiLLMClient

    class Models:
        def generate_content(self, **_kwargs):
            return type("Response", (), {"text": "answer", "usage_metadata": type("Usage", (), {
                "prompt_token_count": 40, "candidates_token_count": 12, "total_token_count": 52})()})()
    client = GeminiLLMClient(api_key="test-only", model="gemini-test", client=type("Client", (), {"models": Models()})())
    monkeypatch.setattr(client, "_config", lambda *_args: None)
    token, calls = start_call_tracking()
    try:
        assert client.generate("system", "user") == "answer"
    finally:
        stop_call_tracking(token)
    assert calls[1] == [{"provider": "gemini", "model": "gemini-test", "measured": {
        "prompt_token_count": 40, "candidates_token_count": 12, "total_token_count": 52}}]

