"""
Local Intelligence Service for ResearchLens.
Provides application-managed, CPU-friendly local language model inference
for grounded research synthesis using open-weight compact models (Qwen 0.8B–2B).
100% offline, zero cloud APIs, strict evidence grounding and citation validation.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from rag.config.settings import settings
from rag.generation.evidence_validator import EvidenceValidator, ValidatedAnswerPayload
from rag.intelligence.confidence_evaluator import ConfidenceLevel, ConfidenceReport
from rag.intelligence.query_analyzer import QueryUnderstanding, ResearchIntent
from rag.retrieval.query import RetrievedSource

logger = logging.getLogger(__name__)

# Single global lock for CPU inference so multiple requests don't thrash CPU cores.
_INFERENCE_SEMAPHORE = threading.BoundedSemaphore(1)


class LocalIntelligenceService:
    """Manages local model inference, structured prompting, and evidence-grounded synthesis."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        context_window: int = 2048,
        max_predict_tokens: int = 450,
    ):
        raw_url = base_url or os.getenv("OLLAMA_BASE_URL") or getattr(settings, "ollama_base_url", "http://127.0.0.1:11434")
        self.base_url = (raw_url or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL") or getattr(settings, "ollama_model", "qwen3.5:0.8b")
        if self.model in ("none", "", None):
            self.model = "qwen3.5:0.8b"
        self.timeout_seconds = timeout_seconds or float(os.getenv("LOCAL_MODEL_TIMEOUT", "12.0"))
        self.context_window = int(os.getenv("LOCAL_MODEL_CONTEXT_SIZE", str(context_window)))
        self.max_predict_tokens = int(os.getenv("LOCAL_MODEL_MAX_TOKENS", "300"))
        self.validator = EvidenceValidator()

    def is_available(self) -> bool:
        """Fast check whether local inference service is responsive."""
        try:
            with httpx.Client(timeout=1.5) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        """Returns health and status of local intelligence runtime."""
        state = {
            "service": "Local Intelligence Engine",
            "provider": "application_managed_ollama",
            "base_url": self.base_url,
            "model": self.model,
            "available": False,
            "model_installed": False,
            "context_window": self.context_window,
            "max_tokens": self.max_predict_tokens,
        }
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    state["available"] = True
                    models = resp.json().get("models", [])
                    state["model_installed"] = any(
                        m.get("name") == self.model or m.get("model") == self.model
                        for m in models if isinstance(m, dict)
                    )
        except Exception as exc:
            state["error"] = str(exc)
        return state

    def _build_system_prompt(self, intent: ResearchIntent) -> str:
        return (
            "You are a rigorous, academic research assistant for ResearchLens. "
            "Synthesize the provided document evidence passages into a clear, structured answer. "
            "STRICT GROUNDING RULES:\n"
            "1. Base your answer EXCLUSIVELY on the facts in the provided evidence passages.\n"
            "2. If the user asks for definitions, criteria, and strategies/types, cover ALL of them with dedicated sections.\n"
            "3. Group and explain the design strategies or concepts present across the evidence passages (such as Divide-and-Conquer, Greedy Method, Dynamic Programming, Backtracking, Branch-and-Bound, Approximation, etc.).\n"
            "4. Be concise: 1 to 2 sentences per section explanation and 1 to 2 key points per section.\n"
            "5. NEVER invent categories, authors, page numbers, or information not present in the evidence.\n"
            "6. Every section MUST include an 'evidence_ids' array referencing the exact source IDs (e.g. [\"S1\", \"S2\"]) supporting it.\n"
            "7. Do NOT output internal reasoning or thinking out loud. Output ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "answer_type": "classification | definition | comparison | explanation | synthesis",\n'
            '  "direct_answer": "Concise headline summary answering the question",\n'
            '  "introduction": "Optional introductory context grounded in sources",\n'
            '  "sections": [\n'
            "    {\n"
            '      "heading": "Clear section heading",\n'
            '      "explanation": "Concise explanation grounded in the cited evidence (1-2 sentences)",\n'
            '      "key_points": ["bullet 1", "bullet 2"],\n'
            '      "evidence_ids": ["S1"]\n'
            "    }\n"
            "  ],\n"
            '  "conclusion": "Brief concluding takeaway",\n'
            '  "coverage": "complete | partial",\n'
            '  "insufficient_evidence": false\n'
            "}\n"
            "Output raw JSON only. No markdown fences, no conversational preface."
        )

    def _build_user_prompt(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
    ) -> str:
        evidence_blocks = []
        for s in sources:
            doc_label = s.title or s.filename or "Document"
            text_snippet = s.text.strip()[:550]
            evidence_blocks.append(
                f"[{s.source_id}] (Document: {doc_label}, Page: {s.page_start}, Section: {s.section or 'Main'})\n"
                f"{text_snippet}"
            )
        evidence_text = "\n\n".join(evidence_blocks)
        return f"EVIDENCE PASSAGES:\n{evidence_text}\n\nQUESTION: {query.raw_query}"

    def synthesize(
        self,
        query: QueryUnderstanding,
        sources: List[RetrievedSource],
        confidence: ConfidenceReport,
        timeout: Optional[float] = None,
    ) -> Tuple[Optional[ValidatedAnswerPayload], Optional[str]]:
        """
        Executes local model inference and validates output.
        Returns:
            (payload, formatted_markdown) if successful, or (None, None) on failure/fallback.
        """
        if not sources or confidence.level == ConfidenceLevel.NOT_LOCATED:
            return None, None

        if not self.is_available():
            logger.info("Local intelligence service not reachable at %s", self.base_url)
            return None, None

        max_sources = 8 if getattr(query, "is_compound", False) or len(getattr(query, "facets", [])) > 2 else 5
        model_sources = sources[:max_sources] if len(sources) > max_sources else sources
        system_prompt = self._build_system_prompt(query.intent)
        user_prompt = self._build_user_prompt(query, model_sources)
        timeout_val = timeout or self.timeout_seconds

        acquired = _INFERENCE_SEMAPHORE.acquire(timeout=2.0)
        if not acquired:
            logger.warning("Local inference slot busy; falling back to deterministic composer.")
            return None, None

        try:
            started = time.perf_counter()
            with httpx.Client(timeout=timeout_val) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "options": {
                            "temperature": 0.1,
                            "num_predict": self.max_predict_tokens,
                            "num_ctx": self.context_window,
                        },
                        "think": False,
                        "stream": False,
                    },
                )
            duration = time.perf_counter() - started
            logger.info("Local inference completed in %.2fs (HTTP %s)", duration, response.status_code)

            if response.status_code != 200:
                logger.warning("Local inference returned HTTP %s: %s", response.status_code, response.text[:200])
                return None, None

            data = response.json()
            raw_content = data.get("message", {}).get("content", "").strip()
            if not raw_content:
                logger.warning("Local inference returned empty content.")
                return None, None

            # Validate against evidence
            is_valid, payload, reasons = self.validator.validate(raw_content, sources)
            if not is_valid or payload is None:
                logger.warning("Local model output failed validation: %s", reasons)
                return None, None

            if payload.insufficient_evidence:
                return payload, None

            formatted_markdown = self.validator.format_to_markdown(
                payload=payload,
                sources=sources,
                confidence=confidence,
                query_text=query.raw_query,
            )
            return payload, formatted_markdown

        except httpx.TimeoutException:
            logger.warning("Local model inference timed out after %.1fs", timeout_val)
            return None, None
        except Exception as exc:
            logger.warning("Local model inference failed (%s): %s", type(exc).__name__, exc)
            return None, None
        finally:
            _INFERENCE_SEMAPHORE.release()
