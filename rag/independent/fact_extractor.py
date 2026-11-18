"""Conservative, provenance-preserving fact patterns for academic passages."""

import re
import unicodedata

from rag.independent.models import ExtractedFact
from rag.retrieval.query import RetrievedSource


_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_NUMBER = re.compile(
    r"(?<![\w])[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:%|percent(?:age)?|fps|ms|seconds?|minutes?|hours?|days?|years?|mb|gb|tb|kb|\$|€|£|°[cf]|cm|mm|km|m|kg|g|mg)\b",
    re.I,
)
_DATE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(?:19|20)\d{2}\b|\b(?:19|20)\d{2}\b", re.I)
_PERSON = re.compile(r"\b[A-Z][A-Za-z'’-]+(?:\s+[A-Z]\.)?\s+[A-Z][A-Za-z'’-]+\b")


def clean_academic_text(text: str) -> str:
    """Strip recurring journal banners, volume metadata, DOIs and URLs from academic text."""
    if not text:
        return ""
    text = re.sub(r"(?im)\bInternational\s+Journal\s+of\s+[^\n.,]+(?:\s+and\s+[^\n.,]+)?", " ", text)
    text = re.sub(r"(?im)\bVolume\s+\d+[\s\S]{1,60}?ISSN[^\n.,;]+", " ", text)
    text = re.sub(r"(?im)\bDOI:\s*10\.\d{4,9}/[^\s,;)]+", " ", text)
    text = re.sub(r"(?im)\bwww\.[a-z0-9\-]+\.[a-z]{2,}(?:/[^\s]*)?", " ", text)
    text = re.sub(r"(?im)\bhttps?://[^\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip(" \t\r\n.,;:")


class FactExtractor:
    """Extract exact values and sentences; ambiguous names remain flagged for review."""

    def extract(self, sources: list[RetrievedSource], important_terms: list[str] | None = None) -> list[ExtractedFact]:
        facts: list[ExtractedFact] = []
        seen: set[tuple[str, str, str]] = set()
        for source in sources:
            raw_text = unicodedata.normalize("NFKC", source.text or "")
            cleaned_text = clean_academic_text(raw_text)
            sentences = [_clean(part) for part in _SENTENCE.split(cleaned_text) if len(_clean(part)) >= 20]
            if source.title:
                self._add(facts, seen, source, "document_title", source.title, source.title,
                          "indexed_source_metadata", "metadata_record")
            for sentence in sentences:
                if self._matches(sentence, important_terms or []):
                    self._add(facts, seen, source, "evidence_sentence", sentence, sentence,
                              "question_term_sentence_overlap", "exact_source_sentence")
                if re.search(r"\b(?:is defined as|are defined as|means|refers to|defined to be|(?:an?|the)?\s*[\w\s-]{2,40}?\s+(?:is|are)\s+(?:an?|the|any|defined|a\s+|basically|used\s+to|a\s+way|a\s+collection|a\s+specialized|a\s+format))\b", sentence, re.I):
                    self._add(facts, seen, source, "definition", sentence, sentence,
                              "definition_copula_pattern", "exact_source_sentence")
                if re.search(r"\b(?:method(?:ology)?|approach|algorithm|procedure|technique|architecture|design)\b", sentence, re.I):
                    self._add(facts, seen, source, "method", sentence, sentence,
                              "method_term_context", "exact_source_sentence")
                if re.search(r"\b(?:dataset|data set|corpus|benchmark)\b", sentence, re.I):
                    self._add(facts, seen, source, "dataset", sentence, sentence,
                              "dataset_term_context", "exact_source_sentence")
                if re.search(r"\b(?:accuracy|precision|recall|f1(?:-score)?|bleu|auc|rmse|mae|score|metric|evaluation)\b", sentence, re.I):
                    self._add(facts, seen, source, "metric", sentence, sentence,
                              "metric_term_context", "exact_source_sentence")
                for match in _NUMBER.finditer(sentence):
                    value = _clean(match.group())
                    if re.search(r"\d", value):
                        self._add(facts, seen, source, "numerical_value", value, sentence,
                                  "number_and_unit_pattern", "exact_source_span")
                for match in _DATE.finditer(sentence):
                    value = _clean(match.group())
                    self._add(facts, seen, source, "date", value, sentence,
                              "calendar_date_or_year_pattern", "exact_source_span")

            for line in cleaned_text.splitlines():
                item = re.match(r"\s*(?:[-*•]|\d+[.)])\s+(.{8,})", line)
                if item:
                    value = _clean(item.group(1))
                    self._add(facts, seen, source, "list_item", value, _clean(line),
                              "explicit_bullet_or_numbered_line", "exact_source_line")

            self._extract_authors(raw_text, source, facts, seen)
        return facts

    @staticmethod
    def _matches(sentence: str, terms: list[str]) -> bool:
        words = set(re.findall(r"[\w]+", sentence.casefold()))
        return len(sentence) >= 30 and any(
            set(re.findall(r"[\w]+", term.casefold())).issubset(words)
            for term in terms if term
        )

    @staticmethod
    def _extract_authors(text, source, facts, seen):
        # 1. Authoritative metadata on source
        if getattr(source, "author_metadata", None):
            for author in source.author_metadata:
                if author and len(str(author).strip().split()) >= 2:
                    FactExtractor._add(facts, seen, source, "person_candidate", str(author).strip(),
                                      f"Author: {author}", "metadata_authors", "exact_source_sentence")

        explicit = re.search(r"(?i)\bauthors?\s*:\s*([^\n]{5,240})", text)
        candidates: list[str] = []
        method = "explicit_author_label"
        verification = "explicit_context_requires_human_review"
        if explicit:
            candidates = _PERSON.findall(explicit.group(1))
            excerpt = _clean(explicit.group(0))
        else:
            by_line = re.search(r"(?im)^\s*by\s+([^\n]{5,180})|\bwritten\s+by\s+([^\n]{5,180})", text)
            if by_line:
                candidates = _PERSON.findall(by_line.group(1) or by_line.group(2))
                excerpt = _clean(by_line.group(0))
                method = "title_page_byline_pattern"
                verification = "byline_pattern_requires_human_review"
            else:
                # Page 1 title block author cluster (e.g. journal articles where authors appear under title before abstract)
                if (source.page_start is None or source.page_start <= 1):
                    abstract_m = re.search(r"\bAbstract\b", text, re.I)
                    if abstract_m:
                        pre_abstract = text[:abstract_m.start()]
                        lines = [l.strip() for l in pre_abstract.splitlines() if l.strip()]
                        for line in lines[1:6]:
                            clean_line = re.sub(r"[\d,\*]+", " ", line)
                            found = _PERSON.findall(clean_line)
                            if 1 <= len(found) <= 6:
                                candidates.extend(found)
                                excerpt = _clean(line)
                                method = "title_page_author_block"
                                verification = "title_page_cluster_requires_human_review"
                                break

                # Many real title pages print a title and edition followed by
                # a typographic cluster of author names, without an "Authors:"
                # label. Restrict this fallback to the bounded title-page region.
                if not candidates:
                    edition = re.search(r"\b(?:first|second|third|fourth|fifth)\s+edition\b", text, re.I)
                    if source.page_start is None or source.page_start > 8 or not edition:
                        return
                    tail = text[edition.end():]
                    tail = re.split(r"\b(?:the\s+mit\s+press|published\s+by|isbn|copyright|all\s+rights\s+reserved)\b", tail, maxsplit=1, flags=re.I)[0][:280]
                    title_match = re.search(
                        r"([A-Z][A-Za-z'’-]+(?:\s+(?:[A-Z][A-Za-z'’-]+|of|to|for|the|and|in)){1,8})\s*$",
                        text[:edition.start()], re.I,
                    )
                    repeated_title = re.search(re.escape(title_match.group(1)), tail, re.I) if title_match else None
                    if repeated_title:
                        tail = tail[:repeated_title.start()]
                    candidates = _PERSON.findall(tail)
                    if len(candidates) < 2:
                        return
                    excerpt = _clean(tail)
                    method = "edition_page_author_cluster"
                    verification = "title_page_cluster_requires_human_review"
        # Keep only distinct person-like strings from an explicit bibliographic
        # label/byline. A name merely mentioned in prose is never an author fact.
        for person in dict.fromkeys(_clean(name) for name in candidates):
            if len(person.split()) >= 2:
                FactExtractor._add(facts, seen, source, "person_candidate", person, excerpt, method, verification)

    @staticmethod
    def _add(facts, seen, source, fact_type, value, excerpt, method, verification):
        value = _clean(value)
        excerpt = _clean(excerpt)
        key = (source.chunk_id, fact_type, value.casefold())
        if not value or key in seen:
            return
        seen.add(key)
        facts.append(ExtractedFact(
            fact_type=fact_type, value=value, source_id=source.source_id,
            paper_id=source.paper_id, document_id=source.document_id,
            source_filename=source.filename, physical_page=source.page_start,
            chunk_id=source.chunk_id, section=source.section,
            supporting_passage=excerpt, extraction_method=method,
            verification_status=verification,
        ))
