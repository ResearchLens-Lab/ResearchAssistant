"""
Token budgeting and context size limits.
"""

from typing import List
from rag.retrieval.query import RetrievedSource
from rag.config.settings import settings


class ContextLimitManager:
    """
    Ensures assembled context stays within target token thresholds.
    """

    def __init__(self, max_tokens: int = 3500):
        self.max_tokens = max_tokens or settings.context_max_tokens

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (approx 1.3 tokens per word)."""
        words = len(text.split())
        return int(words * 1.3) + 1

    def fit_sources_to_budget(self, sources: List[RetrievedSource]) -> List[RetrievedSource]:
        """
        Truncates list of sources to fit within max_tokens budget.
        """
        selected: List[RetrievedSource] = []
        accumulated_tokens = 0

        for source in sources:
            source_tokens = self.estimate_tokens(source.text)
            if accumulated_tokens + source_tokens > self.max_tokens and selected:
                # Stop if adding this source exceeds budget
                break
            selected.append(source)
            accumulated_tokens += source_tokens

        return selected
