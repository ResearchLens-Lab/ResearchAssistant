"""Sentence-Level Evidence Selector with MMR, Context Restoration, and Calibrated Validation.

Provides:
- Abbreviation-aware candidate sentence segmentation
- Term-weighted and position-aware sentence scoring
- Pure-Python TextRank graph centrality (Priority 6)
- Maximal Marginal Relevance (MMR) deduplication (Priority 1)
- Antecedent context restoration for dangling references (Priority 2)
- Document-order preservation
- Calibrated evidence sufficiency validation (Priority 3)
- Sequential prose step extraction (Priority 4)
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import List, Optional, Sequence, Set, Tuple

from rag.independent.fact_extractor import clean_academic_text, is_syntax_convention_noise
from rag.independent.models import CandidateSentence, QueryAnalysis, QuestionIntent
from rag.retrieval.query import RetrievedSource

# Common abbreviations that should not trigger a sentence split
_ABBREVIATIONS = (
    r"\b(?:e\.g|i\.e|et\s+al|vs|etc|fig|figs|sec|secs|ch|ref|refs|vol|vols|no|nos|p|pp|"
    r"dr|prof|mr|mrs|ms|approx|def|thm|thms|al|dept|univ|inc|corp|ltd)\."
)
_INITIALS = r"\b[A-Z]\."
_PLACEHOLDER = "@@DOT@@"

# Dangling references and anaphora openers
_DANGLING_ANAPHORA = re.compile(
    r"^(?:it|they|these|this|those|she|he)\b",
    re.IGNORECASE,
)
_DANGLING_DEMONSTRATIVE = re.compile(
    r"^(?:this|these|those|such)\s+(?:algorithm|procedure|method|approach|technique|model|"
    r"framework|protocol|process|step|finding|result|system|paper|study|architecture|pipeline)\b",
    re.IGNORECASE,
)
_DANGLING_CONNECTORS = re.compile(
    r"^(?:however|therefore|furthermore|moreover|consequently|in\s+addition|as\s+a\s+result|"
    r"similarly|in\s+contrast|specifically|additionally|meanwhile)\b",
    re.IGNORECASE,
)

# Definitional copulas and predicate markers
_COPULA_PATTERNS = re.compile(
    r"\b(?:is\s+defined\s+as|are\s+defined\s+as|is\s+any\s+well-defined|are\s+any\s+well-defined|"
    r"refers\s+to|means|can\s+be\s+defined\s+as|defined\s+to\s+be|is\s+thus|is\s+basically|"
    r"consists\s+of|is\s+an?\s+algorithm|is\s+a\s+computational|is\s+a\s+method|is\s+a\s+system)\b",
    re.IGNORECASE,
)

# Sequential step markers
_STEP_PATTERNS = re.compile(
    r"\b(?:first|second|third|fourth|fifth|finally|initially|subsequently|step\s+\d+|phase\s+\d+)\b",
    re.IGNORECASE,
)

# Limitation / challenge markers
_LIMITATION_PATTERNS = re.compile(
    r"\b(?:limitation|limitations|drawback|drawbacks|constraint|constraints|disadvantage|overhead|"
    r"degradation|bottleneck|trade-off|fails|vulnerability|vulnerabilities|risk|risks)\b",
    re.IGNORECASE,
)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\w]+", unicodedata.normalize("NFKC", text).casefold())


def _token_set(text: str) -> set[str]:
    return set(_tokenize(text))


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return intersection / union if union > 0 else 0.0


def extract_prose_steps(text: str) -> list[tuple[str, str]]:
    """
    Extracts sequential steps from prose text with markers like
    'first, ... second, ... third, ...', 'Phase 1: ...', 'Step 1: ...'.
    Returns list of (step_title, step_description).
    """
    if not text:
        return []

    # Check for ordinal prose markers (first, second, third, fourth, finally)
    ordinal_pattern = re.compile(
        r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|finally|lastly)\b\s*[,:]?\s*",
        re.IGNORECASE,
    )
    # Check for numbered phase/step markers: e.g. "Phase 1: ... Phase 2: ..."
    phase_pattern = re.compile(
        r"\b((?:phase|step)\s+\d+)\s*[:—–-]?\s*",
        re.IGNORECASE,
    )

    matches = list(ordinal_pattern.finditer(text))
    if len(matches) >= 2:
        steps = []
        for i, match in enumerate(matches):
            ordinal_word = match.group(1).capitalize()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            clause = text[start:end].strip(" ;,\n.")
            clause = re.sub(r"\s+(?:and|or|then)\s*$", "", clause, flags=re.I).strip(" ;,\n.")
            if len(clause) >= 10:
                words = clause.split()
                action_title = words[0].capitalize() if words and words[0].lower() not in {"the", "a", "an", "to", "of"} else ordinal_word
                steps.append((action_title, clause))
        if len(steps) >= 2:
            return steps

    matches = list(phase_pattern.finditer(text))
    if len(matches) >= 2:
        steps = []
        for i, match in enumerate(matches):
            phase_label = match.group(1).title()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            clause = text[start:end].strip(" ;,\n.")
            clause = re.sub(r"\s+(?:and|or|then)\s*$", "", clause, flags=re.I).strip(" ;,\n.")
            if len(clause) >= 10:
                steps.append((phase_label, clause))
        if len(steps) >= 2:
            return steps

    return []


def segment_into_sentences(text: str) -> list[str]:
    """Abbreviation-aware sentence segmenter with academic noise filtering."""
    if not text or not text.strip():
        return []

    raw_text = unicodedata.normalize("NFKC", text or "")
    lines = raw_text.splitlines()
    sentences = []

    def mask_dot(m):
        return m.group(0).replace(".", _PLACEHOLDER)

    for line in lines:
        cleaned_line = clean_academic_text(line).strip()
        if not cleaned_line:
            continue

        # Mask decimals, abbreviations, initials, and list markers
        masked = re.sub(r"\b\d+\.\d+\b", mask_dot, cleaned_line)
        masked = re.sub(r"(?:(?<=\s)|(?<=^))\d{1,4}\.", mask_dot, masked)
        masked = re.sub(r"\([a-zA-Z0-9]{1,4}\)\.?", mask_dot, masked)
        masked = re.sub(_INITIALS, mask_dot, masked)
        masked = re.sub(_ABBREVIATIONS, mask_dot, masked, flags=re.IGNORECASE)

        raw_parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'\[])", masked) if p.strip()]
        for p in raw_parts:
            restored = p.replace(_PLACEHOLDER, ".").strip()
            # Strip leading list markers or bullets: e.g. "1. ", "3.1 ", "- "
            p_clean = re.sub(r"^\s*(?:\d+(?:\.\d+)*\s+|[A-Z]\.\s+|[-*•]\s*)", "", restored).strip()
            if (
                len(p_clean) >= 15
                and not is_syntax_convention_noise(p_clean)
                and not re.search(r"\b(?:ISSN|DOI:|www\.|\.com|Volume\s+\d+)\b", p_clean, re.I)
                and not re.search(r"[|\[\]{}~]", p_clean)
                and not re.search(r"^\s*(?:table\s+of\s+contents|contents|index|preface)\b", p_clean, re.I)
            ):
                sentences.append(re.sub(r"\s+", " ", p_clean))
    return sentences


class SentenceSelector:
    """Extracts, scores, contextualizes, and deduplicates candidate sentences."""

    def __init__(self, mmr_lambda: float = 0.70, enable_textrank: bool = True):
        self.mmr_lambda = mmr_lambda
        self.enable_textrank = enable_textrank

    def extract_candidates(self, sources: Sequence[RetrievedSource]) -> list[CandidateSentence]:
        """Segments retrieved chunks into CandidateSentence records with chunk-relative offsets."""
        candidates = []
        for source in sources:
            sents = segment_into_sentences(source.text)
            for idx, sent_text in enumerate(sents):
                # Check for dangling reference
                is_anaphora = bool(_DANGLING_ANAPHORA.search(sent_text))
                is_demonstrative = bool(_DANGLING_DEMONSTRATIVE.search(sent_text))
                is_connector = bool(_DANGLING_CONNECTORS.search(sent_text))
                has_dangling = is_anaphora or is_demonstrative or is_connector

                preceding = None
                restored = sent_text
                if has_dangling and idx > 0:
                    prev_candidate = sents[idx - 1]
                    if len(prev_candidate) >= 25 and not prev_candidate.endswith("?"):
                        preceding = prev_candidate
                        # Merge antecedent with current sentence
                        restored = f"{prev_candidate} {sent_text}"

                c = CandidateSentence(
                    sentence_id=f"{source.source_id}_s{idx}",
                    text=sent_text,
                    source_id=source.source_id,
                    chunk_id=source.chunk_id,
                    paper_id=source.paper_id,
                    document_id=source.document_id,
                    page_start=source.page_start,
                    page_end=source.page_end,
                    section=source.section or "",
                    sentence_index=idx,
                    has_dangling_reference=has_dangling,
                    preceding_text=preceding,
                    restored_text=restored,
                )
                candidates.append(c)
        return candidates

    def compute_textrank(self, candidates: list[CandidateSentence], iterations: int = 15) -> dict[str, float]:
        """Pure-Python TextRank graph centrality scoring over candidate sentences."""
        n = len(candidates)
        if n < 2:
            return {c.sentence_id: 1.0 for c in candidates}

        token_sets = [_token_set(c.text) for c in candidates]
        # Build pairwise Jaccard similarity matrix
        weights = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                sim = _jaccard_similarity(token_sets[i], token_sets[j])
                weights[i][j] = sim
                weights[j][i] = sim

        row_sums = [sum(row) for row in weights]
        scores = [1.0 / n] * n
        d = 0.85

        for _ in range(iterations):
            new_scores = [0.0] * n
            for i in range(n):
                rank_sum = 0.0
                for j in range(n):
                    if i != j and row_sums[j] > 1e-9:
                        rank_sum += (weights[j][i] / row_sums[j]) * scores[j]
                new_scores[i] = (1.0 - d) / n + d * rank_sum
            scores = new_scores

        max_score = max(scores) if scores else 1.0
        return {
            candidates[i].sentence_id: (scores[i] / max_score if max_score > 0 else 0.5)
            for i in range(n)
        }

    def score_candidate(
        self,
        candidate: CandidateSentence,
        analysis: QueryAnalysis,
        source_score: float = 1.0,
        textrank_score: float = 0.5,
    ) -> float:
        """Scores a single candidate using term overlap, position, syntax priors, and chunk relevance."""
        text = candidate.text
        text_lower = text.casefold()
        tokens = _token_set(text)

        # Lexical scoring
        important_terms = [t.casefold() for t in analysis.important_terms]
        expanded_terms = [t.casefold() for t in analysis.expanded_terms]
        primary_concept = (
            getattr(analysis, "primary_phrase", "")
            or (analysis.important_terms[0] if analysis.important_terms else "")
        ).casefold()

        lexical_score = 0.0
        for term in important_terms:
            t_tokens = set(re.findall(r"[\w]+", term))
            if t_tokens and t_tokens.issubset(tokens):
                lexical_score += 2.5 if len(t_tokens) > 1 else 1.5

        for exp in expanded_terms:
            e_tokens = set(re.findall(r"[\w]+", exp))
            if e_tokens and e_tokens.issubset(tokens):
                lexical_score += 0.8

        # Positional and Grammatical Priors
        priors = 0.0

        # Position in chunk (first 2 sentences often contain thesis or definition)
        if candidate.sentence_index == 0:
            priors += 1.2
        elif candidate.sentence_index == 1:
            priors += 0.6

        # Subject-position bonus: does sentence start with primary concept?
        if primary_concept and primary_concept in text_lower:
            lexical_score += 2.0
            if re.match(rf"^\s*(?:in|for)?\s*(?:an?|the)?\s*{re.escape(primary_concept)}\b", text_lower):
                candidate.is_subject_position = True
                priors += 3.5

        # Copula / Definition pattern bonus
        if _COPULA_PATTERNS.search(text_lower):
            priors += 2.5

        # Step marker bonus
        if _STEP_PATTERNS.search(text_lower):
            if analysis.intent in (
                QuestionIntent.PROCEDURE,
                QuestionIntent.PROCEDURAL_QUESTION,
                QuestionIntent.METHODOLOGY_EXTRACTION,
            ):
                priors += 3.0
            else:
                priors += 0.5

        # Limitation marker bonus
        if _LIMITATION_PATTERNS.search(text_lower):
            if analysis.intent in (
                QuestionIntent.LIMITATIONS_EXTRACTION,
                QuestionIntent.RESEARCH_GAP_ANALYSIS,
            ):
                priors += 3.5
            else:
                priors += 0.5

        # Penalties for noise or incidental examples
        if re.match(r"^\s*(?:as\s+an?\s+example|for\s+example|for\s+instance|e\.g\.|example[:\s])", text_lower):
            priors -= 4.0
        if re.search(r"\b(?:declaration|prototype|syntax)\b", text_lower):
            priors -= 2.0

        # Optimal length weighting (50 - 280 characters is ideal for academic citation)
        length = len(text)
        if 50 <= length <= 280:
            priors += 1.0
        elif length < 35:
            priors -= 2.0
        elif length > 400:
            priors -= 1.0

        # Chunk score blending
        final_score = (
            0.55 * lexical_score
            + 0.20 * priors
            + 0.15 * (source_score * 5.0)
            + 0.10 * (textrank_score * 5.0 if self.enable_textrank else 0.0)
        )
        candidate.score = final_score
        candidate.lexical_score = lexical_score
        candidate.textrank_score = textrank_score
        return final_score

    def select_evidence_mmr(
        self,
        analysis: QueryAnalysis,
        sources: Sequence[RetrievedSource],
        limit: int = 5,
        required_terms: Optional[Sequence[str]] = None,
        preserve_document_order: bool = True,
    ) -> list[CandidateSentence]:
        """Selects top candidate sentences using Maximal Marginal Relevance (MMR) deduplication."""
        candidates = self.extract_candidates(sources)
        if not candidates:
            return []

        source_score_map = {s.source_id: (s.score or 1.0) for s in sources}

        # Compute TextRank centrality (capped at top candidates for sub-millisecond efficiency)
        if self.enable_textrank and len(candidates) > 60:
            # Pre-score lexically to select top 60 candidates for graph construction
            pre_scored = []
            for c in candidates:
                src_score = source_score_map.get(c.source_id, 1.0)
                score = self.score_candidate(c, analysis, source_score=src_score, textrank_score=0.5)
                pre_scored.append((score, c))
            pre_scored.sort(key=lambda x: -x[0])
            textrank_candidates = [c for _, c in pre_scored[:60]]
        else:
            textrank_candidates = candidates

        textrank_map = self.compute_textrank(textrank_candidates) if self.enable_textrank else {}

        # Filter and score candidates
        req_set = set(t.casefold() for t in required_terms) if required_terms else set()
        pool: list[CandidateSentence] = []
        for c in candidates:
            if req_set and not any(rt in c.text.casefold() or rt in c.restored_text.casefold() for rt in req_set):
                continue
            src_score = source_score_map.get(c.source_id, 1.0)
            tr_score = textrank_map.get(c.sentence_id, 0.5)
            self.score_candidate(c, analysis, source_score=src_score, textrank_score=tr_score)
            # Require positive lexical relevance when query terms exist
            if analysis.important_terms and c.lexical_score <= 0.0:
                continue
            if c.score > 0.0 or not analysis.important_terms:
                pool.append(c)

        if not pool:
            return []

        # Sort pool descending by score
        pool.sort(key=lambda item: (-item.score, item.source_id, item.sentence_index))

        # MMR Selection
        selected: list[CandidateSentence] = []
        selected_token_sets: list[set[str]] = []
        remaining = pool.copy()

        # Step 1: Pick the highest scoring candidate
        first = remaining.pop(0)
        selected.append(first)
        selected_token_sets.append(_token_set(first.text))

        # Step 2: Iteratively select candidates balancing relevance and diversity
        while len(selected) < limit and remaining:
            best_idx = -1
            best_mmr_score = -float("inf")

            for idx, candidate in enumerate(remaining):
                c_tokens = _token_set(candidate.text)
                max_sim = max(_jaccard_similarity(c_tokens, s_tokens) for s_tokens in selected_token_sets)

                # Hard rejection for near-identical duplicate sentences (Jaccard > 0.55)
                if max_sim > 0.55:
                    continue

                mmr_val = self.mmr_lambda * candidate.score - (1.0 - self.mmr_lambda) * (max_sim * 5.0)
                if mmr_val > best_mmr_score:
                    best_mmr_score = mmr_val
                    best_idx = idx

            if best_idx == -1:
                # No remaining candidate satisfies the diversity threshold
                break

            chosen = remaining.pop(best_idx)
            selected.append(chosen)
            selected_token_sets.append(_token_set(chosen.text))

        # Step 3: Document order preservation
        if preserve_document_order:
            selected.sort(
                key=lambda c: (
                    c.paper_id,
                    c.page_start or 0,
                    c.chunk_id,
                    c.sentence_index,
                )
            )

        return selected

    @staticmethod
    def check_evidence_sufficiency(
        analysis: QueryAnalysis,
        candidates: Sequence[CandidateSentence],
        min_coverage: float = 0.40,
    ) -> Tuple[bool, list[str]]:
        """Calibrated validation: verifies if candidate evidence covers core question terms."""
        if not candidates:
            return False, ["No candidate sentences were extracted from retrieved passages."]

        important = [t.casefold() for t in analysis.important_terms if len(t) > 2]
        if not important:
            return True, []

        all_text = " ".join(c.text.casefold() for c in candidates)
        missing_terms = [t for t in important if t not in all_text]

        coverage = (len(important) - len(missing_terms)) / len(important)
        max_score = max((c.score for c in candidates), default=0.0)

        # Insufficient if coverage is below threshold or max relevance score is too low
        if coverage < min_coverage or max_score < 1.0:
            return False, missing_terms

        return True, []
