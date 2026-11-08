"""Claim-level citation checks with deterministic provenance and an optional narrow LLM judge.

The lexical fallback is deliberately described as a heuristic; it is not an entailment model.
"""
import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from rag.generation.llm_client import BaseLLMClient
from rag.retrieval.query import RetrievedSource

ClaimStatus = Literal["supported", "partial", "contradicted", "unsupported", "invalid_reference"]


class ClaimCheck(BaseModel):
    claim_text: str
    evidence_ids: list[str] = Field(default_factory=list)
    status: ClaimStatus
    reason: Optional[str] = None
    source_ids: list[str] = Field(default_factory=list)
    locators: list[Optional[str]] = Field(default_factory=list)


class ClaimVerificationReport(BaseModel):
    items: list[ClaimCheck] = Field(default_factory=list)
    method: str
    verified_answer: str
    repair_attempted: bool = False


class LLMJudgeResult(BaseModel):
    status: Literal["supported", "partial", "contradicted", "unsupported"]
    evidence_ids: list[str]
    reason: str = Field(max_length=300)


class LLMClaimJudge:
    """Ask one bounded, schema-validated support question per answer, never for new citations."""
    def __init__(self, client: BaseLLMClient):
        self.client = client
        self.calls = 0

    def judge(self, claim: str, evidence: list[RetrievedSource]) -> ClaimStatus:
        payload = [{"evidence_id": s.source_id, "text": s.text} for s in evidence]
        prompt = (
            "Return only JSON: {\"status\":\"supported|partial|contradicted|unsupported\","
            "\"evidence_ids\":[...],\"reason\":\"short\"}. Judge only whether the listed excerpts "
            "support the claim. Use only listed evidence IDs. Do not infer missing details.\n"
            f"CLAIM: {claim}\nEVIDENCE: {json.dumps(payload, ensure_ascii=False)}"
        )
        self.calls += 1
        raw = self.client.generate("You are a cautious evidence verifier.", prompt, temperature=0, max_tokens=180)
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return "unsupported"
        try:
            value = LLMJudgeResult.model_validate_json(match.group())
            status = value.status
            ids = {s.source_id.casefold() for s in evidence}
            if status in {"supported", "partial", "contradicted"} and not value.evidence_ids:
                return "unsupported"
            if any(i.casefold() not in ids for i in value.evidence_ids):
                return "unsupported"
            return status
        except (ValueError, TypeError, KeyError, ValidationError):
            return "unsupported"


