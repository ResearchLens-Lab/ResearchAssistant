"""Configurable rules-based intent and query analysis; deliberately no model use."""

import re
import unicodedata
from collections import OrderedDict
from typing import Iterable

from rag.independent.models import QueryAnalysis, QuestionIntent


STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further
had has have having he her here hers herself him himself his how i if in into is it its itself
just me more most my myself no nor not of off on once only or other our ours ourselves out over
own same she should so some such than that the their theirs them themselves then there these they
this those through to too under until up very was we were what when where which while who whom why
will with would you your yours yourself yourselves explain tell show give find identify list
overview describe discuss information material document paper book topic research
""".split())


TERM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "algorithm": ("procedure", "computational procedure", "method", "pseudocode"),
    "author": ("written by", "authorship", "authors"),
    "methodology": ("method", "methods", "approach", "experimental design", "procedure"),
    "method": ("methodology", "approach", "procedure"),
    "dataset": ("corpus", "benchmark data", "data set"),
    "metric": ("measure", "evaluation measure", "score", "accuracy", "precision"),
    "evaluation": ("metric", "measure", "accuracy", "result"),
    "measure": ("metric", "accuracy", "precision", "score"),
    "result": ("finding", "outcome", "performance"),
    "finding": ("result", "outcome", "evidence"),
    "limitation": ("constraint", "caveat", "weakness", "threats to validity"),
    "advantage": ("benefit", "strength", "merit"),
    "disadvantage": ("drawback", "weakness", "limitation"),
    "definition": ("defined as", "refers to", "means"),
    "date": ("year", "published", "publication date"),
    "publication": ("published", "release date", "issued"),
    "appear": ("published", "issued", "released"),
    "strengths": ("advantage", "benefit"),
    "weakness": ("limitation", "drawback"),
    "weaknesses": ("limitation", "drawback"),
    "stated": ("reported", "described"),
    "shown": ("reported", "measured"),
    "table": ("findings", "results", "methods", "summary"),
}


INTENT_RULES: tuple[tuple[QuestionIntent, tuple[str, ...], tuple[str, ...]], ...] = (
    (QuestionIntent.TOPIC_COUNT_RANKING, (
        r"\bwhich\s+section\b.{0,40}\b(?:more|most|highest|greatest|largest|fewer|fewest|least|lowest)\b.{0,40}\b(?:syllabus|topics?|content|coverage|subtopics?)\b",
        r"\bwhich\s+section\s+(?:has|have|contains?)\s+(?:the\s+)?(?:most|more|highest|largest|maximum|least|fewest)\b",
        r"\b(?:rank|order|compare)\b.{0,30}\bsections?\b.{0,30}\b(?:topics?|syllabus|size|length)\b",
        r"\bsection\s+(?:with|having)\s+(?:the\s+)?(?:most|more|highest|maximum|least|fewest)\s+(?:topics?|syllabus)\b",
        r"\bhow\s+many\s+topics\s+(?:are\s+there\s+)?in\s+each\s+section\b",
        r"\bwhich\s+section\s+contains?\s+(?:the\s+)?(?:most|fewest|least|more)\s+(?:topics?|syllabus)\b",
        r"\btell\s+me\s+which\s+section\s+(?:has|have)\s+more\s+syllabus\s+or\s+topics\b",
    ), ("section ranking", "topic counts", "syllabus coverage", "evidence")),
    (QuestionIntent.TOPIC_EXTRACTION, (
        r"\bhow\s+many\s+(?:distinct\s+)?topics\s+(?:are\s+(?:there\s+)?)?in\s+section\s+([0-9IVXLCDM]+)\b",
        r"\b(?:list|extract|show|give)\s+(?:all\s+)?(?:the\s+)?topics\s+in\s+section\s+([0-9IVXLCDM]+)\b",
        r"\btopics?\s+in\s+section\s+([0-9IVXLCDM]+)\b",
        r"\bwhat\s+topics\s+does\s+section\s+([0-9IVXLCDM]+)\s+cover\b",
    ), ("section topics", "topic items", "syllabus")),
    (QuestionIntent.TOPIC_COVERAGE_ANALYSIS, (
        r"\b(?:syllabus|curriculum|topic)\s+coverage\b",
        r"\b(?:topic|syllabus)\s+distribution\b",
        r"\bdistribution\s+of\s+(?:the\s+)?(?:topics?|syllabus)\b",
        r"\bbreakdown\s+of\s+(?:the\s+)?(?:topics?|syllabus)\b",
        r"\bwhat\s+topics\s+(?:are\s+covered|does\s+this\s+cover)\b",
        r"\btopics?\s+covered\s+in\b",
        r"\b(?:extract|list|show)\s+(?:all\s+)?(?:the\s+)?syllabus\s+topics\b",
    ), ("syllabus coverage", "topic groups", "subtopics")),
    (QuestionIntent.SECTION_COMPARISON, (
        r"\bcompare\s+section\s+([0-9IVXLCDM]+)\s+and\s+section\s+([0-9IVXLCDM]+)\b",
        r"\bdifferences?\s+between\s+section\s+([0-9IVXLCDM]+)\s+and\s+section\s+([0-9IVXLCDM]+)\b",
    ), ("section comparison", "differences", "topics")),
    (QuestionIntent.SECTION_SUMMARY, (
        r"\bsummarize\s+section\s+([0-9IVXLCDM]+)\b",
        r"\bsection\s+([0-9IVXLCDM]+)\s+summary\b",
    ), ("section summary", "main topics", "evidence")),
    (QuestionIntent.DOCUMENT_COMPARISON, (
        r"\bcompare\s+(?:the\s+)?(?:methodolog(?:y|ies)|results?|findings?|approaches?)\s+of\s+(?:these|the)\s+(?:\w+\s+)?papers\b",
        r"\bcompare\s+these\s+(?:\d+\s+)?papers\b",
        r"\bcompare\s+paper\s+\w+\s+and\s+paper\s+\w+\b",
        r"\bcompare\s+across\s+two\s+documents\b",
    ), ("cross-paper comparison", "methods", "findings")),
    (QuestionIntent.DOCUMENT_SUMMARY, (
        r"^\s*(?:give\s+me\s+the\s+)?summary\s*\??$",
        r"\bsummarize\s+this\s+(?:syllabus|paper|document|book)\b",
    ), ("document summary", "overview", "findings")),
    (QuestionIntent.DEFINITION, (
        r"^\s*define\s+[A-Za-z0-9\s-]{2,60}\??$",
        r"\bdefinition\s+of\s+[A-Za-z0-9\s-]{2,60}\??$",
        r"\bwhat\s+is\s+meant\s+by\s+[A-Za-z0-9\s-]{2,60}\??$",
        r"^\s*what\s+(?:is|are)\s+(?:(?:an?|the)\s+)?([A-Za-z0-9\s-]{2,60})\??$",
    ), ("definition", "core concept", "meaning")),
    (QuestionIntent.PROCEDURAL_QUESTION, (
        r"\b(?:steps|process|workflow|procedure)\s+(?:to|of|for|in)\b",
        r"\bhow\s+to\b",
        r"\bstep-by-step\b",
        r"\bexplain\s+(?:the\s+)?steps\b",
    ), ("ordered steps", "conditions", "sources")),
    (QuestionIntent.CONCEPT_EXPLANATION, (
        r"\bexplain\s+(?:the\s+)?(?:concept\s+of\s+)?([A-Za-z0-9\s-]{2,60})\b",
    ), ("concept explanation", "principles", "evidence")),
    (QuestionIntent.NUMERICAL_RESULT_LOOKUP, (
        r"\b(?:reported|numerical)\s+results?\b",
        r"\bfind\s+(?:the\s+)?(?:source'?s\s+)?reported\s+numerical\s+results\b",
        r"\bwhat\s+are\s+the\s+numerical\s+results\b",
    ), ("numerical results", "metrics", "values", "units")),
    (QuestionIntent.RESEARCH_GAP_ANALYSIS, (
        r"\bresearch\s+gaps?\b",
        r"\bunexplored\s+areas?\b",
        r"\bfuture\s+directions?\b",
    ), ("research gaps", "open problems", "future work")),
    (QuestionIntent.CONTRADICTION_ANALYSIS, (
        r"\bcontradict(?:ion|ing|ory)?\b",
        r"\bconflicting\s+(?:claims|results|findings|evidence)\b",
    ), ("contradictions", "conflicts", "opposing findings")),
    (QuestionIntent.BIBLIOGRAPHIC_LOOKUP, (
        r"\bbibliograph(?:y|ic)\b",
        r"\bcitations?\s+list\b",
        r"\breferences?\s+list\b",
    ), ("bibliography", "references", "venue", "year")),
    (QuestionIntent.CHART_SYNTHESIS, (
        r"(?:^|\s)/(?:pie|chart)\b",
        r"\b(?:pie\s+chart|distribution\s+chart|pie\s+diagram|breakdown\s+chart|proportions?\s+chart)\b",
        r"\b(?:show|create|give|format|make)\b.{0,25}\b(?:pie\s+chart|chart\s+of|distribution\s+pie)\b",
    ), ("pie chart", "topic distribution", "proportions", "evidence")),
    (QuestionIntent.DIAGRAM_SYNTHESIS, (
        r"(?:^|\s)/(?:diagram|flowchart|flow)\b",
        r"\b(?:flowchart|process\s+diagram|flow\s+diagram|architecture\s+diagram|mermaid)\b",
        r"\b(?:show|create|give|format|make)\b.{0,25}\b(?:flowchart|flow\s+chart|diagram|process\s+flow)\b",
    ), ("flowchart", "process flow", "architecture", "evidence")),
    (QuestionIntent.TABLE_SYNTHESIS, (
        r"(?:^|\s)/(?:table|tabular)\b",
        r"\b(?:present|show|give|format|put|structure|display)\b.{0,30}\b(?:table|tabular|matrix|grid)\b",
        r"\b(?:in|as)\s+a\s+(?:concise\s+)?table\b",
        r"^\s*(?:use\s+a\s+)?table\s*$",
        r"\b(?:tabular\s+format|as\s+a\s+table)\b",
    ), ("table", "findings", "citations", "evidence")),
    (QuestionIntent.SIMPLIFIED_EXPLANATION, (
        r"\bexplain\s+in\s+simple\s+language\b",
        r"\bsimplif(?:y|ied)\b",
        r"\bin\s+plain\s+(?:english|terms)\b",
        r"\bfor\s+(?:beginners|non-experts)\b",
        r"\beasy\s+to\s+understand\b",
    ), ("simplified overview", "core concept", "intuitive explanation")),
    (QuestionIntent.DEEP_EXPLANATION, (
        r"\bexplain\s+in\s+(?:more\s+)?depth\b",
        r"\bdetailed\s+explanation\b",
        r"\belaborate\b",
        r"\bdeep\s+dive\b",
        r"\bcomprehensive\s+explanation\b",
    ), ("detailed explanation", "underlying mechanisms", "evidence")),
    (QuestionIntent.PRACTICAL_EXAMPLE, (
        r"\b(?:give|provide|show)\s+(?:a\s+)?practical\s+example\b",
        r"\bpractical\s+examples?\b",
        r"\bconcrete\s+example\b",
        r"\breal-world\s+example\b",
        r"\billustrat(?:e|ive)\s+example\b",
    ), ("concrete example", "application scenario", "passages")),
    (QuestionIntent.METHODOLOGY_EXTRACTION, (
        r"(?:^|\s)/(?:methods?|methodology)\b",
        r"\bmethodolog(?:y|ies)\b",
        r"\b(?:research|experimental|study)\s+design\b",
        r"\bwhat\s+(?:approach|method|methods|methodology)\s+did\b",
        r"\bhow\s+was\s+the\s+(?:research|study|experiment|review)\s+conducted\b",
        r"\bmethods?\s+used\b",
        r"\bsearch\s+strategy\b",
        r"\bdata\s+collection\b",
    ), ("methods", "design", "evidence")),
    (QuestionIntent.AUTHOR_LOOKUP, (
        r"\bwho\s+(?:is|are|were)\s+(?:the\s+)?author(?:s)?\b",
        r"\bwho\s+(?:wrote|authored|created|published)\b",
        r"\b(?:identify|list|find|name)\s+(?:the\s+)?(?:book'?s|paper'?s|document'?s)?\s*author(?:s)?\b",
        r"\bauthor(?:s)?\s+of\s+(?:this|the)\b",
        r"^\s*(?:the\s+)?author(?:s)?\s*\??$",
        r"\bwritten\s+by\b",
        r"\bauthorship\b",
    ), ("authors", "authorship")),
    (QuestionIntent.LIMITATIONS_EXTRACTION, (
        r"\b(?:reported\s+)?limitations?\b",
        r"\bthreats?\s+to\s+validity\b",
        r"\bweakness(?:es)?\b",
        r"\bboundaries?\s+and\s+limitations?\b",
        r"\bchallenges?\b",
        r"\bopen\s+(?:issues|problems|challenges)\b",
    ), ("limitations", "threats to validity", "scope")),
    (QuestionIntent.DATASET_EXTRACTION, (
        r"\bdatasets?\b",
        r"\bcorpora?\b",
        r"\bdata\s+sets?\b",
        r"\bbenchmark\s+data\b",
    ), ("datasets", "evidence")),
    (QuestionIntent.ALGORITHMS_EXTRACTION, (
        r"\b(?:extract|list|identify|find)\s+(?:the\s+)?(?:key\s+)?algorithms?\b",
        r"\balgorithms?\s+(?:used|proposed|presented|described)\b",
        r"\balgorithms?\s+and\s+methods?\b",
        r"\bpseudocode\b",
        r"\bcomputational\s+steps?\b",
        r"\bwhich\s+algorithms?\b",
    ), ("algorithms", "computational steps", "methods")),
    (QuestionIntent.SUMMARY, (
        r"(?:^|\s)/(?:summary|outline|curriculum|syllabus)\b",
        r"\bsummar(?:y|ize|ise|izing|ising)\b",
        r"^\s*overview\b",
        r"\bmain\s+(?:findings|themes|points|takeaways)\b",
        r"\bkey\s+findings\b",
        r"\bcore\s+findings\b",
    ), ("summary", "findings", "limitations")),
    (QuestionIntent.COMPARISON, (
        r"(?:^|\s)/(?:compare|diff)\b",
        r"\bcompare\b",
        r"\bcompar(?:e|ison|ing)\b",
        r"\bdifferences?\b",
        r"\bversus\b",
        r"\bvs\.?\b",
    ), ("comparison", "similarities", "differences")),
    (QuestionIntent.NUMERICAL_QUERY, (
        r"\bhow\s+many\b",
        r"\bhow\s+much\b",
        r"\bwhat\s+(?:is|are|was|were)\s+the\s+(?:value|score|rate|percentage|number|amount)\b",
        r"\bpercent(?:age)?\b",
        r"\b\d+(?:\.\d+)?\s*%",
    ), ("values", "units", "sources")),
    (QuestionIntent.METRIC_EXTRACTION, (
        r"\bmetrics?\b",
        r"\bevaluation\s+(?:measure|metric)s?\b",
        r"\b(?:precision|recall|accuracy|f1|bleu|auc|rmse|mae)\b",
    ), ("metrics", "values", "evidence")),
    (QuestionIntent.DATE_LOOKUP, (
        r"\bwhen\b",
        r"\bwhat\s+(?:year|date)\b",
        r"\bpublication\s+date\b",
        r"\bpublished\s+in\b",
        r"\bwhen\s+did\b",
    ), ("dates", "sources")),
    (QuestionIntent.DEFINITION, (
        r"\bdefine\b",
        r"\bdefinition\s+of\b",
        r"\bwhat\s+is\s+meant\s+by\b",
        r"^\s*what\s+(?:is|are)\s+(?:(?:an?|the)\s+)?[\w\s-]{1,50}\??$",
        r"\bwhat\s+(?:is|are)\s+(?:(?:an?|the)\s+)?[\w-]+\s*\??$",
    ), ("definition", "explanation", "key points", "sources")),
    (QuestionIntent.EXPLANATION, (
        r"\bexplain\b",
        r"\bdescribe\b",
        r"\bwhy\b",
        r"\bwhat\s+does\b",
        r"\bwhat\s+is\s+(?:the\s+)?role\s+of\b",
        r"\bhow\s+does\b",
        r"\bwhat\s+are\s+the\b",
    ), ("direct answer", "evidence", "explanation")),
    (QuestionIntent.PROCEDURAL_QUESTION, (
        r"\b(?:steps|process|workflow|procedure)\s+(?:to|of|for|in)\b",
        r"\bhow\s+to\b",
        r"\bstep-by-step\b",
        r"\bexplain\s+(?:the\s+)?steps\b",
    ), ("ordered steps", "conditions", "sources")),
    (QuestionIntent.EVIDENCE_LOOKUP, (
        r"\b(?:show|find|give|provide)\b.{0,24}\b(?:evidence|passages?|quotes?|citations?)\b",
        r"\bsupporting\s+(?:passages?|evidence)\b",
    ), ("excerpts", "source details")),
    (QuestionIntent.LIST_EXTRACTION, (
        r"\blist\b",
        r"\bwhich\s+(?:ones|items|papers|algorithms|authors|datasets|methods)\b",
        r"\bname\s+(?:the|all)\b",
    ), ("items", "sources")),
    (QuestionIntent.FACT_LOOKUP, (
        r"\bwho\b",
        r"\bwhich\b",
        r"\bwhat\b",
        r"\bidentify\b",
        r"\bfind\b",
    ), ("direct answer", "sources")),
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w]+(?:[-'][\w]+)*", unicodedata.normalize("NFKC", text).casefold(), flags=re.UNICODE)


def _entities(question: str) -> list[str]:
    found: OrderedDict[str, None] = OrderedDict()
    for match in re.findall(r"[\"“']([^\"”']{2,100})[\"”']", question):
        found.setdefault(match.strip(), None)
    for doi in re.findall(r"\b10\.\d{4,9}/[A-Za-z0-9._;()/:-]+", question, flags=re.I):
        found.setdefault(doi.rstrip(".,;"), None)
    for acronym in re.findall(r"\b[A-Z][A-Z0-9-]{1,}\b", question):
        found.setdefault(acronym, None)
    # Capture a user's explicit research topic phrase, not every capitalized word.
    topic = re.search(r"\b(?:about|on|related to|regarding|concerning)\s+(.+?)(?:\?|$)", question, re.I)
    if topic:
        phrase = re.sub(r"\b(?:please|in the selected documents|in these papers)\b", "", topic.group(1), flags=re.I).strip(" .")
        if len(_tokens(phrase)) >= 2:
            found.setdefault(phrase, None)
    return list(found)[:12]


def _expand(terms: Iterable[str]) -> list[str]:
    output: OrderedDict[str, None] = OrderedDict()
    for term in terms:
        if term in STOPWORDS or len(term) < 2:
            continue
        output.setdefault(term, None)
        for expansion in TERM_SYNONYMS.get(term, ()):
            for token in _tokens(expansion):
                if token not in STOPWORDS:
                    output.setdefault(token, None)
    return list(output)[:40]


class QuestionIntentClassifier:
    """Rule-driven question interpretation with explainable, testable signals."""

    def __init__(self, synonyms: dict[str, tuple[str, ...]] | None = None):
        self.synonyms = synonyms or TERM_SYNONYMS

    def classify(self, question: str, paper_ids: list[str] | None = None,
                 document_ids: list[str] | None = None,
                 conversation_context: str | None = None) -> QueryAnalysis:
        normalized = unicodedata.normalize("NFKC", question).strip()
        # Clean leading slash commands (e.g. /table, /pie, /flowchart) from the search query for retrieval
        stripped_slash = re.sub(r"^\s*/[a-z_]+\s*", "", normalized).strip()
        search_question = stripped_slash if stripped_slash else "summary overview main topics findings sections"

        # Resolve short follow-ups using the preceding substantive user topic.
        # Only rewrite the search query for retrieval; never corrupt the intent classification.
        is_followup = bool(re.search(
            r"\b(?:more|further|deeper|depth|example|simple|plain|summarize|table|tabular|limitations?|compare)\b",
            normalized, re.I
        )) and not bool(re.search(r"\b(?:what\s+is|what\s+are|define|who\s+wrote|who\s+is|author|methodology)\b", normalized, re.I))

        if conversation_context and is_followup:
            prior_users = re.findall(r"(?im)^\s*user\s*:\s*(.+)$", conversation_context)
            if prior_users:
                substantive_prior = [
                    u.strip() for u in prior_users
                    if not re.search(r"\b(?:table|concise|more depth|example|simple)\b", u, re.I)
                ]
                topic = substantive_prior[-1] if substantive_prior else prior_users[-1].strip()
                search_question = f"{topic} {normalized}"

        # Intent is determined strictly from the user's current question!
        lower = normalized.casefold()
        intent = QuestionIntent.UNKNOWN
        signals: list[str] = []
        answer_shape: list[str] = []
        for candidate, patterns, shape in INTENT_RULES:
            matches = [pattern for pattern in patterns if re.search(pattern, lower, re.I)]
            if matches:
                intent = candidate
                signals = matches
                answer_shape = list(shape)
                break

        concept_match = re.search(
            r"\b(?:what\s+(?:is|are|does|means?)|define|definition\s+of|meaning\s+of|explain|describe)\s+(?:(?:an?|the)\s+)?([A-Za-z0-9\s-]{2,50}?)(?:\s+(?:mean|is|are|defined)|\?|$)",
            search_question, re.I
        )
        concept_phrase = concept_match.group(1).strip() if concept_match else None

        tokens = _tokens(search_question)
        important = list(OrderedDict.fromkeys(
            token for token in tokens if token not in STOPWORDS and len(token) > 1
        ))[:30]
        if concept_phrase and len(_tokens(concept_phrase)) >= 2:
            clean_phrase = " ".join(_tokens(concept_phrase))
            if clean_phrase and clean_phrase not in important:
                important.insert(0, clean_phrase)

        # For generic research queries without topic keywords (e.g. "Use a table"),
        # provide core academic anchor terms so retrieval finds substantive passages.
        if len(important) < 2:
            anchor_terms = ["finding", "method", "result", "experiment", "model", "approach", "conclusion", "table"]
            important.extend([t for t in anchor_terms if t not in important])
            important = important[:15]

        # Extract primary phrase for multi-word concepts
        primary_phrase = ""
        q_clean = normalized.strip().rstrip(".").strip()
        # 1. Steps / procedure: e.g. "Explain the steps of Dijkstra's algorithm"
        m = re.search(r"\b(?:steps|process|procedure|workflow)\s+(?:of|for|to|in)\s+(?:(?:an?|the)\s+)?([A-Za-z0-9\s'-]{1,60}?)(?:\?|$)", q_clean, re.I)
        if m and len(m.group(1).strip()) >= 2:
            primary_phrase = m.group(1).strip()
        # 2. Properties / characteristics / types / advantages: e.g. "List the properties of a B-tree"
        if not primary_phrase:
            m = re.search(r"\b(?:properties|characteristics|features|types|advantages|disadvantages|applications|uses)\s+(?:of|for|in)\s+(?:(?:an?|the)\s+)?([A-Za-z0-9\s'-]{1,60}?)(?:\?|$)", q_clean, re.I)
            if m and len(m.group(1).strip()) >= 2:
                primary_phrase = m.group(1).strip()
        # 3. Compare X and Y
        if not primary_phrase:
            m = re.search(r"\bcompare\s+(?:(?:an?|the)\s+)?([A-Za-z0-9\s'-]{1,60}?)\s+and\s+(?:(?:an?|the)\s+)?([A-Za-z0-9\s'-]{1,60}?)(?:\?|$)", q_clean, re.I)
            if m:
                primary_phrase = f"{m.group(1).strip()} and {m.group(2).strip()}"
        # 4. Why is X required/needed/used: e.g. "Why is normalization required in DBMS?"
        if not primary_phrase:
            m = re.search(r"\bwhy\s+(?:is|are|do|does)\s+(?:(?:an?|the)\s+)?([A-Za-z0-9\s'-]{1,60}?)(?:\s+(?:required|needed|used|important|necessary)|\?|$)", q_clean, re.I)
            if m and len(m.group(1).strip()) >= 2:
                primary_phrase = m.group(1).strip()
        # 5. Definition / explanation
        if not primary_phrase:
            m = re.search(r"\b(?:what\s+(?:is|are|does|means?)|define|definition\s+of|meaning\s+of|explain(?:\s+the\s+concept\s+of|\s+how)?|describe)\s+(?:(?:an?|the)\s+)?([A-Za-z0-9\s'-]{1,60}?)(?:\s+(?:mean|is|are|defined|works|operates|functions|in\s+detail)|\?|$)", q_clean, re.I)
            if m and len(m.group(1).strip()) >= 2:
                primary_phrase = m.group(1).strip()

        # Ensure important_terms has the full phrase as first element (if multi-word)
        if primary_phrase and len(primary_phrase.split()) >= 2:
            clean_phrase = " ".join(_tokens(primary_phrase))
            if clean_phrase and clean_phrase not in important:
                important.insert(0, clean_phrase)

        self_terms = _expand_with(important, self.synonyms)
        filters: dict[str, object] = {}
        if paper_ids:
            filters["paper_ids"] = list(dict.fromkeys(paper_ids))
        if document_ids:
            filters["document_ids"] = list(dict.fromkeys(document_ids))
        year_mentions = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", search_question)]
        if year_mentions:
            filters["mentioned_years"] = year_mentions

        strategies = ["SQLite FTS5 BM25", "local TF-IDF", "reciprocal-rank fusion", "metadata signals", "deduplicate by document and chunk"]
        if intent in {QuestionIntent.AUTHOR_LOOKUP, QuestionIntent.DATE_LOOKUP}:
            strategies.insert(0, "bibliographic/title-page evidence preference")
        if intent == QuestionIntent.METHODOLOGY_EXTRACTION:
            strategies.insert(0, "methods-section preference")
        if intent == QuestionIntent.COMPARISON:
            strategies.insert(0, "balanced per-paper evidence selection")
        if intent == QuestionIntent.TABLE_SYNTHESIS:
            strategies.insert(0, "structured tabular synthesis")

        return QueryAnalysis(
            intent=intent,
            normalized_question=normalized,
            search_query=search_question,
            primary_phrase=primary_phrase,
            entities=_entities(search_question),
            important_terms=important,
            expanded_terms=self_terms,
            document_filters=filters,
            retrieval_strategy=strategies,
            expected_answer_structure=answer_shape or ["evidence summary", "source passages", "limitations"],
            intent_signals=signals,
        )


def _expand_with(terms: Iterable[str], synonyms: dict[str, tuple[str, ...]]) -> list[str]:
    output: OrderedDict[str, None] = OrderedDict()
    for term in terms:
        if term in STOPWORDS or len(term) < 2:
            continue
        output.setdefault(term, None)
        normalized = _normalize_term(term)
        if normalized != term:
            output.setdefault(normalized, None)
        for expanded in synonyms.get(term, ()):
            for token in _tokens(expanded):
                if token not in STOPWORDS:
                    output.setdefault(token, None)
        for expanded in synonyms.get(normalized, ()):
            for token in _tokens(expanded):
                if token not in STOPWORDS:
                    output.setdefault(token, None)
    return list(output)[:40]


def _normalize_term(term: str) -> str:
    """Small deterministic English inflection normalizer for FTS token matching."""
    if len(term) > 5 and term.endswith("ies"):
        return term[:-3] + "y"
    if len(term) > 4 and term.endswith("s") and not term.endswith(("ss", "us", "is")):
        return term[:-1]
    return term
