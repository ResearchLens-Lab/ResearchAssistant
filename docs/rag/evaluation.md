# RAG Evaluation Framework

The evaluator runs deterministic retrieval and answer-quality checks using source-derived fixture labels. These metrics are proxies, not human semantic judgments.

## Metrics and limits

- Hit@K: 1 if a retrieved top-K passage contains an expected section or any expected keyword; otherwise 0.
- Source relevance: fraction of expected keywords found across retrieved text.
- MRR: reciprocal rank of the first passage containing an expected keyword.
- Source coverage: fraction of labeled required source papers present in retrieved passages.
- Answer grounding: lexical overlap/expected-point match; not entailment.
- Citation identity: inline source IDs that resolve to returned sources; does not check sentence-level support.
- Expected-fact coverage: expected answer-point matches by lexical checks.
- Claim-support heuristic: per-claim lexical/numeric overlap; not semantic entailment.
- Numerical extraction: presence of labeled numeric literals in the answer.
- Locator validity: presence of document/chunk/excerpt plus a page or locator field, not correctness against an original PDF.
- Missing-evidence and contradiction handling: deterministic checks against explicit labels.
- Latency: local mock wall time. Model calls estimate generation plus correction calls; no token usage is available in mock mode.
- Retrieval duplicate rate is not currently measured.

## Reproduce

```powershell
.venv\Scripts\python.exe scripts\evaluate_rag.py --report-path docs/rag/reports/phase3_1_mock.json
```

The command indexes the same five fixtures into a temporary vector store and runs direct single-query and bounded orchestration paths at the same top-k, embedding mock, and generation mock. It writes both per-question summaries and category aggregates to the report.

## Latest execution

54 labeled questions were executed at top-k 4. The fixture corpus has five documents. Many of the added cases are alternate phrasings of 22 source-fact anchors; 54 should not be interpreted as 54 independent underlying facts. Provider mode: deterministic mock.

| Metric | Direct | Orchestration |
|---|---:|---:|
| Hit@4 | 98.2% | 98.2% |
| Source relevance | 96.5% | 96.5% |
| MRR | 0.940 | 0.940 |
| Labeled source coverage | 100.0% | 100.0% |
| Answer grounding heuristic | 82.4% | 82.5% |
| Citation identity | 100.0% | 100.0% |
| Mean end-to-end latency | 0.013s | 0.017s |

Orchestration ties direct retrieval on retrieval and citation metrics, shifts grounding by +0.1 percentage points, and adds 0.004 seconds of local mock latency. Per-category scores are in the JSON report; most categories are supported by very small samples.

For the orchestration path, claim-support heuristic was 75.4% across 53 answerable outputs; expected-fact coverage was 76.7% (n=53); numerical extraction was 96.3% (n=27); locator-field completeness was 100% (n=54); missing-evidence handling was 100% (n=1); contradiction handling was 100% (n=1); invalid-citation rate was 0% (n=53). Mean retrieval rounds and estimated model calls were 1.07 and 1.96. These are local fixture results and do not establish semantic correctness or real-provider performance. The fixture lacks independently adjudicated exact PDF-page labels.
