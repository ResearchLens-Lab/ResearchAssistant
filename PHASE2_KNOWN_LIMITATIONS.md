# ResearchLens Phase 2 Known Limitations

- The only checked training run uses six synthetic document groups and a five-example test split; it does not establish real-world intent or ranking quality.
- The review queue and registry are local JSON/JSONL files, not a multi-user database. Concurrent writes are not coordinated across processes; keep one annotator process per store and back up approved snapshots.
- Training infrastructure is not connected to the FastAPI/frontend annotation experience or Phase 1 serving. This preserves runtime behavior and keeps adoption an explicit future step.
- The relevance model is a supervised binary Logistic Regression score derived from 0–3 labels; it is not a pairwise/listwise neural ranker. The deterministic baseline remains authoritative unless a meaningful held-out gain is established.
- Generic entity classification uses manually provided candidate spans/text. It is not sequence labeling, advanced NER, or an automatic document entity miner.
- Evidence and claim classifiers can be trained with reviewed labels, and their requested evaluation metrics are available, but Phase 2 does not train them without a sufficiently sized, reviewed dataset and comparison baseline.
- Class imbalance is reported, not automatically corrected through data synthesis. `class_weight="balanced"` is used in classifier fits; small classes can still produce unstable metrics.
- The held-out test set is frozen by content hash and document groups. A changed dataset requires a new version/split; keep old test results private from model tuning.
- The registry uses `joblib` serialization. Only load local artifacts from the trusted registry directory; checksum validation detects accidental/tampered artifact changes against the registry manifest, but it is not a signed supply-chain format if both artifact and manifest are maliciously replaced.
- Peak RAM and training throughput have not been benchmarked on the target i5-6300U/8 GB machine. Vocabulary is bounded to 20,000 sparse features and training uses one CPU process, but large datasets need measured capacity planning.
- No model is automatically activated. Approval requires an explicit call, held-out-test metrics, and a metric greater than the configured deterministic baseline. Runtime integration and staged rollback exercises remain Phase 3 work.
