# ResearchLens RAG Engine: System Overview

**Owner**: Gorav Gumber (Project Lead & RAG/AI Lead)

## 1. Executive Summary
The ResearchLens RAG Engine is a modular, evidence-grounded research assistant subsystem. It ingests academic research papers (PDFs, Markdown, text), extracts section and page-level structures, generates dense embeddings, indexes chunks in ChromaDB with deterministic IDs, and performs vector retrieval to synthesize citation-attributed answers, paper summaries, and multi-paper comparisons.

---

## 2. Complete RAG Pipeline Flow

```
Research Paper (PDF / TXT)
        ↓
Document Normalization (Page & Section Extraction)
        ↓
Section-Aware Chunking (Preserves Page Start/End, Section, Paper ID)
        ↓
Batch Embedding Generation (DeterministicMockEmbedder / OpenAIEmbedder)
        ↓
ChromaDB Vector Store (Deterministic Identifiers: paper_c0001_p1-2)
        ↓
User Question + Target Paper IDs
        ↓
Query Processing & Embedding
        ↓
Vector Retrieval with Metadata Filtering ($in paper_ids, sections)
        ↓
Relevance Ranking & Deduplication
        ↓
Context Construction with Token Budgeting & Source Tags ([S1], [S2])
        ↓
Grounded LLM Generation (MockGroundedLLM / OpenAILLM)
        ↓
Inline Citation Extraction & Verification
        ↓
Structured RAGResult (Answer + Verified Source Provenance)
```

---

## 3. Core Capabilities
1. **Single-Paper Research Q&A**: Answers deep methodological and empirical questions grounded in the paper.
2. **Paper Summarization**: Generates standardized 7-section summaries (Overview, Problem, Methodology, Datasets, Findings, Limitations, Conclusion).
3. **Multi-Paper Comparative RAG**: Compares two or more papers side-by-side with balanced context and explicit attribution.
4. **Source Provenance Guarantee**: Every citation points to real retrieved chunks with paper ID, document ID, start/end page numbers, section name, and exact snippet.
