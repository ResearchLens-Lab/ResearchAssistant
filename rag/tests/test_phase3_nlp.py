from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from rag.training.datasets import DatasetStore
from rag.training.nlp.adapters import EntityInferenceAdapter, RelationshipInferenceAdapter
from rag.training.nlp.entities import (
    EntitySpanAnnotation, InsufficientTrainingData, SourceProvenance,
    decode_bio, encode_bio, train_entity_recognizer, viterbi_bio_decode,
)
from rag.training.nlp.readiness import inspect_readiness, validate_training_readiness
from rag.training.nlp.relations import generate_candidate_pairs, train_relationship_extractor
from rag.training.nlp.tokenization import tokenize
from rag.training.registry import ModelRegistry
from rag.training.schema import DatasetExample, ExampleStatus, TaskType


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
PROVENANCE = SourceProvenance(source_document_id="doc-1", paper_id="paper-1", page_number=4, chunk_id="chunk-9")


def test_tokenizer_preserves_unicode_character_offsets_and_sentences():
    text = "Café GraphNet works. Δ-Search follows."
    tokens = tokenize(text)
    assert all(text[token.start:token.end] == token.text for token in tokens)
    assert tokens[0].text == "Café"
    assert tokens[0].sentence_id != next(token for token in tokens if token.text.startswith("Δ")).sentence_id


def test_bio_encoding_and_span_decoding_keep_exact_offsets():
    text = "Thomas H. Cormen wrote the paper."
    start, end = text.index("Thomas"), text.index(" wrote")
    tokens, tags = encode_bio(text, [{"start": start, "end": end, "label": "AUTHOR", "text": text[start:end]}])
    assert [tag for tag in tags if tag != "O"] == ["B-PERSON", "I-PERSON", "I-PERSON", "I-PERSON"]
    spans, malformed = decode_bio(text, tokens, tags, [.9] * len(tags), PROVENANCE)
    assert malformed == 0
    assert len(spans) == 1 and spans[0].text == text[start:end]
    assert spans[0].start == start and spans[0].end == end
    assert spans[0].confidence == pytest.approx(.9)
    assert spans[0].provenance.chunk_id == "chunk-9"


def test_bio_decoder_repairs_orphan_inside_tag_and_viterbi_enforces_transitions():
    text = "Alice studies BERT."
    tokens = tokenize(text)
    spans, malformed = decode_bio(text, tokens, ["I-PERSON"] + ["O"] * (len(tokens) - 1), [.8] * len(tokens), PROVENANCE)
    assert malformed == 1 and spans[0].text == "Alice"
    labels = ["B-PERSON", "I-PERSON", "O", "B-METHOD", "I-METHOD"]
    probs = np.asarray([[.1, .8, .1, 0, 0], [.1, .8, .1, 0, 0], [0, 0, .9, .05, .05]], dtype=float)
    path = viterbi_bio_decode(probs, labels, [0, 0, 0])
    decoded, bad = decode_bio("Alice studies BERT", tokenize("Alice studies BERT"), [labels[i] for i in path], provenance=PROVENANCE)
    assert bad == 0
    assert decoded[0].text == "Alice studies" or decoded[0].text == "Alice"


def test_span_offsets_must_match_exact_source_text():
    with pytest.raises(ValueError, match="does not match"):
        DatasetExample(task_type="entity", input_text="Alice uses BERT", expected_label="SEQUENCE",
                       expected_output={"entities": [{"start": 0, "end": 5, "label": "PERSON", "text": "Alicia"}]})


def test_entity_annotation_boundary_correction_is_audited(tmp_path):
    store = DatasetStore(tmp_path)
    text = "Alice uses BERT."
    example = DatasetExample(task_type="entity", input_text=text, candidate_passage=text, expected_label="SEQUENCE",
                             expected_output={"entities": [{"start": 0, "end": 5, "label": "PERSON", "text": "Alice"}]},
                             source_document_id="doc", paper_id="paper", page_number=1, chunk_id="c1",
                             source_group_id="paper", provenance={"annotation_method": "manual"}, annotator="a")
    store.add(example)
    corrected = {"entities": [{"start": 0, "end": 5, "label": "PERSON", "text": "Alice"},
                               {"start": 11, "end": 15, "label": "TOOL", "text": "BERT"}]}
    reviewed = store.review(example.example_id, ExampleStatus.APPROVED, "reviewer", "SEQUENCE", corrected)
    assert len(reviewed.expected_output["entities"]) == 2
    history = store.history_path.read_text(encoding="utf-8")
    assert '"output_correction"' in history and '"label": "TOOL"' in history


