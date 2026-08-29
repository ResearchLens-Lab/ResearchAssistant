# ResearchLens (ResearchAssistant)

**Project Title**: AI Research Assistant Platform: A RAG-Based System for Research Paper Understanding, Citation Analysis and Research Trend Exploration  
**Organization**: ResearchLens-Lab  
**Repository**: ResearchAssistant  

---

## 👥 Monorepo Team Responsibilities

- **Gorav Gumber** → Project Lead + Technical Lead + RAG/AI Lead (`rag/`, `backend/app/integrations/rag_client.py`)
- **Abhay Kumar Singh** → Backend + Database Lead (`backend/`)
- **Himanshu Kumawat** → Frontend Lead (`frontend/`)
- **Harendra Godara** → Knowledge Graph + Research Intelligence Lead (`knowledge-graph/`)

---

## 🧠 Core RAG & AI Engine (Gorav's Area)

The RAG engine is isolated in `rag/` and provides:
1. **Document Ingestion & Normalization**: Extracts PDF/Text pages and detects standard academic sections (Abstract, Methodology, Results, Discussion, etc.).
2. **Section-Aware Chunking**: Chunks text while strictly tracking start/end page numbers and section boundaries.
3. **ChromaDB Vector Storage**: Indexes chunks with deterministic, stable IDs (`{paper_id}_c{chunk_index}_p{page_start}-{page_end}`).
4. **Grounded Retrieval & Context Assembly**: Supports single and multi-paper filtering, relevance scoring, and token budgeting.
5. **Grounded Generation & Citation Provenance**: Generates answers with verified inline citation tags (`[S1]`, `[S2]`) pointing to exact chunk IDs and page numbers.
6. **Paper Summarization & Multi-Paper Comparison**: Structured summaries and side-by-side comparative RAG.
7. **Evaluation Benchmark Suite**: Measures Hit@K, source relevance, answer grounding, and citation correctness.

---

## 🚀 Quick Start

### 1. Setup Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Run Tests
```bash
PYTHONPATH=. pytest rag/tests/ -v
```

### 3. Run Sample CLI Flows
```bash
# Ingest sample paper
python scripts/ingest_sample.py

# Query grounded answers
python scripts/query_rag.py --question "What is the main contribution of the paper?"

# Summarize paper
python scripts/summarize_paper.py --paper-id paper_sample_01

# Compare multiple papers
python scripts/compare_papers.py --paper-ids paper_sample_01 paper_sample_02

# Run RAG evaluation
python scripts/evaluate_rag.py
```

---

## 📚 Documentation
- [RAG System Overview](docs/rag/overview.md)
- [Ingestion & Normalization](docs/rag/ingestion.md)
- [Section-Aware Chunking](docs/rag/chunking.md)
- [Embeddings & Registry](docs/rag/embeddings.md)
- [Vector Retrieval](docs/rag/retrieval.md)
- [Grounded Generation](docs/rag/generation.md)
- [Citation Mapping](docs/rag/citations.md)
- [RAG Evaluation](docs/rag/evaluation.md)
- [Team Integration Boundaries](docs/architecture/integration-boundaries.md)
