"""Pure, deterministic Phase 6 evaluator for hand-judged JSON fixtures."""
from __future__ import annotations

from rag.training.metrics import ranking_metrics


def evaluate_memory_fixture(fixture: dict, k: int = 5) -> dict:
    retrieval = fixture.get("retrieval_cases", [])
    groups = {}
    for item in retrieval:
        groups[item["case_id"]] = [(float(result["score"]), int(bool(result["relevant"])))
                                    for result in item["ranked_results"]]
    retrieval_metrics = ranking_metrics(groups, k) if groups else {}
    assoc = fixture.get("association_cases", [])
    false_assoc = sum(bool(x.get("presented_as_established")) and not bool(x.get("reviewed_confirmed")) for x in assoc)
    contradiction = fixture.get("contradiction_cases", [])
    tp = sum(bool(x.get("expected_candidate")) and bool(x.get("detected_candidate")) for x in contradiction)
    fp = sum(not bool(x.get("expected_candidate")) and bool(x.get("detected_candidate")) for x in contradiction)
    fn = sum(bool(x.get("expected_candidate")) and not bool(x.get("detected_candidate")) for x in contradiction)
    gaps = fixture.get("gap_cases", [])
    gap_correct = sum(bool(x.get("expected_recorded")) == bool(x.get("actual_recorded")) and
                      (not x.get("expected_type") or x.get("expected_type") == x.get("actual_type")) for x in gaps)
    temporal = fixture.get("temporal_cases", [])
    temporal_checks = sum(len(x.get("checks", [])) for x in temporal)
    temporal_passed = sum(bool(c.get("passed")) for x in temporal for c in x.get("checks", []))
    n = len(contradiction)
    resolved = [x for x in contradiction if x.get("expected_outcome") is not None]
    return {
        "fixture_id": fixture.get("fixture_id"), "synthetic": bool(fixture.get("synthetic", True)),
        "sample_sizes": {"retrieval_queries": len(retrieval), "association_cases": len(assoc),
                         "contradiction_cases": len(contradiction), "gap_cases": len(gaps),
                         "temporal_cases": len(temporal), "temporal_checks": temporal_checks},
        "retrieval": retrieval_metrics,
        "associations": {"false_association_rate": false_assoc / len(assoc) if assoc else None,
                         "cases_improperly_presented_as_established": false_assoc},
        "contradictions": {"precision": tp / (tp + fp) if tp + fp else 0.0,
                           "recall": tp / (tp + fn) if tp + fn else 0.0,
                           "false_candidate_rate": fp / n if n else 0.0,
                           "true_positive": tp, "false_positive": fp, "false_negative": fn,
                           "reviewed_outcome_accuracy": sum(x.get("expected_outcome") == x.get("actual_outcome") for x in resolved) / len(resolved) if resolved else None},
        "research_gaps": {"type_and_recording_accuracy": gap_correct / len(gaps) if gaps else None,
                          "correct_cases": gap_correct},
        "temporal": {"check_accuracy": temporal_passed / temporal_checks if temporal_checks else None,
                     "passed": temporal_passed, "total": temporal_checks},
        "limitations": "Scores describe only the supplied judged fixture. They are not real-paper accuracy, calibrated probabilities, or scientific truth measures.",
    }
