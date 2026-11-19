"""Deterministic source-to-claim checks for independent-mode answers."""

import re
import unicodedata
from collections import defaultdict

from rag.independent.models import EvidenceDecision, ExtractedFact, QuestionIntent
from rag.retrieval.query import RetrievedSource


_CITATION = re.compile(r"\[(S\d+)\]", re.I)
_NEGATION = re.compile(r"\b(?:not|no|never|without|failed|decreased|lower|worse|unsupported)\b", re.I)
_METRIC = re.compile(r"\b(accuracy|precision|recall|f1(?:-score)?|bleu|auc|rmse|mae|latency|error\s+rate)\b", re.I)
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?\s*(?:%|percent|ms|seconds?|minutes?|hours?|days?|years?|mb|gb)?(?![\w])", re.I)


def _norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


class EvidenceValidator:
    """Only citations resolving to actual retrieved chunks count as support."""

    def validate(self, answer: str, sources: list[RetrievedSource], facts: list[ExtractedFact],
                 important_terms: list[str], intent: QuestionIntent | None = None) -> EvidenceDecision:
        if not sources:
            return EvidenceDecision(status="NOT FOUND", reasons=["No passages matched the selected-document search."])
        by_id = {source.source_id.upper(): source for source in sources}
        cited = [value.upper() for value in _CITATION.findall(answer)]
        invalid = [value for value in cited if value not in by_id]
        wrong_pages = [source.source_id for source in sources if source.page_start is not None and source.page_start < 1]
        fact_by_source = defaultdict(list)
        for fact in facts:
            fact_by_source[fact.source_id.upper()].append(fact)

        unsupported: list[str] = []
        for fact in facts:
            source = by_id.get(fact.source_id.upper())
            if not source or source.chunk_id != fact.chunk_id or source.document_id != fact.document_id:
                unsupported.append(f"fact source mapping mismatch: {fact.fact_type}")
                continue
            if fact.physical_page is not None and fact.physical_page != source.page_start:
                unsupported.append(f"fact page mapping mismatch: {fact.fact_type}")
            if fact.extraction_method != "indexed_source_metadata" and _norm(fact.supporting_passage) not in _norm(source.text):
                unsupported.append(f"extracted passage absent from indexed chunk: {fact.fact_type}")

        # Remove fenced code blocks (```pie ... ```, ```mermaid ... ```) so diagram/chart syntax isn't flagged as claims
        clean_for_validation = re.sub(r"```[\s\S]*?```", "", answer)

        raw_lines = [line.strip() for line in clean_for_validation.splitlines()
                     if line.strip() and not line.lstrip().startswith("#")]
        factual_lines = []
        for line in raw_lines:
            clean_l = line.lstrip("> ").strip() if line.startswith(">") else line
            if not clean_l or clean_l.startswith((
                "Evidence state:", "These are source-by-source excerpts;", "This is a summary of retrieved passages,",
                "This structured summary", "This flowchart", "All ", "Scope note", "Sequential ",
                "Each document receives its own retrieval pass", "This report organizes retrieved evidence",
                "The excerpts are presented source by source", "The comparison is limited to the selected documents",
                "Only reported text is included", "Similarity or equivalence is not inferred",
                "No relevant passage was retrieved", "No relevant passage retrieved",
                "The names were extracted from an explicit author label/byline;", "Not found in your selected documents.",
                "The names were extracted from title-page or bibliographic structure;",
                "The retrieved text does not contain a clear definition; these passages are related evidence:",
                "The source passages do not expose a clearly ordered list; the following passages describe the process:",
                "Sections are analyzed hierarchically:", "Sections are ranked primarily",
                "Sections are analyzed and ranked", "According to the selected document",
                "Comparison between", "Between **Section", "The document covers **",
                "- **Listed subtopics**:", "- **Leaf-level topic entries**:",
                "- **Curriculum volume**:", "- **Structure**:",
                "*Not explicitly detailed", "Not explicitly detailed",
                "###", "| Source |", "|---|", "|",
            )):
                continue
            if line.startswith("|") and "No matching detail in retrieved passages" in line:
                continue
            factual_lines.append(clean_l)
        factual_lines = [line for line in factual_lines if not (line.startswith("|") and "No matching detail in retrieved passages" in line)]
        uncited = [line for line in factual_lines if not _CITATION.search(line)
                   and not line.startswith("Not found in the retrieved passages.")]
        if uncited:
            unsupported.extend(f"uncited statement: {line[:120]}" for line in uncited)
        for line in factual_lines:
            ids = [value.upper() for value in _CITATION.findall(line)]
            if not ids:
                continue
            claim = self._line_claim(line)
            for source_id in ids:
                source = by_id.get(source_id)
                if source and claim and _norm(claim) not in _norm(source.text):
                    source_facts = fact_by_source.get(source_id, [])
                    if any(_norm(fact.value) in _norm(claim) or _norm(claim) in _norm(fact.supporting_passage)
                           for fact in source_facts if fact.supporting_passage):
                        continue
                    if source.section and _norm(source.section) in _norm(line):
                        continue
                    unsupported.append(f"cited statement is not present in source chunk [{source_id}]: {claim[:100]}")
        if invalid:
            unsupported.extend(f"citation [{value}] does not map to a retrieved chunk" for value in invalid)
        if wrong_pages:
            unsupported.extend(f"source {source_id} has an invalid physical page" for source_id in wrong_pages)

        conflicts = self._find_conflicts(facts, important_terms)
        if conflicts:
            status = "CONFLICTING EVIDENCE"
            reasons = ["Retrieved passages report different values or opposing statements for a shared query-relevant claim."]
        elif unsupported:
            status = "INSUFFICIENT EVIDENCE"
            reasons = ["At least one factual statement or citation did not pass source-to-chunk validation."]
        elif not cited:
            status = "INSUFFICIENT EVIDENCE"
            reasons = ["The composed answer contains no citation to a retrieved passage."]
        else:
            structural_intents = {
                QuestionIntent.TOPIC_COUNT_RANKING,
                QuestionIntent.TOPIC_COVERAGE_ANALYSIS,
                QuestionIntent.TOPIC_EXTRACTION,
                QuestionIntent.SECTION_COMPARISON,
            }
            if intent in structural_intents and not unsupported and set(cited).issubset(by_id):
                status = "COMPUTED FROM EXTRACTED DOCUMENT STRUCTURE"
                reasons = ["All topic counts, subtopic breakdowns, and section rankings are computed deterministically from verified extracted document records, with each section cited directly to its source chunk."]
            else:
                fact_sources = {fact.source_id.upper() for fact in facts if fact.source_id.upper() in by_id}
                overlap = any(term.casefold() in _norm(" ".join(f.supporting_passage for f in facts)) for term in important_terms)
                if ((fact_sources and overlap) or not unsupported) and set(cited).issubset(by_id):
                    status = "STRONGLY SUPPORTED"
                    reasons = ["Displayed facts and topics are extracted from retrieved passages and each citation resolves to its chunk."]
                else:
                    status = "PARTIALLY SUPPORTED"
                    reasons = ["Citations resolve to retrieved chunks, but the extracted facts do not cover the full query clearly."]
        return EvidenceDecision(
            status=status, reasons=reasons,
            supported_source_ids=list(dict.fromkeys(value for value in cited if value in by_id)),
            unsupported_claims=unsupported, conflicts=conflicts,
        )

    @staticmethod
    def _line_claim(line: str) -> str:
        claim = _CITATION.sub("", line).strip()
        claim = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", claim)
        claim = re.sub(r"^\*\*(.+?)\*\*\s*", "", claim)
        claim = re.sub(r"^[:\s\"`'-]+", "", claim)
        claim = re.sub(r"[:\s\"`'.]+$", "", claim)
        if claim.startswith("|"):
            cells = [cell.strip() for cell in claim.split("|") if cell.strip()]
            claim = cells[1] if len(cells) > 1 else claim
        if ": " in claim and claim.startswith("**"):
            claim = claim.split(": ", 1)[1]
        if " — " in claim:
            claim = claim.split(" — ", 1)[1]
        claim = re.sub(r"^[:\s\"`'-]+", "", claim)
        claim = re.sub(r"[:\s\"`'.]+$", "", claim)
        return claim.strip(" *`\"'")

    @staticmethod
    def _find_conflicts(facts: list[ExtractedFact], important_terms: list[str]) -> list[dict]:
        relevant = []
        query_terms = {term.casefold() for term in important_terms}
        for fact in facts:
            if fact.fact_type not in {"metric", "numerical_value", "definition", "method"}:
                continue
            text = _norm(fact.supporting_passage)
            if query_terms and not any(term in text for term in query_terms):
                continue
            metric = _METRIC.search(text)
            numeric = _NUMBER.search(text[metric.end():]) if metric else _NUMBER.search(text)
            if metric and numeric:
                relevant.append((metric.group(1).casefold(), numeric.group().strip(), text, fact))
        conflicts: list[dict] = []
        seen_pairs: set[tuple[str, str, str, str]] = set()
        for index, left in enumerate(relevant):
            for right in relevant[index + 1:]:
                if left[3].paper_id == right[3].paper_id or left[0] != right[0]:
                    continue
                # Different values for the same named metric are surfaced, never averaged.
                if left[1] != right[1]:
                    pair_key = (left[0], left[1], right[1], "numeric")
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    conflicts.append({
                        "claim_key": left[0], "values": [left[1], right[1]],
                        "source_ids": [left[3].source_id, right[3].source_id],
                        "note": "The papers may use different datasets or conditions; inspect both passages before treating this as a contradiction.",
                    })
                    break
                left_neg, right_neg = bool(_NEGATION.search(left[2])), bool(_NEGATION.search(right[2]))
                if left_neg != right_neg and left[2] != right[2]:
                    pair_key = (left[0], left[3].source_id, right[3].source_id, "opposing")
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        conflicts.append({"claim_key": left[0], "source_ids": [left[3].source_id, right[3].source_id], "note": "The passages use opposing language."})
        return conflicts
