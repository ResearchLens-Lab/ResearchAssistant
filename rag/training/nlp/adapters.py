from __future__ import annotations

from typing import Any

from rag.training.nlp.entities import SourceProvenance
from rag.training.nlp.relations import generate_candidate_pairs
from rag.training.registry import ModelRegistry, RegistryError


class EntityInferenceAdapter:
    """Uses only explicitly approved/checksummed models; defaults to a visible all-O fallback."""

    def __init__(self, registry: ModelRegistry, fallback=None):
        self.registry = registry
        self.fallback = fallback or self._empty_fallback

    @staticmethod
    def _empty_fallback(text: str, provenance: SourceProvenance) -> dict[str, Any]:
        return {"entities": [], "malformed_span_count": 0,
                "fallback": "deterministic all-O entity baseline", "uncertainty": 1.0}

    def extract(self, text: str, provenance: SourceProvenance, min_confidence: float = 0.0) -> dict[str, Any]:
        try:
            model = self.registry.load_approved("entity_ner")
        except RegistryError as exc:
            result = self.fallback(text, provenance)
            return {**result, "model_status": "fallback", "fallback_reason": str(exc)}
        result = model.extract(text, provenance, min_confidence)
        return {**result, "model_status": "approved_model"}


class RelationshipInferenceAdapter:
    """Candidate-pair relation classifier with an explicit no-emission fallback."""

    def __init__(self, registry: ModelRegistry, fallback=None):
        self.registry = registry
        self.fallback = fallback or self._no_relation_fallback

    @staticmethod
    def _no_relation_fallback(text, entities, provenance):
        pairs, _ = generate_candidate_pairs(text, list(entities))
        return {"relationships": [], "candidate_count": len(pairs),
                "fallback": "no relation emitted without an approved classifier", "uncertainty": 1.0}

    def extract(self, text: str, entities, provenance: SourceProvenance,
                min_confidence: float = .65) -> dict[str, Any]:
        try:
            model = self.registry.load_approved("relationship_extraction")
        except RegistryError as exc:
            result = self.fallback(text, entities, provenance)
            return {**result, "model_status": "fallback", "fallback_reason": str(exc)}
        result = model.extract(text, entities, provenance, min_confidence)
        return {**result, "model_status": "approved_model"}
