# ResearchLens Phase 3 Implementation Report

## What was implemented

Phase 3 adds optional local NLP components under `rag/training/nlp/`. They are not imported by `QueryPipeline`, not connected to the FastAPI serving path, and do not change `RAG_ENGINE_MODE`. No index, database, conversation, or document collection was modified.

- `tokenization.py`: deterministic Unicode token/sentence segmentation with character offsets into the original passage; sentence-context and orthographic feature extraction; exact token-boundary span alignment.
- `features.py`: categorical feature hashing into a bounded 32,768-bin sparse CPU feature space.
- `entities.py`: configurable entity ontology, sequence span annotation, BIO encoding/repair, hard-constrained Viterbi BIO decoding, token-level TF-IDF-like lexical feature classifier (hashed sparse features + Logistic Regression), exact-text output with confidence/uncertainty and provenance. This is token-level sequence classification; it is distinct from Phase 2 candidate-span classification.
- `relations.py`: sentence-local ordered entity-pair candidate generation; entity type, lexical context, between-entity, position, and distance features; one-vs-rest sparse Logistic Regression trained from reviewed relation sets; explicit `NO_RELATION`; confidence threshold and multi-label output for a pair; exact support sentence and source provenance.
- `evaluation.py`: held-out-only entity exact-span/per-type/token-confusion/BIO-malformation evaluation and relationship micro/macro/per-label/confusion/false-positive/false-negative/`NO_RELATION` evaluation. Deterministic baselines are all-O entities and all-`NO_RELATION` pairs. Relationship confidence threshold selection can use validation only.
- `readiness.py`: inspects the local annotation queue and approved versions; counts real task labels, sources, spans, relations, privacy/provenance issues and frozen splits; excludes synthetic fixtures; blocks training until task gates pass.
- `adapters.py`: checksum-verified approved-model inference wrappers with visible deterministic fallback and confidence/uncertainty. These adapters are intentionally not called by Phase 1.
- `cli.py`: annotation, correction/review, readiness, dataset validation, split freezing, training/candidate registration, held-out evaluation, explicit approval, and registry inspection.

Phase 2 was extended compatibly: `DatasetExample` now validates exact entity offsets and relationship-pair spans/labels; a relationship row can include multiple positive `additional_relationships`; correction history records corrected span output; relationship-pair duplicates are distinguished by pair offsets; frozen splits verify the deterministic document assignment; and the registry records training data hash, frozen-split path/hash, label/feature configuration, baseline metrics, Python/scikit-learn/joblib versions, artifact checksum, status, and training time. Private local annotations and model files are ignored by `.gitignore`.

## Real-data gate and model status

The default annotation store, `rag/training/local_data/`, does not exist. The readiness command found zero pending, approved, or rejected local annotations; zero approved real examples for every task; zero real source documents; zero entity spans; zero labelled relationship pairs; no real-data split manifest; no private examples; and no missing-provenance examples. It found the separate 30-row Phase 2 synthetic fixture and explicitly excluded all 30 rows from real-data counts and training.

Accordingly, **no entity or relationship model was fit, registered as a candidate, or approved**. No synthetic labels were generated or mixed into the local training store. The repository's Phase 2 synthetic smoke scores are not reused as Phase 3 model results.

Readiness gates require at least 50 reviewed real task examples across at least five identifiable source documents, valid non-overlapping frozen train/validation/test groups, complete source provenance, and explicit permission for private data. Entity data additionally needs at least 50 spans and two entity types with at least five reviewed spans each. Relationship data additionally needs positive and `NO_RELATION` examples and at least five examples per observed relationship label. The trainer checks the complete approved version before fitting; below-gate data fails closed.

## Reproducible commands

Run from the project root in PowerShell. Annotation JSON files contain Unicode-codepoint `start`/`end` offsets and exact `text` values from the original passage.

```powershell
# Inspect local readiness; this is read-only and does not create the store.
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data readiness

# Add a token-level entity annotation as pending (spans.json is an array of exact spans).
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data annotate-entity --text "Alice uses BERT." --spans-json spans.json --document-id doc-17 --paper-id paper-4 --page 5 --chunk-id doc-17-c12 --source-group-id paper-4 --annotator researcher

# Add a reviewed-pair candidate label; repeat --additional-label for multiple positive relations.
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data annotate-relationship --text "The paper proposes and uses BERT." --subject-json subject.json --object-json object.json --label PROPOSES --additional-label USES_METHOD --document-id doc-17 --paper-id paper-4 --page 5 --chunk-id doc-17-c12 --source-group-id paper-4 --annotator researcher

# Review/correct boundaries or types; corrected-output.json contains the complete expected_output object.
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data list-pending
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data list-approved
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data list-rejected
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data history --example-id EXAMPLE_ID
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data review EXAMPLE_ID --status approved --reviewer reviewer --correct-output-json corrected-output.json

# Export reviewed examples using the Phase 2 immutable versioned workflow.
.\.venv\Scripts\python.exe -m rag.training.cli --store rag/training/local_data export-approved --version real-v1
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data validate --version real-v1
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data freeze-split --version real-v1
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data readiness

# These fail closed until real-data readiness thresholds pass. Entity ontology aliases are optional JSON.
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data train-entity --version real-v1 --model-version 1.0.0 --ontology-json ontology.json
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data train-relationship --version real-v1 --model-version 1.0.0

# Test is read only for the final evaluation. Approval remains an explicit, separate action.
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data evaluate-candidate --version real-v1 --model-id MODEL_ID --task entity_ner
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --store rag/training/local_data approve-candidate --model-id MODEL_ID --metric exact_match_f1
.\.venv\Scripts\python.exe -m rag.training.nlp.cli --registry rag/training/model_registry inspect-registry
```

For relationship approval, use `--metric micro_f1`. Candidate registration happens only after the version has passed readiness and a model fit succeeds; final test evaluation and approval are separate commands. The test partition is not used for threshold selection.

## Phase 1 and hardware boundary

The classifiers use CPU scikit-learn Logistic Regression over sparse hashed local features, with a fixed 32,768-bin ceiling, no GPU, no multiprocessing, no pretrained weights, no embedding downloads, and no external inference. Phase 1 remains the baseline and is operational. Phase 3 outputs are provenance-aware candidate objects only; they do not mutate the knowledge graph or permanent stores.

See [PHASE3_DATASET_READINESS.md](PHASE3_DATASET_READINESS.md), [PHASE3_MODEL_EVALUATION.md](PHASE3_MODEL_EVALUATION.md), and [PHASE3_KNOWN_LIMITATIONS.md](PHASE3_KNOWN_LIMITATIONS.md) for the actual readiness counts, evaluation status, and limits.
