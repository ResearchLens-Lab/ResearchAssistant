# ResearchLens RAG Engine

**Technical Lead & Author**: Gorav Gumber (Project Lead & RAG/AI Lead)

## 📌 Overview
The `rag/` module is the core evidence-grounded AI engine of the ResearchLens platform. It is designed to ingest academic research papers, normalize their section and page structure, chunk them with semantic awareness, generate vector embeddings, and retrieve relevant passages from ChromaDB to answer research questions with strict citation provenance.

---

## 🗂 Folder Structure

```
rag/
├── config/             # Settings, model configs, retrieval and chunking configs
├── ingestion/          # Document loaders (PDF/TXT), normalizer, metadata mapper
├── chunking/           # Section-aware chunking strategy, chunk metadata container
├── embeddings/         # Base embedder, DeterministicMockEmbedder, OpenAIEmbedder, batching
├── vectorstore/        # ChromaDB client factory, collection manager, vector repository
├── retrieval/          # Query models, filter builder, ranking, reranker, retriever
├── context/            # Context builder, token limits manager, multi-paper balancer
├── generation/         # Academic prompt templates, LLM clients, response parser, generator
├── citations/          # Provenance tracking, citation mapper, RAGResult formatting
├── pipelines/          # IngestionPipeline & QueryPipeline high-level orchestrators
├── evaluation/         # Benchmark dataset, metrics (Hit@K, Grounding, Citations), evaluator
└── tests/              # Full unit and end-to-end test suite
```

Embedding collections are separated by provider, model, version, and dimension.
After changing the embedding model, first review the selection with a dry run,
then explicitly apply it to a selected document or (only when intended) all
eligible documents. The previous collection remains available for rollback:

```bash
python scripts/reindex_documents.py --document-id <document-id> --dry-run
python scripts/reindex_documents.py --document-id <document-id> --apply
```

`--all` also requires a dry-run review before `--apply`. Interrupted processing
rows are excluded by default; use `--resume-stale` only to include rows whose
heartbeat is older than the configured stale interval.

---

## ⚙️ Configuration

All configuration is managed via `rag/config/settings.py` and can be overridden using environment variables or a `.env` file:

```env
# Local embeddings (no Gemini API key or quota required for ingestion/search)
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSION=384
EMBEDDING_BATCH_SIZE=64
FASTEMBED_CACHE_DIR=.model_cache

# Optional Gemini generation
GEMINI_API_KEY=your-key

LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.8-flash

# ChromaDB Settings
CHROMA_PERSIST_DIR=.chroma
CHROMA_COLLECTION_NAME=research_papers

# Chunking & Retrieval
CHUNK_SIZE=500
CHUNK_OVERLAP=80
RETRIEVAL_TOP_K=5
```

---

## 🚀 Running Sample CLI Scripts

### 1. Ingest a Research Paper
```bash
python scripts/ingest_sample.py --file-path scripts/sample_data/sample_paper.txt --paper-id paper_sample_01
```

### 2. Query Grounded Answers
```bash
python scripts/query_rag.py --question "What is the primary contribution of the Transformer?" --paper-ids paper_sample_01
```

### 3. Summarize an Indexed Paper
```bash
python scripts/summarize_paper.py --paper-id paper_sample_01
```

### 4. Compare Multiple Papers
```bash
python scripts/compare_papers.py --paper-ids paper_sample_01 paper_sample_02
```

### 5. Run Evaluation Benchmarks
```bash
python scripts/evaluate_rag.py
```

---

## 🧪 Running Tests

Execute the complete test suite:
```bash
PYTHONPATH=. pytest rag/tests/ -v
```

---

## 🔗 Backend Integration Contract

Abhay's FastAPI backend integrates with RAG cleanly via `backend/app/integrations/rag_client.py`:

```python
from backend.app.integrations.rag_client import rag_client

# Ingest
result = rag_client.ingest_document(file_path="paper.pdf", paper_id="paper_01")

# Query
response = rag_client.ask_question(question="Explain the methodology.", paper_ids=["paper_01"])
```
