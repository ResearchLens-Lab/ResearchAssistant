# Retrieval and Ranking Design

## Baseline verified in code

The default mode is `independent`. Uploads select `IndependentIngestionPipeline`, which writes owner-scoped text chunks to a local SQLite FTS5 index. Queries use `IndependentRetriever` with explicit `owner_id` and optional paper/document/section filters, deterministic term expansion and BM25 ordering. `IndependentResearchEngine` classifies intent with rules and composes a local evidence-only response. Comparisons issue a bounded retrieval pass for each selected document. This is the baseline to preserve.

The legacy pipeline remains available behind configuration and can use Chroma/vector, embeddings, optional reranking, research planning and optional providers. Its existence does not imply it is the default or that its network/model settings are safe for a local-only claim.

## Candidate pipeline

1. Validate authenticated owner and explicit scope; no owner means fail closed.
2. Parse intent and requested response format deterministically unless a sufficiently reviewed supervised classifier is explicitly approved.
3. Retrieve candidates from FTS5 BM25, exact phrase, title/metadata and section paths. Optional vector candidates must carry the same owner/document/version constraints.
4. Deduplicate by immutable versioned chunk identity and suppress overlapping passages without deleting bibliography/header information globally.
5. Apply transparent features: exact phrase, query-term coverage, title/section match, passage completeness, duplicate/header penalty and extraction quality. Preserve feature contributions for diagnostics.
6. Use RRF only when combining independent ranked lists and evaluate it against the current BM25 baseline. Do not feed raw scores across incompatible scales.
7. For comparison, retrieve per selected document with equal candidate budgets; show selected documents with no qualifying passage as missing evidence.
8. Expand a selected sentence to its parent paragraph/table row only when the stored structure reliably identifies that parent.

## Relevance, threshold and abstention

Keyword overlap is candidate relevance, not entailment. An answer composer may quote/extract only retrieved passages, but must label checks as lexical/extractive. Insufficient evidence means no relevant passage matched the explicit scope/focus under the current retriever; it is not proof the document has no such information. Metadata queries can intentionally search front matter and references.

## Learning gate

Train a reranker only from approved passage-relevance examples with original document provenance and explicit permission. Split by document/project, freeze the manifest, compare baseline and candidate on held-out documents, report Precision@K, Recall@K, MRR, nDCG@K, duplicate rate and per-document coverage. No model is active merely because the registry can load one.

## Current limitations

- Default independent path is lexical FTS5; no pretrained embeddings are required or used there.
- The existing legacy reranker and vector path are a different configured path.
- Current FTS5 candidate expansion has bounded candidates and deterministic filters but no full rank-fusion pipeline.
- No authorized human relevance judgments were found in the inspected evaluation artifacts; synthetic fixture labels cannot justify deploying a better ranker.
