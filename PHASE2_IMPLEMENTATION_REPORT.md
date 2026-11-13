# ResearchLens Phase 2 Implementation Report

## Scope and safety

Phase 2 adds local infrastructure to curate reviewed labels, train/evaluate small CPU task models, and keep candidate/approved artifacts in a versioned local registry. It is not connected to serving: `RAG_ENGINE_MODE=independent`, its deterministic retrieval and response pipeline, the legacy path, databases, indexes, and conversations were not changed for model adoption. No model is automatically activated.

No uploaded library is harvested as training data. A local example starts pending, only explicitly reviewed examples can be exported, and private sources require explicit per-example `training_permission`. The included smoke set is marked synthetic and kept separate from real-paper evaluation.

## Implementation

- `rag/training/schema.py`: typed six-task example schema, label validation, provenance/page/chunk fields, privacy flags, timestamps, reviewer and dataset version.
- `rag/training/datasets.py`: append/update workflow, duplicate and contradiction checks, provenance and imbalance report, review queue, correction history, approved-only immutable version export with SHA-256 manifest.
- `rag/training/cli.py`: local pending/add/review/export commands. It is separate from app UI and does not add an application dependency.
- `rag/training/splits.py`: deterministic paper/document-group splits and frozen manifests that reject content drift or cross-partition leakage.
- `rag/training/models.py`: CPU TF-IDF + Logistic Regression intent classification and supervised relevance classification; generic classical label classifiers for evidence, claim, relationship, and manually supplied entity-span labels. No token-sequence NER is claimed.
- `rag/training/metrics.py`: classification accuracy/macro-F1/per-class metrics/confusion matrix, Recall@K/MRR/NDCG, evidence precision/recall/false-support/false-abstention, exact entity span precision/recall/F1, and baseline comparisons for intent/ranking.
- `rag/training/registry.py`: candidate registration, explicit test-split-vs-baseline approval gate, artifact checksum and task/version checks, rollback, and deterministic fallback adapter. Artifacts are loaded only from the registry directory after checksum verification.
- `rag/training/smoke_run.py` and `rag/training/fixtures/`: isolated synthetic smoke dataset/results; no model is activated.
- `rag/tests/test_training_infrastructure.py`: annotation, privacy, validation, leakage split, training, metrics, serialization, registry, rollback, tamper, and fallback coverage.
- `requirements.txt`: added scikit-learn and joblib CPU dependencies. The Phase 1 serving pipeline does not import or invoke them.

## Training algorithms and hardware

All model features are sparse word unigram/bigram TF-IDF with a 20,000-feature ceiling and `float32` vectorization. Logistic Regression uses a bounded 300-iteration CPU fit, a single process, and no GPU. No pretrained weights, remote model calls, CUDA, Transformer models, or embedding downloads are used. Dataset input is loaded as structured JSONL; this phase does not build an all-corpus matrix or train on the user’s full library.

For the target i5-6300U / 8 GB Windows machine, the implementation is designed for small reviewed datasets and bounded sparse vocabularies. Training time and memory grow with the number and length of reviewed examples. The current smoke run does not establish a reliable peak-memory figure or production-scale training speed; measure those on the target data before scaling. No heavy multiprocessing is configured.

## Annotation commands

From the project root:

```powershell
.\.venv\Scripts\python.exe -m rag.training.cli --store rag/training/local_data list-pending
.\.venv\Scripts\python.exe -m rag.training.cli --store rag/training/local_data add --task intent --input "What is an algorithm?" --label DEFINITION --annotator "researcher" --source-group-id "paper-17"
.\.venv\Scripts\python.exe -m rag.training.cli --store rag/training/local_data review EXAMPLE_ID --status approved --reviewer "reviewer" --correct-label DEFINITION
.\.venv\Scripts\python.exe -m rag.training.cli --store rag/training/local_data export-approved --version v1.0.0
```

Pass `--document-id`, `--paper-id`, `--page`, `--chunk-id`, and `--passage` for passage/entity/evidence/claim/relationship examples. For private material, `--private` and `--training-permission` are both required before approval. Training uses the exported `approved.jsonl`, not pending annotations.

## Results

See [PHASE2_TRAINING_RESULTS.md](PHASE2_TRAINING_RESULTS.md) for measured synthetic fixture scores and clear limitations. The held-out synthetic intent sample measured higher accuracy and macro-F1 than the rule baseline; the synthetic passage ranker tied its lexical baseline. The registry therefore does not auto-activate either result.

## Phase 3 prerequisites

Before connecting learned components to runtime: collect a larger manually reviewed corpus with explicit rights and document-level provenance; include all intent classes and realistic hard negatives; reserve multiple independent papers for a stable untouched test set; evaluate per-domain and per-class uncertainty; compare against Phase 1 across several dataset versions; review performance and safety thresholds; and explicitly approve a model in the registry. Any serving adapter should retain rules/fallback and expose model/dataset/version metadata. The current registry adapter is opt-in and is not wired into Phase 1.
