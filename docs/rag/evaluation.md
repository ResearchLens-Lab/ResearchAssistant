# RAG Evaluation Framework

**Path**: `rag/evaluation/`

## Purpose
Provides practical, lightweight evaluation metrics to benchmark retrieval accuracy and generation quality without heavy external evaluation dependencies.

## Key Metrics

1. **Hit@K**: Measures whether the retrieved top-K chunks contain the expected section or target evidence keywords (1.0 = match, 0.0 = miss).
2. **Source Relevance**: Fraction of golden benchmark keywords captured in the retrieved context.
3. **Answer Grounding**: Semantic overlap and factual consistency between generated answer sentences and retrieved source passages.
4. **Citation Correctness**: Proportion of inline citation tags (`[S1]`, `[S2]`) that map to valid, retrieved source chunks (100% = no hallucinated citations).

## Key Components
- `datasets/sample_questions.json`: Golden test cases with questions, paper IDs, expected sections, and answer facts.
- `metrics.py`: Computes individual metrics and `EvaluationSummary`.
- `retrieval_eval.py`: Evaluates retrieval stage against ground truth.
- `generation_eval.py`: Evaluates generation grounding and citation faithfulness.
- `evaluator.py`: Unified `RAGEvaluator` runner generating aggregate metrics.

## Running Evaluation
```bash
python scripts/evaluate_rag.py
```
