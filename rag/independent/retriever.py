"""Read-only SQLite BM25 + local TF-IDF retrieval with provenance preservation."""

import math
import hashlib
import re
import sqlite3
import unicodedata
from importlib.metadata import PackageNotFoundError, version
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rag.config.settings import settings
from rag.independent.models import QueryAnalysis, QuestionIntent
from rag.retrieval.query import RetrievedSource


class IndependentIndexUnavailable(RuntimeError):
    pass


def configured_lexical_collection_name() -> str:
    """Mirror collection naming using package metadata only; never load a model."""
    collection_name = settings.chroma_collection_name
    embedding_model = settings.embedding_model
    provider = settings.embedding_provider
    if provider == "fastembed":
        try:
            package_version = version("fastembed")
        except PackageNotFoundError:
            # Reuse a uniquely identifiable existing namespace from FTS metadata;
            # this permits reads when the FastEmbed package is not installed.
            lexical_path = Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3"
            if lexical_path.is_file():
                try:
                    uri = lexical_path.resolve().as_uri() + "?mode=ro"
                    connection = sqlite3.connect(uri, uri=True, timeout=5)
                    try:
                        names = [row[0] for row in connection.execute("SELECT DISTINCT collection_name FROM lexical_chunks")]
                    finally:
                        connection.close()
                    model_hint = "".join(c if c.isalnum() or c in "_-" else "_" for c in settings.embedding_model)
                    suffix = f"_chunkidv2_{settings.embedding_dimension}"
                    matches = [name for name in names if model_hint in name and "fastembed-" in name and name.endswith(suffix)]
                    if len(matches) == 1:
                        return matches[0]
                except sqlite3.Error:
                    pass
            # Old, non-namespaced indexes remain queryable without FastEmbed.
            return collection_name
        embedding_model = f"{embedding_model}@fastembed-{package_version}"
    if settings.chroma_namespace_by_embedding:
        safe_model = "".join(c if c.isalnum() or c in "_-" else "_" for c in f"{provider}_{embedding_model}_chunkidv2")
        suffix = f"_{safe_model}_{settings.embedding_dimension}"[-58:]
        collection_name = f"{collection_name[:63-len(suffix)]}{suffix}"
    return collection_name


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w]+", unicodedata.normalize("NFKC", text).casefold(), flags=re.UNICODE)


