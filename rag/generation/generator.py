"""
Grounded response generator coordinating prompts, LLM client, and output parsing.
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field

from rag.generation.llm_client import BaseLLMClient, LLMClientFactory
from rag.generation.prompts import (
    RESEARCH_QA_SYSTEM_PROMPT,
    RESEARCH_QA_USER_TEMPLATE,
    SUMMARIZATION_SYSTEM_PROMPT,
    SUMMARIZATION_USER_TEMPLATE,
    COMPARISON_SYSTEM_PROMPT,
    COMPARISON_USER_TEMPLATE,
)
from rag.generation.response_parser import ResponseParser, ParsedResponse
from rag.context.context_builder import AssembledContext

logger = logging.getLogger(__name__)


class GenerationResult(BaseModel):
    answer: str
    parsed: ParsedResponse
    system_prompt: str
    user_prompt: str


class GroundedGenerator:
    """
    Generates grounded answers from assembled research context.
    """

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        self.llm_client = llm_client or LLMClientFactory.get_client()

    def generate_answer(
        self,
        question: str,
        context: AssembledContext,
        temperature: Optional[float] = None,
    ) -> GenerationResult:
        """
        Generates grounded Q&A answer.
        """
        system_prompt = RESEARCH_QA_SYSTEM_PROMPT
        user_prompt = RESEARCH_QA_USER_TEMPLATE.format(
            context=context.formatted_context,
            question=question,
        )

        raw_output = self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
        parsed = ResponseParser.parse(raw_output)

        return GenerationResult(
            answer=parsed.cleaned_answer,
            parsed=parsed,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def generate_summary(
        self,
        context: AssembledContext,
        temperature: Optional[float] = None,
    ) -> GenerationResult:
        """
        Generates structured research paper summary.
        """
        system_prompt = SUMMARIZATION_SYSTEM_PROMPT
        user_prompt = SUMMARIZATION_USER_TEMPLATE.format(
            context=context.formatted_context,
        )

        raw_output = self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
        parsed = ResponseParser.parse(raw_output)

        return GenerationResult(
            answer=parsed.cleaned_answer,
            parsed=parsed,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def generate_comparison(
        self,
        focus_area: str,
        context: AssembledContext,
        temperature: Optional[float] = None,
    ) -> GenerationResult:
        """
        Generates structured multi-paper comparison.
        """
        system_prompt = COMPARISON_SYSTEM_PROMPT
        user_prompt = COMPARISON_USER_TEMPLATE.format(
            context=context.formatted_context,
            question=focus_area or "Compare methodologies, datasets, and trade-offs.",
        )

        raw_output = self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
        parsed = ResponseParser.parse(raw_output)

        return GenerationResult(
            answer=parsed.cleaned_answer,
            parsed=parsed,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
