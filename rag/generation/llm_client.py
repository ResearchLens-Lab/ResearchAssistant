"""
LLM client interfaces and implementations.
Includes MockGroundedLLMClient for deterministic local testing/CI
and OpenAILLMClient as the standard real LLM provider.
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import httpx

from rag.config.settings import settings

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """
    Abstract LLM client interface.
    """

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generates text completion for given system and user prompts.
        """
        pass


class MockGroundedLLMClient(BaseLLMClient):
    """
    Deterministic, offline LLM simulator designed for testing and offline local development.
    Extracts facts directly from supplied evidence blocks and synthesizes grounded answers
    with valid inline citations [S1], [S2].
    """

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        # Check if context has no evidence
        if "[NO RELEVANT EVIDENCE FOUND" in user_prompt:
            return "Based on the provided papers, there is insufficient evidence to answer this question."

        # Parse source blocks from user prompt: e.g. [S1] (Paper: paper_1, ...) \n text
        source_matches = re.findall(
            r"\[(S\d+)\]\s*\(([^)]+)\)\n(.*?)(?=\n\n---\n\n|\Z|\nQUESTION:|\nFOCUS AREA)",
            user_prompt,
            flags=re.DOTALL,
        )

        if not source_matches:
            # Check if any inline sources exist
            raw_sources = re.findall(r"\[(S\d+)\]", user_prompt)
            if not raw_sources:
                return "Based on the provided papers, there is insufficient evidence to answer this question."

        # Check task type
        is_summary = "summarize" in system_prompt.lower() or "summary" in user_prompt.lower()
        is_comparison = "compare" in system_prompt.lower() or "comparison" in user_prompt.lower()

        if is_summary:
            return self._generate_mock_summary(source_matches)
        elif is_comparison:
            return self._generate_mock_comparison(source_matches, user_prompt)
        else:
            return self._generate_mock_qa(source_matches, user_prompt)

    def _generate_mock_summary(self, source_matches: List[tuple]) -> str:
        s_tags = [f"[{s[0]}]" for s in source_matches] or ["[S1]"]
        first_tag = s_tags[0]
        second_tag = s_tags[1] if len(s_tags) > 1 else first_tag

        # Find key snippets
        overview_text = source_matches[0][2].strip().replace("\n", " ")[:200] if source_matches else "Research analysis of proposed methodology"

        return f"""### 1. Overview & Core Objective
The paper introduces a comprehensive framework focusing on {overview_text}... {first_tag}.

### 2. Problem Statement
The research addresses foundational challenges in existing approaches, specifically improving accuracy, scalability, and domain understanding {first_tag}.

### 3. Proposed Methodology & Architecture
The authors develop an evidence-grounded approach structured with modular pipeline components and specialized representations {first_tag, second_tag}.

### 4. Experimental Setup & Datasets
Evaluation is conducted on standard benchmark datasets using rigorous quantitative metrics {second_tag}.

### 5. Key Findings & Results
The empirical evaluation demonstrates notable performance gains and robustness compared to baseline methods {first_tag, second_tag}.

### 6. Limitations & Future Work
Identified limitations include computational constraints and potential extensions to broader multilingual domains {second_tag}.

### 7. Conclusion
The proposed framework provides a solid foundation for research assistance, showing high grounding faithfulness and practical utility {first_tag}."""

    def _generate_mock_comparison(self, source_matches: List[tuple], user_prompt: str) -> str:
        # Group source matches by paper
        papers: Dict[str, List[str]] = {}
        for tag, header, text in source_matches:
            paper_match = re.search(r"Paper:\s*([^\s,]+)", header)
            paper_id = paper_match.group(1) if paper_match else "Paper"
            if paper_id not in papers:
                papers[paper_id] = []
            papers[paper_id].append((tag, text.strip()[:150]))

        paper_names = list(papers.keys())
        p1 = paper_names[0] if paper_names else "Paper A"
        p2 = paper_names[1] if len(paper_names) > 1 else "Paper B"

        s1_tag = f"[{papers[p1][0][0]}]" if (p1 in papers and papers[p1]) else "[S1]"
        s2_tag = f"[{papers[p2][0][0]}]" if (p2 in papers and papers[p2]) else "[S2]"

        return f"""### 1. High-Level Comparison Summary
Comparing **{p1}** and **{p2}**, both systems tackle core research tasks but employ distinct architectural choices {s1_tag, s2_tag}.

### 2. Methodological Differences
- **{p1}** focuses on: {papers.get(p1, [(s1_tag, 'Structured RAG pipeline')])[0][1]}... {s1_tag}.
- **{p2}** focuses on: {papers.get(p2, [(s2_tag, 'Comparative knowledge mapping')])[0][1]}... {s2_tag}.

### 3. Datasets & Evaluation Metrics
Both papers evaluate on standard benchmark collections using accuracy, recall, and grounding metrics {s1_tag, s2_tag}.

### 4. Relative Strengths & Trade-offs
- **{p1}**: High retrieval precision and lower inference latency {s1_tag}.
- **{p2}**: Broader multi-paper relational coverage with higher analytical depth {s2_tag}.

### 5. Synthesis & Takeaways
The two approaches are complementary; combining {p1}'s structured retrieval with {p2}'s comparative exploration yields an effective research assistant architecture {s1_tag, s2_tag}."""

    def _generate_mock_qa(self, source_matches: List[tuple], user_prompt: str) -> str:
        # Extract question
        q_match = re.search(r"QUESTION:\s*(.*)", user_prompt, re.DOTALL)
        question = q_match.group(1).strip() if q_match else "the query"

        if not source_matches:
            return "Based on the provided papers, there is insufficient evidence to answer this question."

        # Extract top 2 source snippets
        top_tag, top_header, top_text = source_matches[0]
        clean_top_text = top_text.strip().replace("\n", " ")[:250]

        citations = [f"[{top_tag}]"]
        second_citation = ""
        if len(source_matches) > 1:
            second_tag, _, second_text = source_matches[1]
            clean_second_text = second_text.strip().replace("\n", " ")[:200]
            second_citation = f" Furthermore, the study emphasizes that {clean_second_text} [{second_tag}]."
            citations.append(f"[{second_tag}]")

        return f"Based on the research paper evidence, {clean_top_text} [{top_tag}].{second_citation}"


class OpenAILLMClient(BaseLLMClient):
    """
    OpenAI Chat Completion API Client.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.timeout = timeout or settings.llm_timeout_seconds

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("OpenAI API key is missing. Set LLM_API_KEY in environment or .env.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class LLMClientFactory:
    """
    Factory creating configured LLM client.
    """

    @staticmethod
    def get_client(
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> BaseLLMClient:
        prov = (provider or settings.llm_provider).lower()
        if prov == "openai":
            key = api_key or settings.llm_api_key
            model = model_name or settings.llm_model
            logger.info("Initializing OpenAILLMClient (model: %s)", model)
            return OpenAILLMClient(api_key=key, model=model)
        elif prov == "mock":
            logger.info("Initializing MockGroundedLLMClient")
            return MockGroundedLLMClient()
        else:
            logger.warning("Unknown LLM provider '%s', defaulting to MockGroundedLLMClient", prov)
            return MockGroundedLLMClient()
