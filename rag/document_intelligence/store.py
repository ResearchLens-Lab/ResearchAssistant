from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.document_intelligence.models import DocumentIntelligence, ReviewEvent


class ExtractionStore:
    """Local versioned artifact store; atomic snapshots avoid partial extraction writes."""

    def __init__(self, root: str | Path = "rag/document_intelligence/local_data"):
        self.root = Path(root)

    def save(self, extraction: DocumentIntelligence) -> tuple[Path, bool]:
        run_dir = self.root / extraction.document_id / "runs"
        target = run_dir / f"{extraction.run_id}.json"
        run_dir.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing.get("content_hash") == extraction.content_hash and existing.get("extraction_version") == extraction.extraction_version:
                return target, False
        self._atomic_json(target, extraction.model_dump(mode="json"))
        self._atomic_json(self.root / extraction.document_id / "current.json", {"run_id": extraction.run_id})
        return target, True

    def save_failure(self, document_id: str, error: str, extraction_version: str = "phase4-rules-1") -> Path:
        """Record a failed opt-in attempt without moving the last successful pointer."""
        run_id = "failed_" + uuid.uuid4().hex
        target = self.root / document_id / "runs" / f"{run_id}.json"
        self._atomic_json(target, {"run_id": run_id, "document_id": document_id,
                                   "extraction_version": extraction_version, "status": "failed",
                                   "error_type": error[:120], "recorded_at": datetime.now(timezone.utc).isoformat()})
        return target

    def get(self, document_id: str, run_id: str | None = None) -> DocumentIntelligence:
        base = self.root / document_id
        if run_id is None:
            pointer = json.loads((base / "current.json").read_text(encoding="utf-8"))
            run_id = pointer["run_id"]
        data = json.loads((base / "runs" / f"{run_id}.json").read_text(encoding="utf-8"))
        result = DocumentIntelligence.model_validate(data)
        events = self.list_review_events(document_id, run_id)
        by_id = {r.record_id: r for r in result.knowledge_records}
        for event in events:
            record = by_id.get(event.record_id)
            if record:
                for key, value in event.updated.items():
                    if key in record.model_fields:
                        setattr(record, key, value)
        return result

    def list_runs(self, document_id: str) -> list[dict[str, Any]]:
        folder = self.root / document_id / "runs"
        output = []
        for path in sorted(folder.glob("*.json")) if folder.exists() else []:
            data = json.loads(path.read_text(encoding="utf-8"))
            output.append({"run_id": data["run_id"], "extraction_version": data["extraction_version"],
                           "status": data.get("status", data.get("extraction_status", "unknown")),
                           "content_hash": data.get("content_hash"),
                           "duration_seconds": data.get("duration_seconds")})
        return output

    def review(self, document_id: str, run_id: str, record_id: str, action: str, reviewer: str,
               correction: dict[str, Any] | None = None, training_permission: bool = False) -> ReviewEvent:
        extraction = self.get(document_id, run_id)
        record = next((r for r in extraction.knowledge_records if r.record_id == record_id), None)
        if record is None:
            raise ValueError(f"Unknown knowledge record: {record_id}")
        if action not in {"approve", "reject", "correct"}:
            raise ValueError("Review action must be approve, reject, or correct")
        if action == "correct" and not correction:
            raise ValueError("Correction requires at least one field")
        previous = record.model_dump(mode="json")
        updated = dict(correction or {})
        updated.setdefault("review_status", "approved" if action in {"approve", "correct"} else "rejected")
        changed = {**previous, **updated}
        # Validate complete corrected record, including unchanged provenance.
        from rag.document_intelligence.models import KnowledgeRecord
        revised = KnowledgeRecord.model_validate(changed)
        if revised.document_id != document_id or revised.record_id != record_id:
            raise ValueError("Review cannot change document or record identity")
        if revised.char_start < 0 or revised.char_end < revised.char_start:
            raise ValueError("Invalid evidence offsets")
        source_page = next((p for p in extraction.pages if p["page_number"] == revised.page_number), None)
        if source_page is None or revised.char_end > len(source_page["text"]):
            raise ValueError("Evidence offsets do not fit the source page")
        if source_page["text"][revised.char_start:revised.char_end] != revised.exact_text:
            raise ValueError("Corrected evidence must exactly match the source page offsets")
        if training_permission and action != "approve":
            raise ValueError("Training permission can only accompany an explicit approval")
        event = ReviewEvent(event_id=hashlib.sha256(f"{run_id}:{record_id}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:20],
                            run_id=run_id, record_id=record_id, action=action, reviewer=reviewer,
                            changed_at=datetime.now(timezone.utc).isoformat(), previous=previous,
                            updated=updated, training_permission=training_permission)
        path = self.root / document_id / "review_history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(event.model_dump_json() + "\n")
            stream.flush(); os.fsync(stream.fileno())
        return event

    def list_review_events(self, document_id: str, run_id: str | None = None) -> list[ReviewEvent]:
        path = self.root / document_id / "review_history.jsonl"
        if not path.exists(): return []
        events = [ReviewEvent.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [e for e in events if run_id is None or e.run_id == run_id]

    @staticmethod
    def _atomic_json(target: Path, payload: dict[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".phase4-", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name): os.unlink(temp_name)
