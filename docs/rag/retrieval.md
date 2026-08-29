# Vector Retrieval, Filtering & Ranking

**Path**: `rag/retrieval/`

## Purpose
Executes semantic vector searches over ChromaDB, applies metadata filters (single or multi-paper IDs, section constraints), normalizes similarity scores, and prepares candidates for context construction.

## Key Components

### 1. `query.py`
- `QueryRequest`: Encapsulates question text, target paper IDs, optional `QueryFilters`, `top_k`, and `min_score`.
- `RetrievedSource`: Structured representation of a retrieved passage with `source_id` (e.g. `S1`, `S2`), `chunk_id`, `paper_id`, `document_id`, `page_start`, `page_end`, `section`, `text`, `score`, `title`.

### 2. `filters.py`
`FilterBuilder`: Translates queries into ChromaDB `$and` / `$in` / `$eq` where-clauses for fast indexed retrieval.

### 3. `ranking.py`
`ResultRanker`: Normalizes cosine distance to similarity score `[0.0, 1.0]` and prunes low-relevance results.

### 4. `reranker.py`
- `BaseReranker`: Extensible abstraction for future neural cross-encoders.
- `IdentityReranker`: Active pass-through reranker preserving initial vector ranking.

### 5. `retriever.py`
`ResearchRetriever`: High-level orchestrator executing query embedding, filtered Chroma query, ranking, reranking, and source labeling.
