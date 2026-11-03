"""
Extractive Response Engine for Local-First RAG without Paid LLMs.
Implements honest, extractive, source-grounded answer generation.
Preserves exact document names, pages, locators, and citations [S1], [S2].
"""

import re
import unicodedata
import logging
from typing import List, Dict, Any, Optional, Tuple

from rag.retrieval.query import RetrievedSource
from rag.citations.citation_mapper import CitationMapper, SourceCitation
from rag.citations.source_tracker import SourceTracker
from rag.citations.citation_formatter import RAGResult

logger = logging.getLogger(__name__)

STOP_WORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll",
    "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me",
    "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd",
    "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "tell", "show", "give", "explain", "describe", "find",
})


class ExtractiveAnswerEngine:
    """
    Synthesizes extractive, source-grounded answers directly from retrieved evidence.
    Operates 100% locally with zero external API calls or hallucinations.
    """

    def __init__(self, min_relevance_threshold: float = 0.05):
        self.min_relevance_threshold = min_relevance_threshold

    @staticmethod
    def preprocess_query(query: str) -> Dict[str, Any]:
        """Normalize query, extract keywords, and detect intent."""
        normalized = unicodedata.normalize("NFKC", query).strip()
        tokens = re.findall(r"[a-z0-9][a-z0-9_-]{1,}", normalized.casefold())
        keywords = [t for t in tokens if t not in STOP_WORDS]
        numbers = re.findall(r"\b\d+(?:\.\d+)?%?\b", normalized)

        # Detect intent
        intent = "factoid"
        if any(term in normalized.casefold() for term in ["compare", "difference", "versus", "vs", "better", "faster"]):
            intent = "comparison"
        elif any(term in normalized.casefold() for term in ["summarize", "overview", "summary", "brief"]):
            intent = "summary"
        elif any(term in normalized.casefold() for term in ["how to", "procedure", "steps", "algorithm", "method"]):
            intent = "procedural"

        return {
            "query": normalized,
            "keywords": keywords,
            "numbers": numbers,
            "intent": intent,
        }

    @staticmethod
    def extract_salient_sentences(text: str, keywords: List[str], max_sentences: int = 2) -> List[Tuple[str, float]]:
        """Extract the most relevant sentences from a passage matching query keywords."""
        if not text.strip():
            return []

        # Split into sentences preserving punctuation
        raw_sentences = re.split(r"(?<=[.?!])\s+", text.strip())
        scored: List[Tuple[str, float]] = []

        keyword_set = set(keywords)
        for s in raw_sentences:
            s_clean = s.strip()
            if len(s_clean) < 15:
                continue
            s_words = set(re.findall(r"[a-z0-9][a-z0-9_-]{1,}", s_clean.casefold()))
            if not s_words:
                continue
            overlap = len(keyword_set.intersection(s_words))
            ratio = overlap / max(len(keyword_set), 1)
            # Give bonus for sentences containing numbers or technical tokens
            bonus = 0.1 if any(re.search(r"\b\d+(?:\.\d+)?%?\b", s_clean) for _ in [1]) else 0.0
            score = ratio + bonus
            if overlap > 0 or len(raw_sentences) == 1:
                scored.append((s_clean, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:max_sentences]

    def generate_extractive_answer(
        self,
        question: str,
        sources: List[RetrievedSource],
        selected_paper_ids: Optional[List[str]] = None,
        tracker: Optional[SourceTracker] = None,
    ) -> Dict[str, Any]:
        """
        Builds an extractive, grounded response with exact citations.
        """
        if not sources:
            return {
                "answer": "There is insufficient evidence in the selected documents to answer this question.",
                "sources": [],
                "answer_mode": "evidence_only",
                "is_abstention": True,
            }

        prep = self.preprocess_query(question)
        keywords = prep["keywords"]

        # Select top sources that match keywords or carry high retrieval rank
        relevant_sources: List[RetrievedSource] = []
        for src in sources:
            src_words = set(re.findall(r"[a-z0-9][a-z0-9_-]{1,}", src.text.casefold()))
            matches = len(set(keywords).intersection(src_words))
            if matches > 0 or src.score >= self.min_relevance_threshold:
                relevant_sources.append(src)

        if not relevant_sources:
            relevant_sources = sources[:1]

        # Extract salient sentences and build grounded narrative
        used_sources: List[RetrievedSource] = []
        evidence_blocks: List[str] = []
        top_salient: List[str] = []

        for src in relevant_sources:
            salient = self.extract_salient_sentences(src.text, keywords, max_sentences=2)
            if salient:
                used_sources.append(src)
                citation_tag = f"[{src.source_id}]"
                doc_title = src.filename or src.title or "Document"
                page_str = src.page_display or f"page {src.page_start}"
                locator_str = f" · {src.locator}" if src.locator and "passage" not in src.locator else ""

                sentences_text = " ".join(s[0] for s in salient)
                top_salient.append(f'"{sentences_text}" {citation_tag}')
                evidence_blocks.append(
                    f"**{doc_title}** ({page_str}{locator_str}):\n"
                    f'> "{src.text.strip()}" {citation_tag}'
                )

        if not used_sources:
            return {
                "answer": "There is insufficient evidence in the retrieved passages to answer this question.",
                "sources": [],
                "answer_mode": "evidence_only",
                "is_abstention": True,
            }

        # Build clean extractive synthesis
        core_answer = " ".join(top_salient)
        full_text = (
            f"**Extractive Evidence:**\n\n"
            f"{core_answer}\n\n"
            f"**Source Passages:**\n\n"
            + "\n\n".join(evidence_blocks)
        )

        return {
            "answer": full_text,
            "used_sources": used_sources,
            "answer_mode": "evidence_only",
            "is_abstention": False,
        }

