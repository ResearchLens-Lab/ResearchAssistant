import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from rag.config.settings import settings
from rag.embeddings.model_registry import EmbeddingModelRegistry
from rag.generation.llm_client import OllamaLLMClient
from rag.independent.engine import IndependentResearchEngine
from rag.independent.evidence_validator import EvidenceValidator
from rag.independent.fact_extractor import FactExtractor
from rag.independent.intent_classifier import QuestionIntentClassifier
from rag.independent.retriever import IndependentRetriever, configured_lexical_collection_name
from rag.independent.models import QuestionIntent
from rag.pipelines.query_pipeline import QueryPipeline
from rag.retrieval.retriever import ResearchRetriever
from rag.retrieval.query import RetrievedSource
from backend.app.integrations.rag_client import RAGClient


_CORPUS_PATH = Path(__file__).parents[1] / "evaluation" / "phase1_fixture_corpus.json"
_CORPUS = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
PASSAGES = [(row["chunk_id"], row["paper_id"], row["document_id"], row["page"], row["section"], row["text"], row["title"], row["filename"]) for row in _CORPUS]


def make_index(path):
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE VIRTUAL TABLE lexical_chunks USING fts5(chunk_id UNINDEXED, owner_id UNINDEXED, collection_name UNINDEXED, paper_id UNINDEXED, document_id UNINDEXED, section UNINDEXED, page_start UNINDEXED, page_end UNINDEXED, title UNINDEXED, filename UNINDEXED, locator UNINDEXED, text, tokenize='unicode61')")
        for chunk, paper, document, page, section, text, title, filename in PASSAGES:
            db.execute("INSERT INTO lexical_chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (chunk, "test_owner", configured_lexical_collection_name(), paper, document, section, page, page, title, filename, f"Page {page}", text))
        db.commit()
    return path


def test_classifier_handles_intent_paraphrases_and_short_unknowns():
    classifier = QuestionIntentClassifier()
    cases = [
        ("Who wrote this book?", QuestionIntent.AUTHOR_LOOKUP),
        ("Identify the book's authors", QuestionIntent.AUTHOR_LOOKUP),
        ("Define an algorithm", QuestionIntent.DEFINITION),
        ("What does binary search mean?", QuestionIntent.EXPLANATION),
        ("How many records were used?", QuestionIntent.NUMERICAL_QUERY),
        ("When did the paper come out?", QuestionIntent.DATE_LOOKUP),
        ("Compare the reported accuracy", QuestionIntent.COMPARISON),
        ("Which datasets were evaluated?", QuestionIntent.DATASET_EXTRACTION),
        ("Show the supporting passages", QuestionIntent.EVIDENCE_LOOKUP),
        ("blorp flarn", QuestionIntent.UNKNOWN),
    ]
    for question, expected in cases:
        assert classifier.classify(question).intent == expected


def test_independent_answer_path_is_provider_free_and_citations_resolve(tmp_path, monkeypatch):
    index = make_index(tmp_path / "researchlens_lexical.sqlite3")
    monkeypatch.setattr(settings, "rag_engine_mode", "independent")
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path))
    monkeypatch.setattr(ResearchRetriever, "__init__", lambda *a, **k: (_ for _ in ()).throw(AssertionError("legacy retriever constructed")))
    monkeypatch.setattr(EmbeddingModelRegistry, "get_embedder", lambda *a, **k: (_ for _ in ()).throw(AssertionError("embedding provider called")))
    monkeypatch.setattr(OllamaLLMClient, "__init__", lambda *a, **k: (_ for _ in ()).throw(AssertionError("generation provider called")))
    before = hashlib.sha256(index.read_bytes()).hexdigest()
    pipeline = QueryPipeline()
    result = pipeline.answer_question("What is an algorithm?", user_id="test_owner", paper_ids=["p-book"], top_k=4)
    after = hashlib.sha256(index.read_bytes()).hexdigest()
    assert result.metadata["generation_provider"] == "none"
    assert result.metadata["embedding_provider"] == "none"
    assert "well-defined computational procedure" in result.answer
    assert result.sources and all(source.chunk_id in {row[0] for row in PASSAGES} for source in result.sources)
    assert before == after


def test_rag_client_startup_does_not_construct_legacy_embedder_in_independent_mode(monkeypatch):
    monkeypatch.setattr(settings, "rag_engine_mode", "independent")
    monkeypatch.setattr(EmbeddingModelRegistry, "get_embedder", lambda *a, **k: (_ for _ in ()).throw(AssertionError("embedding provider constructed")))
    monkeypatch.setattr(OllamaLLMClient, "__init__", lambda *a, **k: (_ for _ in ()).throw(AssertionError("generation provider constructed")))
    client = RAGClient(vector_repo=object())
    assert client._ingest_pipeline is None


