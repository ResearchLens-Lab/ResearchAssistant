"""
Response parser for LLM outputs.
Extracts grounded text and identified inline citation tags ([S1], [S2], etc.).
"""

import re
from typing import List, Set, Tuple
from pydantic import BaseModel, Field


class ParsedResponse(BaseModel):
    raw_answer: str
    cleaned_answer: str
    cited_source_ids: List[str] = Field(default_factory=list)


class ResponseParser:
    """
    Parses LLM generation text and extracts citation markers.
    """

    CITATION_PATTERN = re.compile(
        r"\[(?:Source\s*)?(S\d+)(?:\s*,\s*(?:Source\s*)?(S\d+))*\]",
        re.IGNORECASE,
    )

    @classmethod
    def parse(cls, text: str) -> ParsedResponse:
        if not text:
            return ParsedResponse(
                raw_answer="",
                cleaned_answer="Insufficient evidence found in the indexed papers.",
                cited_source_ids=[],
            )

        # Extract cited IDs (e.g., S1, S2)
        cited_ids: Set[str] = set()
        for match in cls.CITATION_PATTERN.finditer(text):
            for group in match.groups():
                if group:
                    cited_ids.add(group.upper())

        # Also fallback regex matching any [S\d+]
        fallback_tags = re.findall(r"\[(S\d+)\]", text, re.IGNORECASE)
        for tag in fallback_tags:
            cited_ids.add(tag.upper())

        sorted_ids = sorted(list(cited_ids), key=lambda s: int(s[1:]) if s[1:].isdigit() else 999)

        return ParsedResponse(
            raw_answer=text,
            cleaned_answer=text.strip(),
            cited_source_ids=sorted_ids,
        )