def test_candidate_pairs_are_ordered_sentence_local_and_provenance_exact():
    text = "Alice uses BERT. Carol tests T5."
    spans = []
    for phrase, label in (("Alice", "PERSON"), ("BERT", "TOOL"), ("Carol", "PERSON"), ("T5", "TOOL")):
        start = text.index(phrase)
        spans.append({"start": start, "end": start + len(phrase), "text": phrase, "label": label})
    pairs, _ = generate_candidate_pairs(text, spans)
    assert len(pairs) == 4
    assert all(text[p.subject.start:p.subject.end] == p.subject.text for p in pairs)
    assert all(tokenize(text)[p.subject_token_start].sentence_id == tokenize(text)[p.object_token_start].sentence_id for p in pairs)


def test_no_relation_pair_is_valid_and_candidates_require_explicit_labels():
    text = "Alice and BERT are mentioned together."
    a, b = text.index("Alice"), text.index("BERT")
    example = DatasetExample(task_type="relationship", input_text=text, candidate_passage=text, expected_label="NO_RELATION",
                             expected_output={"subject": {"start": a, "end": a+5, "label": "PERSON", "text": "Alice"},
                                              "object": {"start": b, "end": b+4, "label": "TOOL", "text": "BERT"}},
                             source_document_id="doc", paper_id="paper", page_number=2, chunk_id="c2",
                             source_group_id="paper", provenance={"annotation_method": "manual"}, annotator="a")
    assert example.expected_label == "NO_RELATION"


def test_multiple_supported_relationship_labels_are_preserved_per_pair():
    text = "The paper proposes and uses BERT."
    s, o = text.index("paper"), text.index("BERT")
    example = DatasetExample(task_type="relationship", input_text=text, candidate_passage=text,
                             expected_label="PROPOSES",
                             expected_output={"subject": {"start": s, "end": s+5, "label": "CONCEPT", "text": "paper"},
                                              "object": {"start": o, "end": o+4, "label": "TOOL", "text": "BERT"},
                                              "additional_relationships": ["USES_METHOD"]},
                             source_document_id="d", paper_id="p", page_number=1, chunk_id="c",
                             source_group_id="p", provenance={"annotation_method": "manual"})
    assert example.expected_output["additional_relationships"] == ["USES_METHOD"]


def _approved_entity(example_id="e1", version="phase2-smoke-test"):
    text = "Alice uses BERT."
    return DatasetExample(example_id=example_id, task_type="entity", input_text=text, candidate_passage=text,
                          expected_label="SEQUENCE", expected_output={"entities": [{"start": 0, "end": 5, "label": "PERSON", "text": "Alice"}]},
                          source_document_id="doc", paper_id="paper", page_number=1, chunk_id="c1",
                          source_group_id="synthetic-paper-1", provenance={"not_real_document": True},
                          review_status=ExampleStatus.APPROVED, reviewer="r", reviewed_at=NOW,
                          dataset_version=version, created_at=NOW)


def test_synthetic_data_is_excluded_and_insufficient_training_fails_closed():
    item = _approved_entity()
    manifest = {"train_ids": [item.example_id], "validation_ids": [], "test_ids": []}
    with pytest.raises(ValueError, match="synthetic examples"):
        train_entity_recognizer([item], manifest, min_spans=1, min_documents=1, min_per_type=1)
    report = inspect_readiness("nonexistent-training-store")
    assert report["training_allowed"] == {"entity": False, "relationship": False}
    assert report["annotations"] == {"pending": 0, "approved": 0, "rejected": 0}


def test_relationship_model_refuses_small_reviewed_dataset_before_fit():
    text = "Alice and BERT are mentioned together."
    a, b = text.index("Alice"), text.index("BERT")
    item = DatasetExample(example_id="r1", task_type="relationship", input_text=text, candidate_passage=text,
                          expected_label="NO_RELATION",
                          expected_output={"subject": {"start": a, "end": a+5, "label": "PERSON", "text": "Alice"},
                                           "object": {"start": b, "end": b+4, "label": "TOOL", "text": "BERT"}},
                          source_document_id="doc", paper_id="paper", page_number=1, chunk_id="c1",
                          source_group_id="paper", provenance={"annotation_method": "manual"},
                          review_status=ExampleStatus.APPROVED, reviewer="r", reviewed_at=NOW)
    with pytest.raises(InsufficientTrainingData, match="relationship candidate refused"):
        train_relationship_extractor([item], {"train_ids": ["r1"]})


