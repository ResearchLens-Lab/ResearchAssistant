# Phase 3 Quality Validation — Retrieval Accuracy and Evidence Verification

**Date:** 2026-10-26  
**Scope:** Synthetic, isolated local RAG evaluation only. No Gemini, paid API, real corpus, shared database, or persistent project Chroma store was used.

## Verified findings

- `ResearchRetriever` obtains dense candidates, applies SQLite FTS5 lexical search within metadata scope, fuses rankings using reciprocal rank fusion, maps original chunk/page metadata, then invokes the configured reranker. The configured default is `IdentityReranker`, so it currently passes through the fused order. The implementation is in `rag/retrieval/retriever.py` and `rag/retrieval/reranker.py`.
- The query planner and sufficiency checker are deterministic heuristics in `rag/research/orchestrator.py`; query-term coverage is explicitly not semantic entailment. Citation validation checks source identity/scope/provenance, not entailment. `ClaimEvidenceVerifier` uses lexical overlap and a numeric heuristic; even a supported verdict is not proof of semantic entailment.
- **Confirmed false conflict:** the previous conflict detector treated different metric values from different papers as a conflict, without matching the measured subject or experimental setting. Atlas (91.2%) and Boreal (87.6%) are distinct systems and were evaluated on different dates/node counts. The old Phase 2.5 fixture mislabeled that pair as a conflict. The fixture now correctly calls it a different-system comparison, and the checker compares only explicit facts matching subject, metric, unit, and condition. This supports the tested phrasing patterns; it is intentionally conservative and does not claim broad natural-language contradiction understanding.
- **Confirmed numeric-verification defect:** the previous check could match `91` as a substring of `91.2`, and labeled a missing number contradicted whenever any unrelated number appeared in cited evidence. The verifier now matches whole numeric atoms, keeps identifiers such as `AX-17A` intact, and only labels a numeric mismatch contradicted when the same named metric has an explicit, different value. Different dates or unrelated measurements result in unsupported rather than contradictory. Citation identity, selected scope, filename/page provenance, and optional judge behavior remain intact.
- The local reranker was not changed. The three answerable Phase 3 retrieval questions already ranked their expected passage first; this tiny synthetic set does not establish generalization for a candidate reranker. No ranking threshold, fusion weight, chunk setting, or production retrieval order was tuned.
- Existing Phase 2.5 tests continue to cover the generated/evidence-only routing adapter, cache invalidation dimensions, atomic concurrent call-budget reservations, and isolated concurrent Chroma query/upsert/delete/retry. The historical `Error finding id` remains unreproduced; this phase makes no claim to fix it.

## Evaluation corpus and method

`rag/tests/fixtures/phase3_quality_v1.json` is a versioned, manually authored corpus with Atlas and Boreal identifiers, dates, percentages, and node counts; two Orion-4 measurements with matching conditions; one Orion-4 measurement under a different condition; and two within-document Delta precision values. Five real FastEmbed retrieval questions include paraphrases, lookalike identifiers, an absent fact, and a question whose answer exists only outside the selected paper scope. Four separate gold conflict cases test comparable cross-document disagreement, different conditions, within-document disagreement, and different subjects.

The test `rag/tests/test_phase3_evidence_quality.py` uses the cached `BAAI/bge-small-en-v1.5` FastEmbed model (384 dimensions), a fresh `tmp_path` SQLite cache and Chroma directory, the actual `ResearchRetriever`, and `QueryPipeline` with `LLM_PROVIDER=local`. It invokes no generation API. Retrieval quality is measured over answerable retrieval cases; citation precision/recall count the passages selected by the pipeline as evidence for answerable cases, excluding explicitly abstained questions; page accuracy compares selected source page metadata against the fixture. Conflict recognition is tested on the real indexed passage texts passed directly to the actual sufficiency checker.

## Results

