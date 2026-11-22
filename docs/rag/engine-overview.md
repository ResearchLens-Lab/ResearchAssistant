# Research Engine Architecture

The `rag/` module implements the deterministic evidence retrieval and synthesis engine for ResearchLens. It ingests academic research papers, normalizes section and page structures, chunks text with semantic boundaries, and retrieves relevant passages to produce evidence-grounded answers with inline citations.

---

## Module Layout

```text
rag/
├── config/             # Settings, model configuration, chunking parameters
├── ingestion/          # Document loaders (PDF, TXT), normalization
├── chunking/           # Section-aware chunking and locator metadata
├── embeddings/         # Base embedder interfaces and optional providers
├── vectorstore/        # Optional vector storage collection management
├── retrieval/          # Lexical search, filter builders, ranking
├── independent/        # Deterministic FTS5 BM25 + TF-IDF engine
├── context/            # Context window budgeting and balance
├── generation/         # Answer composition and formatting templates
├── citations/          # Citation provenance tracking and formatting
├── pipelines/          # IngestionPipeline and QueryPipeline orchestrators
├── evaluation/         # Retrieval benchmark datasets and evaluators
├── training/           # Scikit-learn feature extractors and metric utilities
└── tests/              # Pytest test suites
```

---

## Lexical Indexing and Maintenance

The default engine maintains full-text indexes using SQLite FTS5 in WAL mode. Document reindexing can be inspected with a dry run before applying changes:

```bash
python scripts/reindex_documents.py --document-id <document-id> --dry-run
python scripts/reindex_documents.py --document-id <document-id> --apply
```

---

## Configuration

Configuration is managed via `rag/config/settings.py` and can be configured with environment variables or a `.env` file:

```env
RAG_ENGINE_MODE=independent
RAG_ANSWER_MODE=INDEPENDENT
LLM_PROVIDER=none
EMBEDDING_PROVIDER=none
```
