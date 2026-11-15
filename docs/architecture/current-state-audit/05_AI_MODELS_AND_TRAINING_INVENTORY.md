# AI Models and Training Inventory

**Document Version**: 1.0  
**Last Updated**: November 8, 2026

---

## Executive Finding

**CRITICAL**: ResearchLens currently uses **100% pretrained third-party models**. No custom training, no fine-tuning, no independent AI components have been developed.

---

## Table of Contents

1. [Complete Model Inventory](#complete-model-inventory)
2. [Pretrained vs Custom Analysis](#pretrained-vs-custom-analysis)
3. [Embedding Models](#embedding-models)
4. [Generation Models](#generation-models)
5. [Rule-Based Components](#rule-based-components)
6. [Training Infrastructure Assessment](#training-infrastructure-assessment)
7. [Path to Independent AI](#path-to-independent-ai)

---

## Complete Model Inventory

### Summary Table

| Component | Model Name | Type | Provider | Training Status | Local/API | Purpose |
|-----------|-----------|------|----------|----------------|-----------|---------|
| **Embeddings (Default)** | BAAI/bge-small-en-v1.5 | Pretrained Bi-Encoder | BAAI (HuggingFace) | ❌ No Custom Training | Local (CPU) | Document & query embeddings |
| **Embeddings (Optional)** | Gemini Embeddings | Pretrained | Google | ❌ No Custom Training | API | Alternative embeddings |
| **Embeddings (Optional)** | OpenAI text-embedding-3-small | Pretrained | OpenAI | ❌ No Custom Training | API | Alternative embeddings |
| **Generation (Default)** | Qwen 3.5:0.8b | Pretrained LLM | Alibaba (via Ollama) | ❌ No Custom Training | Local (CPU) | Answer generation |
| **Generation (Optional)** | Gemini Flash | Pretrained LLM | Google | ❌ No Custom Training | API | Alternative generation |
| **Generation (Optional)** | OpenAI GPT | Pretrained LLM | OpenAI | ❌ No Custom Training | API | Alternative generation |
| **Query Classification** | None | N/A | N/A | ❌ Not Implemented | N/A | Intent detection |
| **Entity Recognition** | None | N/A | N/A | ❌ Not Implemented | N/A | Entity extraction |
| **Relation Extraction** | None | N/A | N/A | ❌ Not Implemented | N/A | Knowledge graph |
| **Reranker** | IntentAwareReranker | Rule-based | Custom | ✅ Deterministic Algorithm | Local | Result reordering |
| **Section Detector** | Regex Patterns | Rule-based | Custom | ✅ Deterministic Algorithm | Local | Academic section detection |
| **Chunker** | Token-based Splitter | Rule-based | Custom | ✅ Deterministic Algorithm | Local | Text segmentation |

**Evidence**: Code inspection of `rag/embeddings/`, `rag/generation/`, `rag/config/settings.py`

---

## Pretrained vs Custom Analysis

### Current Architecture: 100% Pretrained Models

**Embedding Generation**:
- ❌ No custom embedding model training
- ❌ No domain-specific fine-tuning
- ❌ No academic paper corpus used for training
- ✅ Uses pretrained BAAI BGE model unchanged

**Answer Generation**:
- ❌ No custom LLM training
- ❌ No fine-tuning on research Q&A pairs
- ❌ No instruction tuning
- ✅ Uses pretrained Qwen 3.5 unchanged

**Retrieval & Ranking**:
- ❌ No learned passage ranker
- ❌ No query-document relevance model
- ❌ No cross-encoder reranker
- ✅ Uses cosine similarity + simple heuristics

**Entity & Relation Models**:
- ❌ No NER model (named entity recognition)
- ❌ No relation extraction model
- ❌ No coreference resolution
- ❌ No claim detection model

### What IS Custom-Built

**Deterministic Components** (not ML models):
1. **Section-Aware Chunker**: Token-based text splitting with section boundaries
2. **Metadata Tracker**: Chunk ID generation, page tracking
3. **Citation Mapper**: Links LLM output citations to source chunks
4. **Intent Reranker**: Simple rule-based reordering (not learned)
5. **Context Assembler**: Token budget enforcement, passage formatting

**Evidence**: These are algorithmic components, not trained models

---

## Embedding Models

### 1. BAAI/bge-small-en-v1.5 (Default)

**Full Name**: Beijing Academy of Artificial Intelligence - BGE (BAAI General Embedding) Small English v1.5

**Model Card**: https://huggingface.co/BAAI/bge-small-en-v1.5

**Architecture**: BERT-based bi-encoder

**Parameters**: ~33 million

**Training Data** (from BAAI):
- C-Pack: Large-scale Chinese-English corpus
- MS MARCO: Web search corpus
- NLI datasets: SNLI, MultiNLI
- Wikipedia: General knowledge

**Training Objective**: Contrastive learning (cosine similarity maximization for relevant pairs)

**Dimensions**: 384

**Max Sequence Length**: 512 tokens

**Training Status**: ❌ **Pretrained by BAAI, no ResearchLens-specific training**

**Distribution**: Downloaded from HuggingFace via FastEmbed

**License**: MIT (permissive, allows commercial use)

**Performance** (BAAI benchmarks):
- MTEB Average: 55.0
- Retrieval (NDCG@10): 50.3
- Speed: Fast (ONNX optimized)

**ResearchLens Usage**:
- Embed document chunks (batch size: 128)
- Embed user queries (single)
- Store vectors in ChromaDB

**Limitations**:
- Not trained on academic papers specifically
- General-purpose, may miss domain terminology
- 512-token limit (truncation risk)

**Evidence**: `rag/embeddings/embedder.py` (class `FastEmbedder`), `rag/config/settings.py`

**File**: `rag/embeddings/embedder.py` (lines 99-228)

### 2. Gemini Embeddings (Optional)

**Provider**: Google (via google-genai SDK)

**Model**: `models/text-embedding-004` (default)

**Dimensions**: Configurable (default 768)

**Training Status**: ❌ **Pretrained by Google, no custom training**

**Usage**: API-based (requires `GEMINI_API_KEY`)

**Cost**: Free tier + paid quota

**ResearchLens Integration**: Code exists, not default

**Evidence**: `rag/embeddings/embedder.py` (class `GeminiEmbedder`, line 291)

### 3. OpenAI Embeddings (Optional)

**Provider**: OpenAI

**Model**: `text-embedding-3-small` (assumed)

**Dimensions**: 1536

**Training Status**: ❌ **Pretrained by OpenAI, no custom training**

**Usage**: API-based (requires `OPENAI_API_KEY`)

**Cost**: $0.02 per 1M tokens (as of training data cutoff)

**ResearchLens Integration**: Code exists, not default

**Evidence**: `rag/embeddings/embedder.py` (class `OpenAIEmbedder`, line 230)

### Embedding Provider Selection

**Configuration**:
```env
EMBEDDING_PROVIDER=fastembed  # Options: fastembed, gemini, openai, mock
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSION=384
```

**Registry Pattern**: `rag/embeddings/model_registry.py` provides factory

**Evidence**: `rag/config/settings.py` (lines 28-36)

---

## Generation Models

### 1. Qwen 3.5:0.8b (Default)

**Full Name**: Qwen 3.5 (0.8 billion parameters)

**Provider**: Alibaba Cloud (via Ollama)

**Architecture**: Transformer decoder (similar to GPT)

**Parameters**: ~800 million

**Training Data** (from Alibaba):
- Web text (multilingual)
- Books, articles
- Code repositories
- Instruction-following pairs

**Training Status**: ❌ **Pretrained by Alibaba, no ResearchLens-specific training**

**Serving**: Ollama (local inference server)

**Deployment**:
```bash
# User must manually install
ollama pull qwen3.5:0.8b
```

**Model Size**: ~500 MB (quantized)

**Inference Speed** (CPU i5):
- Prompt processing: 2-5 sec
- Generation: 20-40 tokens/sec
- Total (512 tokens): 10-20 sec

**Max Context**: 8192 tokens (Qwen architecture)

**ResearchLens Context Usage**: ~3000 tokens (config limit)

**ResearchLens Integration**:
```python
# rag/generation/llm_client.py (OllamaLLMClient)
response = requests.post(
    f"{ollama_base_url}/api/generate",
    json={
        "model": "qwen3.5:0.8b",
        "prompt": full_prompt,
        "options": {"temperature": 0.1, "num_predict": 512}
    }
)
```

**Strengths**:
- Small size (runs on CPU)
- Fast inference
- No API costs

**Weaknesses**:
- Not specialized for academic research
- May struggle with complex reasoning
- No research-specific instruction tuning

**Evidence**: `rag/generation/llm_client.py` (lines 299-462), `rag/config/settings.py`

### 2. Gemini Flash (Optional)

**Full Name**: Gemini 1.5 Flash (assumed based on config "gemini-3.8-flash")

**Provider**: Google

**Architecture**: Google's proprietary multimodal LLM

**Training Status**: ❌ **Pretrained by Google, no custom training**

**Usage**: API-based (requires `GEMINI_API_KEY`)

**Context Window**: 1M tokens (Gemini 1.5)

**ResearchLens Integration**: Code exists, not default

**Evidence**: `rag/generation/llm_client.py` (class `GeminiLLMClient`, line 221)

### 3. OpenAI GPT (Optional)

**Provider**: OpenAI

**Model**: Configurable (likely GPT-4, GPT-3.5-turbo)

**Training Status**: ❌ **Pretrained by OpenAI, no custom training**

**Usage**: API-based (requires `OPENAI_API_KEY`)

**ResearchLens Integration**: Code exists, not tested

**Evidence**: `rag/generation/llm_client.py` (class `OpenAILLMClient`, line 129)

### LLM Provider Selection

**Configuration**:
```env
LLM_PROVIDER=ollama  # Options: ollama, gemini, openai, mock
LLM_MODEL=qwen3.5:0.8b
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=512
```

**Fallback Mode**: Extractive (returns top passage without LLM)

**Evidence**: `rag/config/settings.py` (lines 42-52)

---

## Rule-Based Components

### 1. Section-Aware Chunker

**Type**: Deterministic Algorithm

**Input**: Normalized document pages with section labels

**Algorithm**:
1. Iterate through pages in order
2. Split text into ~500-token windows
3. Never split across section boundaries
4. Overlap windows by 80 tokens
5. Track page_start, page_end for each chunk

**Training**: ❌ No training (rule-based)

**Configurability**: Token size, overlap adjustable

**Evidence**: `rag/chunking/chunker.py`

### 2. Intent-Aware Reranker

**Type**: Heuristic Rules

**Input**: Retrieved passages + query intent

**Rules**:
- **Comparison**: Ensure each paper has top representative
- **Q&A**: Rank by score only
- **Follow-up**: Prefer same section as previous

**Training**: ❌ No training (rule-based)

**Limitations**: No learned relevance model

**Evidence**: `rag/retrieval/reranker.py`

### 3. Section Detector

**Type**: Regex Pattern Matching

**Patterns**:
```python
{
    'abstract': r'^abstract\s*$',
    'introduction': r'^introduction\s*$',
    'methodology': r'^(methodology|methods)\s*$',
    'results': r'^results\s*$',
    'discussion': r'^discussion\s*$',
    'conclusion': r'^conclusion\s*$',
    'references': r'^references\s*$',
}
```

**Training**: ❌ No training (pattern-based)

**Limitations**: Fails on non-standard paper formats

**Evidence**: `rag/ingestion/normalizer.py`

### 4. Citation Parser

**Type**: Regex + String Matching

**Detects**: `[S1]`, `[S2]`, `[S3]` patterns in LLM output

**Maps**: Citation ID → Source metadata

**Training**: ❌ No training (pattern-based)

**Evidence**: `rag/generation/response_parser.py`

---

## Training Infrastructure Assessment

### Current Training Capabilities: NONE

**No Training Code**:
- ❌ No PyTorch training loops
- ❌ No TensorFlow training code
- ❌ No model fine-tuning scripts
- ❌ No hyperparameter tuning
- ❌ No model evaluation harnesses
- ❌ No model checkpointing

**No Training Data**:
- ❌ No labeled query-answer pairs
- ❌ No relevance judgments
- ❌ No human annotations
- ❌ No synthetic data generation
- ❌ No training corpus curation

**No Compute Resources**:
- ❌ No GPU utilization (CPU-only)
- ❌ No distributed training setup
- ❌ No cloud training integration
- ❌ No model registry

**Evidence**: Complete codebase inspection, no training directory or scripts found

### Evaluation Suite (Partial)

**Exists**: `rag/evaluation/evaluator.py`

**Metrics Implemented**:
- Hit@K (retrieval recall)
- Source relevance (manual labels)
- Citation correctness (exact match)
- Answer grounding (citation coverage)

**Limitations**:
- Small benchmark dataset (if any)
- No automated continuous evaluation
- No A/B testing framework

**Evidence**: `rag/evaluation/` directory, `scripts/evaluate_rag.py`

---

## Path to Independent AI

### What "Independent AI" Requires

To build ResearchLens without third-party pretrained models:

### Option 1: Train Custom Models (Realistic Scope)

#### 1.1 Custom Query-Passage Ranking Model

**Purpose**: Replace pretrained embeddings for retrieval

**Approach**: Train bi-encoder on academic query-passage pairs

**Training Data Needed**:
- 10,000+ (query, relevant_passage, irrelevant_passage) triples
- Labeled from academic papers

**Model Size**: 100M parameters (BERT-small scale)

**Training Hardware**: Single GPU (V100/A100), 2-3 days

**Feasibility**: ✅ **Achievable with labeled data collection**

#### 1.2 Custom Intent Classifier

**Purpose**: Classify query intent (comparison, Q&A, summarization)

**Approach**: Fine-tune small BERT on labeled queries

**Training Data Needed**:
- 1,000+ labeled queries with intent categories

**Model Size**: 30M parameters

**Training Hardware**: CPU or single GPU, hours

**Feasibility**: ✅ **Very Achievable**

#### 1.3 Custom Entity Recognition Model

**Purpose**: Extract research entities (methods, datasets, metrics)

**Approach**: Fine-tune BERT-NER on academic entity corpus

**Training Data Needed**:
- 5,000+ annotated paper excerpts with entity spans

**Model Size**: 110M parameters (BERT-base scale)

**Training Hardware**: Single GPU, 1-2 days

**Feasibility**: ✅ **Achievable with annotation effort**

#### 1.4 Custom Relation Extraction Model

**Purpose**: Detect relationships between entities

**Approach**: Train transformer classifier on (entity1, entity2, relation) triples

**Training Data Needed**:
- 10,000+ labeled entity-relation examples

**Model Size**: 110M parameters

**Training Hardware**: Single GPU, 2-3 days

**Feasibility**: ⚠️ **Moderate - requires significant annotation**

### Option 2: Deterministic Alternatives (No Training)

#### 2.1 BM25-Only Retrieval

**Replace**: BGE embeddings

**Use**: Pure lexical search (already exists as hybrid component)

**Pros**: No pretrained model needed

**Cons**: Lower quality, keyword-dependent

**Feasibility**: ✅ **Already Implemented**

#### 2.2 Template-Based Extraction

**Replace**: LLM generation

**Use**: Regex + pattern matching for structured data

**Pros**: Fully deterministic, fast

**Cons**: Brittle, limited to structured queries

**Feasibility**: ✅ **Achievable for specific use cases**

#### 2.3 Rule-Based Entity Extraction

**Replace**: ML NER

**Use**: Domain lexicons + regex patterns

**Pros**: No training needed

**Cons**: Low recall, maintenance burden

**Feasibility**: ⚠️ **Partial coverage only**

### Option 3: Not Realistic on Laptop

#### Foundation LLM Training

**Purpose**: Replace Qwen with custom LLM

**Training Data Needed**: 100B+ tokens

**Model Size**: 1B+ parameters

**Training Hardware**: Multi-GPU cluster, weeks-months

**Feasibility**: ❌ **Not Achievable on 8GB laptop**

#### Custom Embedding Model from Scratch

**Purpose**: Replace BGE with trained embedding model

**Training Data Needed**: Billions of text pairs

**Model Size**: 100M+ parameters

**Training Hardware**: Multi-GPU, weeks

**Feasibility**: ❌ **Not Achievable on laptop**

---

## Recommended Hybrid Strategy

### Phase 1: Minimize Pretrained Dependencies

1. **Keep**: FastEmbed BGE (best local option, permissive license)
2. **Keep**: Ollama Qwen (local, no API costs)
3. **Replace**: Gemini/OpenAI options → Remove API dependencies

**Rationale**: Local execution more important than custom training initially

### Phase 2: Train Specialized Components

1. **Train**: Intent classifier (1,000 examples, achievable)
2. **Train**: Entity NER (5,000 examples, moderate effort)
3. **Train**: Passage ranker (10,000 examples, significant effort)

**Rationale**: Smaller models with clear ROI, manageable training costs

### Phase 3: Advanced Custom Models

1. **Train**: Relation extraction (if knowledge graph prioritized)
2. **Train**: Custom cross-encoder reranker (improve retrieval quality)
3. **Evaluate**: Fine-tune small LLM (if sufficient Q&A pairs collected)

**Rationale**: Longer-term improvements, requires established data pipeline

### Phase 4: Full Independence (Long-Term)

1. **Research**: Feasibility of distillation (Qwen → smaller custom model)
2. **Evaluate**: Open-source alternatives (Mistral, Falcon) vs custom
3. **Consider**: Cloud training for foundation-scale models

**Rationale**: Only pursue if strong product-market fit justifies investment

---

## Training Data Collection Strategy

### Immediate Actions

1. **Log User Queries**: Store all questions asked (anonymized)
2. **Track Useful Sources**: Record which passages users cite
3. **Feedback Collection**: Add relevance thumbs up/down
4. **Conversation Analysis**: Identify successful vs failed answer patterns

### Active Labeling

1. **Intent Labeling**: Crowdsource or internal labeling of 1,000 queries
2. **Relevance Judgments**: Binary relevant/not for (query, passage) pairs
3. **Entity Annotation**: Use annotation tools (Prodigy, LabelStudio) for NER

### Synthetic Data Generation

1. **Question Generation**: Use Qwen to generate questions from passages
2. **Paraphrase Queries**: Augment labeled data with paraphrases
3. **Negative Mining**: Sample hard negatives for ranking training

**Evidence**: No data collection infrastructure currently exists

---

## Summary

### Current State

❌ **0 custom-trained models** in production  
❌ **0 training pipelines** exist  
❌ **0 labeled datasets** exist  
✅ **3 pretrained models** used (BGE, Qwen, optional Gemini)  
✅ **5 deterministic algorithms** implemented (chunking, parsing, citation)

### Path Forward

**Realistic Goal**: Hybrid system with custom specialized models

**Not Realistic**: Fully independent foundation models on laptop hardware

**First Steps**:
1. Implement user feedback collection
2. Build intent classifier training pipeline
3. Annotate 1,000 queries with intents
4. Train and deploy first custom model
5. Measure quality improvement

**Long-Term Vision**: Custom embeddings, rankers, entity models; leverage open-source LLMs

---

**Next Document**: [07_KNOWLEDGE_GRAPH_AND_MEMORY_AUDIT.md](./07_KNOWLEDGE_GRAPH_AND_MEMORY_AUDIT.md)
