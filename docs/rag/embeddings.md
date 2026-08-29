# Embeddings & Model Registry

**Path**: `rag/embeddings/`

## Purpose
Provides an extensible embedding generation abstraction supporting local offline testing/CI and real cloud embedding providers.

## Key Components

### 1. `embedder.py`
- `BaseEmbedder`: Abstract interface defining `dimension`, `embed_documents(texts)`, and `embed_query(text)`.
- `DeterministicMockEmbedder`: Token-hashed dense vector generator producing L2-normalized 384-dimensional vectors. Allows 100% offline, deterministic testing with semantic keyword matching without API keys.
- `OpenAIEmbedder`: Production embedding client calling `text-embedding-3-small` (1536 dims) or configured model via HTTP API.

### 2. `batch_generator.py`
`BatchEmbeddingGenerator`: Slices large chunk collections into batches (`batch_size=32`) with progress logging.

### 3. `model_registry.py`
`EmbeddingModelRegistry`: Factory instantiating configured embedders based on `.env` or configuration parameters.