- Answerable retrieval cases: **3**. Recall@5: **1.00**; MRR: **1.00** (3/3 expected passages ranked first).
- Pipeline evidence citation precision: **1.00**; recall: **1.00** (3 expected and 3 selected passages across answerable cases).
- Original page locator accuracy: **1.00** (2/2 expected page checks; the third answerable case is an identifier case without a page mapping entry in the fixture).
- Expected abstentions: **2/2** (missing recall, and answer present only in an out-of-scope document); no out-of-scope source was returned.
- Conflict cases: prior metric-only rule **2/4** correct on these same gold cases; updated rule **4/4** correct. Comparable same-condition values were identified as conflicting, including values within one document; changed conditions and different subjects were not.
- Index consistency: **9 synthetic chunks** in the isolated Chroma collection; Atlas and within-document sample counts each matched between Chroma and FTS5, with unique IDs.
- Relevant Phase 2.5 regression evaluation also passed after correcting its false-conflict label: Recall@5 **1.00**, MRR **0.8889** in this run, answer citation precision/recall **1.00**, page accuracy **1.00**, abstention **2/2**. The earlier Phase 2.5 report's MRR **0.7778** is preserved as the historical pre-change result; the revised fixture wording changes one query, so those MRR figures are not a strict same-query before/after comparison.

Metrics are from small synthetic data and local deterministic code. They do not measure live Gemini answer quality, semantic entailment accuracy on papers, broad retrieval performance, or user-corpus behavior. The retrieval-set test intentionally does not count the retrieval candidates returned for an abstention as answer citations.

## Changes

- `rag/research/orchestrator.py`: compare only explicit metric statements with matching subject, metric, unit, and condition; recognize within-document as well as cross-document disagreement.
- `rag/research/claim_verifier.py`: exact numeric boundaries, full identifier recognition, metric-associated numeric comparisons, and less aggressive contradiction status.
- `rag/tests/fixtures/phase2_5_quality_v1.json` and `rag/tests/test_phase2_5_quality.py`: correct the previous false-conflict fixture label and preserve checks for both comparison passages.
- `rag/tests/fixtures/phase3_quality_v1.json` and `rag/tests/test_phase3_evidence_quality.py`: add the Phase 3 gold set, real local retrieval, citations/pages, scope/abstention, index consistency, conflict, numeric, and identifier regressions.
- `rag/tests/test_end_to_end_rag.py`: accept the existing safe generic abstention message when an unsupported BLEU claim has no retrieved passage establishing BLEU (rather than falsely requiring a contradiction-specific message).
- `PHASE3_QUALITY_VALIDATION.md` and `PROJECT_AUDIT.md`: this report and a dated correction addendum.

## Commands and validation

- `\.venv\Scripts\python.exe -m pytest rag/tests/test_phase3_evidence_quality.py rag/tests/test_claim_verifier.py rag/tests/test_research_orchestrator.py -q -s` — **19 passed** in the last targeted run; local FastEmbed metrics above.
- `\.venv\Scripts\python.exe -m pytest rag/tests backend/tests -q` — **189 passed** in 91.36 seconds after the final test adjustment.
- `npm.cmd test` — **18 passed**.
- `npm.cmd run lint` — passed.
- `npm.cmd run typecheck` — passed.
- `npm.cmd run build` — passed (Next.js production build; existing warning: Next.js ESLint plugin not detected in ESLint configuration).
- `git diff --check` — passed; Git emitted only existing LF/CRLF normalization warnings.

## Remaining limitations and decision

The Phase 3 fixture has five retrieval questions and only three answerable queries. The conflict detector recognizes a narrow explicit metric statement shape; implicit paraphrases, arbitrary attributes, mixed units that require conversion, ambiguous subjects, nuanced dates/periods, and semantic contradictions need more evaluation before claiming general conflict detection. The numeric/identifier verifier is still lexical and can neither prove entailment nor reliably interpret every scientific notation, unit, range, or table. The lexical query planner and sufficiency threshold were not changed. No independent candidate reranker was evaluated because no maintained local cross-encoder was already available and ranking was already perfect on this small set; no package or model was downloaded.

**Decision:** Go for the next synthetic/local reliability phase. **Not a go for claims of real-document or broad semantic verification quality.** Before full-corpus/live-provider validation, expand manually annotated real-paper evaluations and review residual false positives/abstentions; keep current safe conservative behavior meanwhile.