def test_safe_inference_adapters_use_visible_deterministic_fallback(tmp_path):
    registry = ModelRegistry(tmp_path)
    entity = EntityInferenceAdapter(registry).extract("Alice uses BERT.", PROVENANCE)
    assert entity["model_status"] == "fallback" and entity["entities"] == []
    spans = [{"start": 0, "end": 5, "label": "PERSON", "text": "Alice"},
             {"start": 11, "end": 15, "label": "TOOL", "text": "BERT"}]
    relation = RelationshipInferenceAdapter(registry).extract("Alice uses BERT.", spans, PROVENANCE)
    assert relation["model_status"] == "fallback" and relation["relationships"] == []
    assert relation["candidate_count"] == 2 and relation["uncertainty"] == 1.0


def test_phase3_registry_records_dataset_split_features_and_checksum(tmp_path):
    registry = ModelRegistry(tmp_path)
    record = registry.register({"weights": [1, 2]}, name="entity ner", task="entity_ner", version="1.0",
                               dataset_version="real-v1", dataset_content_hash="abc123",
                               split_manifest_reference="splits/real-v1.json", feature_config={"hash_bins": 32768},
                               label_configuration={"entities": ["PERSON", "METHOD"]},
                               metrics={"validation": {"exact_match_f1": 0.0}},
                               baseline_metrics={"validation": {"exact_match_f1": 0.0}})
    assert record["approval_status"] == "candidate"
    assert record["training_dataset_content_hash"] == "abc123"
    assert record["frozen_split_manifest_reference"] == "splits/real-v1.json"
    assert record["software_versions"]["scikit_learn"]
    assert registry.load_candidate(record["model_id"], "entity_ner") == {"weights": [1, 2]}
    artifact = registry.artifacts / f"{record['model_id']}.joblib"
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    from rag.training.registry import RegistryError
    with pytest.raises(RegistryError, match="checksum"):
        registry.load_candidate(record["model_id"], "entity_ner")


def test_annotation_cli_lists_review_states_and_correction_history(tmp_path, monkeypatch, capsys):
    from rag.training.nlp import cli
    store = DatasetStore(tmp_path)
    pending = DatasetExample(task_type="intent", input_text="What is a graph?", expected_label="DEFINITION", annotator="a")
    store.add(pending)
    store.review(pending.example_id, ExampleStatus.APPROVED, "reviewer")
    rejected = DatasetExample(task_type="intent", input_text="Who made this?", expected_label="AUTHOR_LOOKUP", annotator="a")
    store.add(rejected)
    store.review(rejected.example_id, ExampleStatus.REJECTED, "reviewer")
    monkeypatch.setattr("sys.argv", ["nlp_cli", "--store", str(tmp_path), "list-approved"])
    cli.main()
    assert pending.example_id in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["nlp_cli", "--store", str(tmp_path), "list-rejected"])
    cli.main()
    assert rejected.example_id in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["nlp_cli", "--store", str(tmp_path), "history", "--example-id", pending.example_id])
    cli.main()
    assert pending.example_id in capsys.readouterr().out


def test_frozen_split_must_be_document_level_before_readiness_allows_training():
    rows = [_approved_entity(str(i), "v1") for i in range(3)]
    manifest = {"train_ids": ["0", "1", "2"], "validation_ids": [], "test_ids": [],
                "train_groups": ["same"], "validation_groups": [], "test_groups": []}
    with pytest.raises(ValueError):
        validate_training_readiness(rows, TaskType.ENTITY, manifest)


def test_frozen_split_rejects_assignment_edits(tmp_path):
    from rag.training.splits import freeze_split_manifest, split_from_manifest
    rows = []
    for index in range(9):
        rows.append(DatasetExample(example_id=f"i{index}", task_type="intent", input_text=f"Question {index}",
                                   expected_label="UNKNOWN", source_group_id=f"paper-{index}",
                                   provenance={"annotation_method": "manual"},
                                   review_status=ExampleStatus.APPROVED, reviewer="r", reviewed_at=NOW))
    path = tmp_path / "split.json"
    manifest = freeze_split_manifest(rows, path)
    split_from_manifest(rows, manifest)
    manifest["test_ids"][0], manifest["train_ids"][0] = manifest["train_ids"][0], manifest["test_ids"][0]
    with pytest.raises(ValueError, match="deterministic document-level split"):
        split_from_manifest(rows, manifest)
