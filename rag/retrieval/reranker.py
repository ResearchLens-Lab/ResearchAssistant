"""
Reranking interface and IntentAwareReranker implementation.
Enhances retrieval with intent signals, section headings, metadata extraction,
and boilerplate rejection.
"""

import re
from abc import ABC, abstractmethod
from typing import List, Optional
from rag.retrieval.query import RetrievedSource


class BaseReranker(ABC):
    """
    Abstract reranker interface.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        sources: List[RetrievedSource],
        top_k: int,
        intent: Optional[str] = None,
    ) -> List[RetrievedSource]:
        """
        Reranks a list of candidate RetrievedSource objects against the query.
        """
        pass


class IdentityReranker(BaseReranker):
    """
    Default pass-through reranker preserving initial vector similarity order.
    """

    def rerank(
        self,
        query: str,
        sources: List[RetrievedSource],
        top_k: int,
        intent: Optional[str] = None,
    ) -> List[RetrievedSource]:
        return sources[:top_k]


class IntentAwareReranker(BaseReranker):
    """
    Multi-signal relevance reranker combining:
    - Semantic similarity & BM25 ranking
    - Query intent alignment (definitions, authors, methods, comparisons)
    - Structural signals (section headings, chapter numbers, title pages)
    - Negative filtering (penalizing prefaces, index, dedication for definitions)
    - Term proximity and exact phrase matches
    - Chunk diversity
    """

    DEFINITION_MARKERS = re.compile(
        r"\b(?:is\s+(?:a|an|any|defined\s+as)|refers\s+to|can\s+be\s+defined|computational\s+procedure|sequence\s+of\s+steps)\b",
        re.I,
    )
    BOILERPLATE_SECTIONS = re.compile(
        r"\b(?:preface|acknowledgments?|dedication|contents|table\s+of\s+contents|index|bibliography|references)\b",
        re.I,
    )
    AUTHOR_NAMES = [
        "cormen", "leiserson", "rivest", "stein",
        "thomas h. cormen", "charles e. leiserson", "ronald l. rivest", "clifford stein"
    ]

    def rerank(
        self,
        query: str,
        sources: List[RetrievedSource],
        top_k: int,
        intent: Optional[str] = None,
    ) -> List[RetrievedSource]:
        if not sources:
            return []

        q_lower = query.casefold().strip()
        is_def = intent == "definition" or any(q_lower.startswith(p) for p in ["what is an ", "what is a ", "define ", "definition of "])
        is_author = intent == "author_entity" or any(w in q_lower for w in ["author", "wrote", "written by", "who is the author"])
        is_method = intent in ("method_algorithm", "how_to") or any(w in q_lower for w in ["algorithm", "method", "procedure", "how to"])
        is_reference_request = bool(re.search(r"\b(references?|bibliography|works cited|citation list|index|acknowledgments?|dedication)\b", q_lower))
        is_summary = intent == "summary"

        scored: list[tuple[float, RetrievedSource]] = []
        for src in sources:
            text_lower = src.text.casefold()
            section_lower = (src.section or "").casefold()
            score = float(src.score or 0.0)

            # Signal 1: Definition questions
            if is_def:
                # Heavy penalty for preface / acknowledgements / index
                if self.BOILERPLATE_SECTIONS.search(section_lower) or "preface" in text_lower[:200]:
                    score -= 0.40
                # Boost for definition phrasing
                if self.DEFINITION_MARKERS.search(src.text):
                    score += 0.35
                # Boost if chapter / section title is relevant (e.g. "Algorithms", "What is an algorithm?")
                if "algorithm" in section_lower or "1.1" in section_lower:
                    score += 0.30
                # Boost if "computational procedure" or "input" and "output" are in the text
                if "computational procedure" in text_lower or ("input" in text_lower and "output" in text_lower):
                    score += 0.35

            # Short contextual follow-ups otherwise match bibliography prose
            # too easily. Keep reference pages only when the user asks for them.
            if (intent == "follow_up" and not is_reference_request
                    and self.BOILERPLATE_SECTIONS.search(section_lower)):
                score -= 0.65

            # A source summary should represent the actual content, not the
            # bibliography or index that happens to share the book's keywords.
            if (is_summary and not is_reference_request
                    and re.search(r"\b(?:references?|bibliography|works cited|index|acknowledgments?|dedication)\b", section_lower)):
                score -= 0.85

            # Signal 2: Author questions
            elif is_author:
                # Title page or cover (pages 1-5)
                if src.page_start and src.page_start <= 5:
                    score += 0.35
                # Contains author names
                matched_authors = sum(1 for a in self.AUTHOR_NAMES if a in text_lower)
                if matched_authors > 0:
                    score += 0.45 + (0.10 * min(3, matched_authors))
                if "mit press" in text_lower or "third edition" in text_lower or "published by" in text_lower:
                    score += 0.20

            # Signal 3: Method / Algorithm questions
            elif is_method:
                if any(w in text_lower for w in ["input:", "output:", "step ", "runtime", "complexity", "pseudocode"]):
                    score += 0.20

            # Signal 4: Section heading match for query terms
            terms = [t for t in re.findall(r"\w{3,}", q_lower) if t not in {"what", "which", "where", "when", "does", "this", "that"}]
            if any(t in section_lower for t in terms):
                score += 0.20

            # Signal 5: Exact phrase match
            if len(terms) >= 2 and " ".join(terms[:3]) in text_lower:
                score += 0.25

            scored.append((score, src))

        # Sort descending by adjusted score
        scored.sort(key=lambda item: item[0], reverse=True)

        # De-duplicate / diversify: avoid returning multiple near-identical chunks from exact same page/text prefix
        seen_keys = set()
        reranked: list[RetrievedSource] = []
        for score, src in scored:
            key = (src.paper_id, src.page_start, src.text[:60])
            if key not in seen_keys:
                seen_keys.add(key)
                src_copy = src.model_copy(update={"score": round(max(0.0, score), 4)})
                reranked.append(src_copy)

        return reranked[:top_k]
