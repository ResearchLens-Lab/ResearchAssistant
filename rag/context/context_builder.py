"""
Context builder formatting retrieved passages into structured prompts for LLM grounding.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from rag.retrieval.query import RetrievedSource
from rag.context.context_selector import ContextSelector
from rag.context.context_limits import ContextLimitManager


class AssembledContext(BaseModel):
    formatted_context: str
    selected_sources: List[RetrievedSource]
    total_sources: int
    estimated_tokens: int


class ContextBuilder:
    """
    Constructs clean, annotated context blocks for the LLM generator.
    """

    def __init__(
        self,
        limit_manager: Optional[ContextLimitManager] = None,
        context_selector: Optional[ContextSelector] = None,
    ):
        self.limit_manager = limit_manager or ContextLimitManager()
        self.context_selector = context_selector or ContextSelector()

    def build_context(
        self,
        sources: List[RetrievedSource],
        target_paper_ids: Optional[List[str]] = None,
    ) -> AssembledContext:
        if not sources:
            return AssembledContext(
                formatted_context="[NO RELEVANT EVIDENCE FOUND IN INDEXED PAPERS]",
                selected_sources=[],
                total_sources=0,
                estimated_tokens=0,
            )

        # 1. Deduplicate
        deduped = self.context_selector.deduplicate(sources)

        # 2. Balance across papers if multi-paper
        if target_paper_ids and len(target_paper_ids) > 1:
            deduped = self.context_selector.balance_multi_paper(deduped, target_paper_ids)

        # 3. Fit to token budget
        fitted = self.limit_manager.fit_sources_to_budget(deduped)

        # 4. Format blocks with clear source markers
        blocks: List[str] = []
        for src in fitted:
            header = f"[{src.source_id}] (Paper: {src.paper_id}, {src.page_display}, Section: {src.section})"
            if src.title:
                header = f"[{src.source_id}] (Paper: {src.paper_id} - '{src.title}', {src.page_display}, Section: {src.section})"
            blocks.append(f"{header}\n{src.text.strip()}")

        formatted_text = "\n\n---\n\n".join(blocks)
        total_tokens = self.limit_manager.estimate_tokens(formatted_text)

        return AssembledContext(
            formatted_context=formatted_text,
            selected_sources=fitted,
            total_sources=len(fitted),
            estimated_tokens=total_tokens,
        )