class ClaimEvidenceVerifier:
    MAX_CLAIMS = 12
    TAG = re.compile(r"\[((?:Source\s*)?S\d+(?:\s*,\s*(?:Source\s*)?S\d+)*)\]", re.I)
    WORD = re.compile(r"[a-z][a-z0-9-]{2,}", re.I)
    STOP = {"the", "and", "for", "with", "from", "that", "this", "was", "were", "are", "its", "their", "they", "then", "than", "into", "also", "using", "used", "based", "reported", "shows", "showed", "paper", "study", "result", "results"}
    # Keep numbers as complete atoms: 91 must not match 91.2, and digits inside
    # identifiers such as AX-17A must not be treated as independent measurements.
    NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?\s*%?(?![\w.])")
    IDENTIFIER = re.compile(r"(?<!\w)(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+(?!\w)", re.I)
    METRIC = re.compile(r"\b(accuracy|precision|recall|bleu|f1|error rate)\b", re.I)

    def __init__(self, judge: Optional[LLMClaimJudge] = None):
        self.judge = judge

    @classmethod
    def _metric_value(cls, text: str, metric: str) -> Optional[str]:
        """Return a nearby explicit metric value, without treating later dates as it."""
        escaped = re.escape(metric)
        patterns = (
            rf"\b{escaped}\b\s+(?:was|is|of|at|reached|reported)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)?",
            rf"(\d+(?:\.\d+)?)\s*(?:%|percent)?\s+\b{escaped}\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(1)
        return None

    @classmethod
    def _sentences(cls, answer: str):
        for line in answer.splitlines():
            if not line.strip() or line.lstrip().startswith("#") or line.strip() in {"---", "***"}:
                yield line, False
                continue
            # Preserve markdown list/table lines as one claim; split prose at sentence boundaries.
            pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", line)
            trailing = re.search(r"((?:\[(?:Source\s*)?S\d+(?:\s*,\s*(?:Source\s*)?S\d+)*\]\s*)+)$", line, re.I)
            inherited_citations = trailing.group(1).strip() if trailing else ""
            for piece in pieces:
                if inherited_citations and not cls.TAG.search(piece):
                    piece = piece.rstrip() + " " + inherited_citations
                yield piece, bool(cls.WORD.search(re.sub(cls.TAG, "", piece))) and len(piece.split()) >= 5

    def verify(self, answer: str, sources: list[RetrievedSource], selected_paper_ids: list[str]) -> ClaimVerificationReport:
        by_id = {s.source_id.upper(): s for s in sources}
        kept, checks = [], []
        method = "deterministic provenance and lexical/numeric support heuristic (not entailment)"
        if self.judge:
            method = "deterministic provenance plus one schema-validated LLM support judgment per material claim; fallible"
        material_count = 0
        for piece, substantive in self._sentences(answer):
            if not substantive:
                kept.append(piece)
                continue
            material_count += 1
            if material_count > self.MAX_CLAIMS:
                checks.append(ClaimCheck(claim_text=re.sub(self.TAG, "", piece).strip(), evidence_ids=[],
                                         status="unsupported", reason="Verification claim budget exceeded.", source_ids=[], locators=[]))
                continue
            raw_ids = [x.upper() for x in re.findall(r"S\d+", " ".join(self.TAG.findall(piece)), re.I)]
            reason = None
            resolved = [by_id[x] for x in dict.fromkeys(raw_ids) if x in by_id]
            in_scope = [s for s in resolved if not selected_paper_ids or s.paper_id in selected_paper_ids]
            invalid = len(in_scope) != len(dict.fromkeys(raw_ids)) or any(
                not s.text.strip() or not s.chunk_id or not s.document_id
                or (s.page_start is not None and s.page_end is not None and s.page_end < s.page_start)
                or (s.page_start is None and not s.locator)
                for s in in_scope
            )
            if not raw_ids or invalid:
                status: ClaimStatus = "invalid_reference" if raw_ids else "unsupported"
                reason = "Citation does not resolve to authorized retrieved evidence with valid provenance." if raw_ids else "Material claim has no evidence citation."
                eligible = []
            else:
                eligible = in_scope
                if self.judge:
                    status = self.judge.judge(re.sub(self.TAG, "", piece).strip(), eligible)
                else:
                    claim = re.sub(self.TAG, "", piece).casefold()
                    terms = {w for w in self.WORD.findall(claim) if w not in self.STOP}
                    evidence = " ".join(s.text.casefold() for s in eligible)
                    nums = [n.strip() for n in self.NUMBER.findall(claim)]
                    evidence_numbers = {n.strip() for n in self.NUMBER.findall(evidence)}
                    ids = {value.casefold() for value in self.IDENTIFIER.findall(claim)}
                    evidence_ids = {value.casefold() for value in self.IDENTIFIER.findall(evidence)}
                    missing_values = any(n not in evidence_numbers for n in nums)
                    missing_ids = any(value not in evidence_ids for value in ids)
                    if missing_values or missing_ids:
                        # Only call a numeric mismatch a contradiction when the same
                        # named metric is explicitly measured in the excerpt. Unrelated
                        # dates/counts do not contradict a claim. An alternate ID is
                        # contradictory only when the excerpt labels an identifier.
                        metrics = {m.casefold() for m in self.METRIC.findall(claim)}
                        evidence_metrics = {m.casefold() for m in self.METRIC.findall(evidence)}
                        metric_conflict = any(
                            self._metric_value(claim, metric) is not None
                            and self._metric_value(evidence, metric) is not None
                            and self._metric_value(claim, metric) != self._metric_value(evidence, metric)
                            for metric in metrics & evidence_metrics
                        )
                        identifier_conflict = missing_ids and "identifier" in evidence
                        status = "contradicted" if metric_conflict or identifier_conflict else "unsupported"
                    else:
                        overlap = len(terms & set(self.WORD.findall(evidence))) / max(1, len(terms))
                        status = "supported" if overlap >= .55 else "partial" if overlap >= .25 else "unsupported"
                    reason = "Claim's value is absent from evidence for the same explicitly named attribute." if status == "contradicted" else "A requested value or identifier is absent from cited evidence." if status == "unsupported" and (missing_values or missing_ids) else "Lexical overlap heuristic; semantic entailment not established." if status != "supported" else None
            check = ClaimCheck(claim_text=re.sub(self.TAG, "", piece).strip(), evidence_ids=[s.chunk_id for s in eligible],
                               status=status, reason=reason,
                               source_ids=[s.source_id for s in eligible], locators=[s.locator or (f"page:{s.page_start}" if s.page_start else None) for s in eligible])
            checks.append(check)
            if status in {"supported", "partial"}:
                if status == "partial":
                    kept.append("The available evidence partially supports this statement: " + piece)
                else:
                    kept.append(piece)
            elif status == "contradicted":
                kept.append("The cited passages conflict with this statement, so it is not reported as established.")
        return ClaimVerificationReport(items=checks, method=method, verified_answer="\n".join(kept))
