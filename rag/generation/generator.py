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
from rag.config.settings import settings
from rag.generation.budgeted_client import BudgetedLLMClient

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
        provider = settings.llm_provider
        client = llm_client or LLMClientFactory.get_client()
        if provider == "mock" and settings.app_env != "testing" and llm_client is None:
            raise ValueError("The mock generation provider is only available in automated tests.")
        self.llm_client = (client if isinstance(client, BudgetedLLMClient) or provider == "mock"
                           or not isinstance(client, BaseLLMClient)
                           else BudgetedLLMClient(client, provider))

    def _generate(self, system_prompt, user_prompt, temperature=None, on_token=None):
        if on_token and self.llm_client.supports_streaming:
            parts = []
            for token in self.llm_client.generate_stream(system_prompt, user_prompt, temperature=temperature):
                if getattr(on_token, "is_cancelled", lambda: False)():
                    break
                parts.append(token)
                on_token({"type": "token", "text": token, "provisional": True})
            return "".join(parts)
        return self.llm_client.generate(system_prompt, user_prompt, temperature=temperature)

    def generate_answer(
        self,
        question: str,
        context: AssembledContext,
        temperature: Optional[float] = None,
        intent: str = "direct",
        on_token=None,
    ) -> GenerationResult:
        """
        Generates grounded Q&A answer.
        """
        system_prompt = RESEARCH_QA_SYSTEM_PROMPT
        format_instruction = ""
        if intent == "structured_extraction":
            format_instruction = "\nReturn a concise markdown table of requested fields and values. Cite each value in its row and mark absent values as not reported."
        elif intent == "gap_analysis":
            format_instruction = "\nSeparate directly reported findings, disagreements, and information absent from the retrieved passages. Do not call absence in retrieval a contradiction."
        elif intent == "multi_hop":
            format_instruction = "\nShow each reasoning step separately and cite the passage supporting that step. Identify any unsupported link."
        elif intent == "follow_up":
            format_instruction = (
                "\nThis is a continuation of the immediately preceding answer. Resolve the topic from the question, "
                "then stay strictly on that topic. Give a genuinely deeper explanation: define the key idea, explain "
                "how its parts relate, and use only details supported by the supplied passages. Cite each factual "
                "paragraph. Do not output a list of loosely related terms, chapter headings, or other algorithms. "
                "If the passages do not support more depth, say exactly what is and is not supported."
            )
        user_prompt = RESEARCH_QA_USER_TEMPLATE.format(
            context=context.formatted_context,
            question=question + format_instruction,
        )

        raw_output = self._generate(system_prompt, user_prompt, temperature, on_token)
        parsed = ResponseParser.parse(raw_output)

        return GenerationResult(
            answer=parsed.cleaned_answer,
            parsed=parsed,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def repair_answer(self, question: str, answer: str, issues: list[str], context: AssembledContext) -> str:
        """Perform one bounded evidence-only correction using the existing provider client."""
        prompt = (
            "TASK: REPAIR. Return a complete corrected answer in Markdown. Use only the evidence below. "
            "Keep only supported claims, correct values only when evidence establishes the correction, "
            "qualify partial conclusions, and preserve citations only in the form [S#] for supplied IDs. "
            "Do not add sources, assumptions, or commentary about hidden verification.\n"
            f"QUESTION: {question}\nINITIAL ANSWER:\n{answer[:12000]}\n"
            f"ISSUES TO FIX:\n{chr(10).join('- ' + issue[:400] for issue in issues[:12])}\n"
            f"AUTHORIZED EVIDENCE:\n{context.formatted_context[:20000]}"
        )
        return self.llm_client.generate(
            system_prompt="You revise research answers using only authorized source excerpts.",
            user_prompt=prompt,
            temperature=0,
            max_tokens=settings.llm_max_tokens,
        )

    def generate_summary(
        self,
        context: AssembledContext,
        focus: str = "Summarize the main ideas supported by these passages.",
        temperature: Optional[float] = None,
        on_token=None,
    ) -> GenerationResult:
        """
        Generates a concise, source-grounded summary matched to the supplied evidence.
        """
        system_prompt = SUMMARIZATION_SYSTEM_PROMPT
        user_prompt = SUMMARIZATION_USER_TEMPLATE.format(
            focus=focus,
            context=context.formatted_context,
        )

        raw_output = self._generate(system_prompt, user_prompt, temperature, on_token)
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
        on_token=None,
    ) -> GenerationResult:
        """
        Generates structured multi-paper comparison.
        """
        system_prompt = COMPARISON_SYSTEM_PROMPT
        user_prompt = COMPARISON_USER_TEMPLATE.format(
            context=context.formatted_context,
            question=focus_area or "Compare methodologies, datasets, and trade-offs.",
        )

        raw_output = self._generate(system_prompt, user_prompt, temperature, on_token)
        parsed = ResponseParser.parse(raw_output)

        return GenerationResult(
            answer=parsed.cleaned_answer,
            parsed=parsed,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