def test_independent_ingestion_indexes_locally_without_pretrained_models(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "rag_engine_mode", "independent")
    monkeypatch.setattr(settings, "chroma_persist_dir", str(tmp_path))
    monkeypatch.setattr(EmbeddingModelRegistry, "get_embedder", lambda *a, **k: (_ for _ in ()).throw(AssertionError("embedding provider constructed")))
    monkeypatch.setattr(OllamaLLMClient, "__init__", lambda *a, **k: (_ for _ in ()).throw(AssertionError("generation provider constructed")))
    pipeline = QueryPipeline()
    client = RAGClient(query_pipeline=pipeline, vector_repo=object())
    ingested = client.ingest_text_content(
        "An algorithm is a precise procedure that accepts input and produces output.",
        paper_id="local-paper", metadata={"owner_id": "test_owner", "document_id": "local-document", "filename": "notes.txt"},
    )
    assert ingested["success"] is True and ingested["chunk_count"] > 0
    assert ingested["metadata"]["pretrained_embeddings_used"] is False
    counts = client.get_document_index_counts("local-document")
    assert counts["storage_mode"] == "sqlite_fts5_only"
    assert counts["fts_count"] == ingested["chunk_count"]
    result = pipeline.answer_question("Define an algorithm", user_id="test_owner", paper_ids=["local-paper"], top_k=4)
    assert "precise procedure" in result.answer


def test_author_lookup_requires_explicit_bibliographic_structure(tmp_path):
    index = make_index(tmp_path / "index.sqlite3")
    engine = IndependentResearchEngine(IndependentRetriever(index))
    result = engine.answer("Who authored this book?", paper_ids=["p-book"], document_ids=["d-book"])
    assert "Thomas H. Cormen" in result.answer
    assert "Clifford Stein" in result.answer
    assert "c-author" in {source.chunk_id for source in engine.retriever.retrieve(QuestionIntentClassifier().classify("who authored this book"), ["p-book"], ["d-book"])[0]}


def test_numeric_units_comparison_abstention_and_provenance(tmp_path):
    engine = IndependentResearchEngine(IndependentRetriever(make_index(tmp_path / "index.sqlite3")))
    numeric = engine.answer("What percentage accuracy was reported?", paper_ids=["p-a"])
    assert "83%" in numeric.answer
    comparison = engine.answer("Compare the accuracy reported in the two papers", paper_ids=["p-a", "p-b"], document_labels={"d-a": "Paper A", "d-b": "Paper B"})
    assert "Paper A" in comparison.answer and "Paper B" in comparison.answer
    assert "83%" in comparison.answer and "79%" in comparison.answer
    assert comparison.metadata["independent_research"]["evidence_decision"]["status"] == "CONFLICTING EVIDENCE"
    missing = engine.answer("What is the moon's chemical formula?", paper_ids=["p-book"])
    assert "Not found in your selected documents." in missing.answer
    for result in (numeric, comparison):
        source_ids = {source.source_id for source in result.sources}
        citations = __import__("re").findall(r"\[(S\d+)\]", result.answer)
        assert citations and set(citations) <= source_ids


def test_section_filter_and_conflict_values_are_exact(tmp_path):
    retriever = IndependentRetriever(make_index(tmp_path / "index.sqlite3"))
    analysis = QuestionIntentClassifier().classify("What is an algorithm?")
    sources, _ = retriever.retrieve(analysis, paper_ids=["p-book"], section_names=["Algorithms Informally"])
    assert [source.chunk_id for source in sources] == ["c-alg"]
    engine = IndependentResearchEngine(retriever)
    result = engine.answer("Compare accuracy reported by Paper A and Paper B", paper_ids=["p-a", "p-b"])
    conflicts = result.metadata["independent_research"]["evidence_decision"]["conflicts"]
    assert conflicts
    assert set(conflicts[0]["values"]) == {"83%", "79%"}


def test_names_are_not_authors_without_bibliographic_context_and_bad_citations_fail():
    source = RetrievedSource(
        source_id="S1", chunk_id="chunk-1", paper_id="paper-1", document_id="doc-1",
        page_start=4, page_end=4, section="Background",
        text="Thomas H. Cormen is mentioned in this historical discussion of algorithms.",
        score=1.0, title="A Study of Algorithms", filename="study.pdf",
    )
    facts = FactExtractor().extract([source], ["Thomas", "Cormen"])
    assert not [fact for fact in facts if fact.fact_type == "person_candidate"]
    title_page = RetrievedSource(
        source_id="S2", chunk_id="title-page", paper_id="book", document_id="book-copy",
        page_start=2, page_end=2, section="Introduction",
        text=("Introduction to Algorithms Third Edition Thomas H. Cormen Charles E. Leiserson "
              "Ronald L. Rivest Clifford Stein Introduction to Algorithms Third Edition The MIT Press"),
        score=1.0, title="Computer Science", filename="Cormen Introduction to Algorithms.pdf",
    )
    author_facts = [fact for fact in FactExtractor().extract([title_page]) if fact.fact_type == "person_candidate"]
    assert [fact.value for fact in author_facts] == [
        "Thomas H. Cormen", "Charles E. Leiserson", "Ronald L. Rivest", "Clifford Stein",
    ]
    assert all(fact.extraction_method == "edition_page_author_cluster" for fact in author_facts)
    decision = EvidenceValidator().validate("Unsupported factual claim [S9]", [source], [], ["factual"])
    assert decision.status == "INSUFFICIENT EVIDENCE"
    assert any("does not map" in item for item in decision.unsupported_claims)