class IndependentRetriever:
    """Uses the existing synchronized lexical index without touching Chroma or BGE."""

    def __init__(self, db_path: str | Path | None = None, max_candidates: int = 1000,
                 collection_name: str | None = None):
        self.db_path = Path(db_path or (Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3"))
        self.max_candidates = max(20, min(max_candidates, 3000))
        self.collection_name = collection_name or configured_lexical_collection_name()

    def retrieve(self, analysis: Any = None, paper_ids: list[str] | None = None,
                 document_ids: list[str] | None = None, section_names: list[str] | None = None,
                 top_k: int = 8, owner_id: str | None = None, query: Any = None, **kwargs) -> tuple[list[RetrievedSource], dict[str, list[str]]]:
        if analysis is None and query is not None:
            analysis = query
        if not self.db_path.is_file():
            raise IndependentIndexUnavailable("The local SQLite FTS5 index is not present. Index a document through the current ingestion path first.")
        raw_terms = getattr(analysis, "expanded_terms", None) or getattr(analysis, "expansion_terms", None)
        if not raw_terms and hasattr(analysis, "primary_concept") and analysis.primary_concept:
            raw_terms = [analysis.primary_concept]
        terms = list(dict.fromkeys(raw_terms or []))[:32]
        if not terms:
            terms = ["finding", "method", "result", "conclusion", "table", "summary", "paper"]
        match_query = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
        constraints: list[str] = ["collection_name = ?"]
        values: list[Any] = [match_query, self.collection_name]
        if owner_id:
            constraints.append("owner_id = ?")
            values.append(owner_id)
        for column, selected in (("paper_id", paper_ids), ("document_id", document_ids)):
            if selected:
                constraints.append(f"{column} IN ({','.join('?' for _ in selected)})")
                values.extend(selected)
        if section_names:
            constraints.append(f"lower(section) IN ({','.join('lower(?)' for _ in section_names)})")
            values.extend(section_names)
        where = " AND ".join(["lexical_chunks MATCH ?", *constraints])
        sql = (
            "SELECT chunk_id, paper_id, document_id, section, page_start, page_end, title, filename, locator, text, "
            "bm25(lexical_chunks) AS lexical_score FROM lexical_chunks WHERE " + where +
            " ORDER BY lexical_score ASC, chunk_id ASC LIMIT ?"
        )
        values.append(self.max_candidates)
        try:
            uri = self.db_path.resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=10.0)
            try:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(sql, values).fetchall()
                if analysis.intent == QuestionIntent.AUTHOR_LOOKUP:
                    # Author questions often target a title page whose text has
                    # names but no literal "author" keyword. Inspect only early
                    # pages/explicit front-matter sections within selected scope.
                    author_constraints = ["collection_name = ?"]
                    author_values: list[Any] = [self.collection_name]
                    if owner_id:
                        author_constraints.append("owner_id = ?")
                        author_values.append(owner_id)
                    for column, selected in (("paper_id", paper_ids), ("document_id", document_ids)):
                        if selected:
                            author_constraints.append(f"{column} IN ({','.join('?' for _ in selected)})")
                            author_values.extend(selected)
                    if section_names:
                        author_constraints.append(f"lower(section) IN ({','.join('lower(?)' for _ in section_names)})")
                        author_values.extend(section_names)
                    front_filter = "(CAST(page_start AS INTEGER) BETWEEN 1 AND 8 OR lower(section) LIKE '%title%' OR lower(section) LIKE '%front matter%')"
                    author_where = " AND ".join([front_filter, *author_constraints])
                    extra_sql = (
                        "SELECT chunk_id, paper_id, document_id, section, page_start, page_end, title, filename, locator, text, "
                        "0.0 AS lexical_score FROM lexical_chunks WHERE " + author_where +
                        " ORDER BY CAST(page_start AS INTEGER), chunk_id LIMIT 200"
                    )
                    rows.extend(connection.execute(extra_sql, author_values).fetchall())
                if analysis.intent in {
                    QuestionIntent.SUMMARY,
                    QuestionIntent.DOCUMENT_SUMMARY,
                    QuestionIntent.TOPIC_COUNT_RANKING,
                    QuestionIntent.TOPIC_COVERAGE_ANALYSIS,
                    QuestionIntent.TOPIC_EXTRACTION,
                    QuestionIntent.SECTION_COMPARISON,
                    QuestionIntent.TABLE_SYNTHESIS,
                    QuestionIntent.CHART_SYNTHESIS,
                    QuestionIntent.DIAGRAM_SYNTHESIS,
                }:
                    # These modes need the full selected scope to build a complete
                    # outline, topic ranking, or visualization. Merge all in-scope chunks with
                    # lexical hits instead of limiting synthesis to top matches.
                    scope_constraints = ["collection_name = ?"]
                    scope_values: list[Any] = [self.collection_name]
                    if owner_id:
                        scope_constraints.append("owner_id = ?")
                        scope_values.append(owner_id)
                    for column, selected in (("paper_id", paper_ids), ("document_id", document_ids)):
                        if selected:
                            scope_constraints.append(f"{column} IN ({','.join('?' for _ in selected)})")
                            scope_values.extend(selected)
                    if section_names:
                        scope_constraints.append(f"lower(section) IN ({','.join('lower(?)' for _ in section_names)})")
                        scope_values.extend(section_names)
                    scope_where = " AND ".join(scope_constraints)
                    scope_sql = (
                        "SELECT chunk_id, paper_id, document_id, section, page_start, page_end, title, filename, locator, text, "
                        "0.0 AS lexical_score FROM lexical_chunks WHERE " + scope_where +
                        " ORDER BY CAST(page_start AS INTEGER), chunk_id LIMIT 200"
                    )
                    rows.extend(connection.execute(scope_sql, scope_values).fetchall())
            finally:
                connection.close()
        except sqlite3.OperationalError as exc:
            raise IndependentIndexUnavailable(f"The existing FTS5 index could not be queried read-only ({type(exc).__name__}).") from exc

        # A chunk can exist in multiple legacy embedding namespaces. Keep the
        # best lexical hit for each document-scoped chunk ID.
        unique: dict[tuple[str, str], sqlite3.Row] = {}
        seen_passages: set[tuple[str, str]] = set()
        for row in rows:
            if not row[0] or not row[1] or not row[2] or not row[9]:
                continue
            key = (str(row[2]), str(row[0]))
            normalized_passage = " ".join(str(row[9]).casefold().split())
            duplicate_key = (str(row[1]), hashlib.sha1(normalized_passage.encode("utf-8")).hexdigest())
            if duplicate_key in seen_passages:
                continue
            seen_passages.add(duplicate_key)
            unique.setdefault(key, row)
        candidates = list(unique.values())
        if not candidates:
            return [], {}

        bm25_rank = {(str(row[2]), str(row[0])): rank for rank, row in enumerate(candidates, start=1)}
        tfidf_scores = self._tfidf(candidates, terms)
        tfidf_order = sorted(tfidf_scores, key=lambda key: (-tfidf_scores[key], key[1]))
        tfidf_rank = {key: rank for rank, key in enumerate(tfidf_order, start=1)}
        fused: list[tuple[float, tuple[str, str], sqlite3.Row, list[str]]] = []
        question_terms = set(analysis.important_terms)
        for key, row in unique.items():
            body_tokens = set(_tokens(str(row[9])))
            title = str(row[6] or "")
            section = str(row[3] or "")
            title_hit = bool(question_terms.intersection(_tokens(title)))
            section_hit = self._section_signal(analysis.intent, section)
            if analysis.intent == QuestionIntent.AUTHOR_LOOKUP and row[4] is not None:
                section_hit = section_hit or int(row[4]) <= 8
            score = 1 / (60 + bm25_rank[key]) + 1 / (60 + tfidf_rank.get(key, len(candidates)))
            reasons = ["matched indexed passage terms"]
            if tfidf_scores.get(key, 0) > 0:
                reasons.append("TF-IDF overlap")
            if title_hit:
                score += 0.002
                reasons.append("document title matched a query term")
            if section_hit:
                score += 0.002
                reasons.append(f"section matched {analysis.intent.value.casefold()} intent")

            # Boost methodology passages when methodology is requested
            if analysis.intent == QuestionIntent.METHODOLOGY_EXTRACTION:
                if re.search(r"\b(?:research methodology|systematic literature review|methodology|experimental design)\b", str(row[9]), re.I):
                    score += 0.04
                    reasons.append("passage contains explicit research methodology / review design")

            # Boost direct definition copula sentences for definition queries
            if analysis.intent in {QuestionIntent.DEFINITION, QuestionIntent.DIRECT_DEFINITION}:
                for q_term in analysis.important_terms[:2]:
                    if re.search(rf"\b(?:an?|the)?\s*{re.escape(q_term)}\s+(?:is|are)\s+(?:an?|the|any|defined|a\s+|basically|used\s+to|a\s+way)\b", str(row[9]), re.I):
                        score += 0.04
                        reasons.append("passage contains explicit definition copula for target concept")
                        break
                    elif len(_tokens(q_term)) >= 2 and re.search(rf"\b{re.escape(q_term)}\b", str(row[9]), re.I):
                        score += 0.015
                        reasons.append(f"passage contains exact phrase '{q_term}'")

            # Boost results and findings for summary or table synthesis
            if analysis.intent in {QuestionIntent.SUMMARY, QuestionIntent.TABLE_SYNTHESIS}:
                if re.search(r"\b(?:results and discussion|findings|key results|threat detection)\b", str(row[9]), re.I):
                    score += 0.02
                    reasons.append("passage discusses research findings or results")

            # Downweight references and bibliography chunks for non-bibliographic queries
            is_ref = bool(re.search(r"\b(?:references|bibliography|works cited)\b", section, re.I)) or bool(re.search(r"^\s*\[\d+\]\s+[A-Z][\w\s.,-]+\(\d{4}\)", str(row[9])))
            if is_ref and analysis.intent not in {QuestionIntent.DATE_LOOKUP, QuestionIntent.AUTHOR_LOOKUP}:
                score *= 0.1
                reasons.append("downweighted bibliographic reference chunk")

            if analysis.intent == QuestionIntent.AUTHOR_LOOKUP and row[4] is not None and int(row[4]) <= 8:
                score += 0.02
                reasons.append("early-page title/front-matter candidate for author lookup")
            matched = question_terms.intersection(body_tokens)
            if matched:
                reasons.append("terms: " + ", ".join(sorted(matched)[:6]))
            fused.append((score, key, row, reasons))

        fused.sort(key=lambda item: (-item[0], item[2][0]))
        whole_scope_intent = analysis.intent in {
            QuestionIntent.SUMMARY,
            QuestionIntent.DOCUMENT_SUMMARY,
            QuestionIntent.TOPIC_COUNT_RANKING,
            QuestionIntent.TOPIC_COVERAGE_ANALYSIS,
            QuestionIntent.TOPIC_EXTRACTION,
            QuestionIntent.SECTION_COMPARISON,
            QuestionIntent.TABLE_SYNTHESIS,
            QuestionIntent.CHART_SYNTHESIS,
            QuestionIntent.DIAGRAM_SYNTHESIS,
        }
        if whole_scope_intent:
            fused.sort(key=lambda item: (
                str(item[2][2]),
                int(item[2][4]) if item[2][4] is not None else 0,
                int(item[2][5]) if item[2][5] is not None else 0,
                str(item[2][0]),
            ))
        source_limit = len(fused) if whole_scope_intent else top_k
        fused = self._balance_papers(fused, paper_ids, source_limit, analysis.intent)
        best = max((item[0] for item in fused), default=1.0) or 1.0
        sources: list[RetrievedSource] = []
        explanations: dict[str, list[str]] = {}
        for rank, (score, _key, row, reasons) in enumerate(fused[:source_limit], start=1):
            source = RetrievedSource(
                source_id=f"S{rank}", chunk_id=str(row[0]), paper_id=str(row[1]), document_id=str(row[2]),
                page_start=int(row[4]) if row[4] is not None else None,
                page_end=int(row[5]) if row[5] is not None else None,
                section=str(row[3] or "Main Content"), text=str(row[9]),
                score=round(score / best, 4), title=str(row[6] or "") or None,
                filename=str(row[7] or "") or None, locator=str(row[8] or "") or None,
            )
            sources.append(source)
            explanations[source.source_id] = reasons
        return sources, explanations

    @staticmethod
    def _tfidf(rows: list[sqlite3.Row], terms: list[str]) -> dict[tuple[str, str], float]:
        docs = {(str(row[2]), str(row[0])): Counter(_tokens(str(row[9]))) for row in rows}
        doc_freq: Counter[str] = Counter()
        for counts in docs.values():
            doc_freq.update(counts.keys())
        n_docs = max(len(docs), 1)
        vocab = set(terms)
        idf = {term: math.log((1 + n_docs) / (1 + doc_freq.get(term, 0))) + 1 for term in vocab}
        query_vec = {term: idf[term] for term in vocab}
        query_norm = math.sqrt(sum(weight * weight for weight in query_vec.values())) or 1.0
        output: dict[tuple[str, str], float] = {}
        for key, counts in docs.items():
            length = max(sum(counts.values()), 1)
            vector = {term: (1 + math.log(count)) * idf[term] for term, count in counts.items() if term in vocab and count}
            norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
            output[key] = sum(vector.get(term, 0.0) * query_vec[term] for term in vocab) / (norm * query_norm)
        return output

    @staticmethod
    def _section_signal(intent: QuestionIntent, section: str) -> bool:
        value = section.casefold()
        signals = {
            QuestionIntent.METHODOLOGY_EXTRACTION: ("method", "approach", "design", "algorithm"),
            QuestionIntent.DATASET_EXTRACTION: ("data", "corpus", "experiment", "evaluation"),
            QuestionIntent.METRIC_EXTRACTION: ("result", "evaluation", "experiment"),
            QuestionIntent.AUTHOR_LOOKUP: ("title", "front matter", "publication", "metadata"),
            QuestionIntent.DEFINITION: ("introduction", "definition", "overview", "basics", "background", "concept"),
            QuestionIntent.DIRECT_DEFINITION: ("introduction", "definition", "overview", "basics", "background", "concept"),
        }.get(intent, ())
        return any(signal in value for signal in signals)

    @staticmethod
    def _balance_papers(items, paper_ids, top_k: int, intent: QuestionIntent):
        if intent != QuestionIntent.COMPARISON or len(paper_ids or []) < 2:
            return items
        by_paper: dict[str, tuple] = {}
        for item in items:
            by_paper.setdefault(item[2][1], item)
        balanced = [by_paper[paper_id] for paper_id in paper_ids if paper_id in by_paper]
        chosen = {item[1] for item in balanced}
        balanced.extend(item for item in items if item[1] not in chosen)
        return balanced[:max(top_k, len(balanced))]
