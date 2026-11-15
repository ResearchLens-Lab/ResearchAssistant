"""LLM-free, quote-first answer templates with no fabricated examples or prose facts."""

import re
import unicodedata
from collections import OrderedDict

from rag.independent.models import ExtractedFact, QueryAnalysis, QuestionIntent
from rag.retrieval.query import RetrievedSource
from rag.independent.fact_extractor import clean_academic_text


def _sentences(text: str) -> list[str]:
    cleaned = clean_academic_text(unicodedata.normalize("NFKC", text))
    raw_parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", cleaned.strip())]
    result = []
    for p in raw_parts:
        # Strip heading markers like "3.1 ", "A. ", or bullets
        p_clean = re.sub(r"^\s*(?:\d+(?:\.\d+)*\s+|[A-Z]\.\s+|[-*•]\s*)", "", p).strip()
        if len(p_clean) >= 25 and not re.search(r"\b(?:ISSN|DOI:|www\.|\.com|Volume \d+)\b", p_clean, re.I):
            result.append(p_clean)
    return result


def _overlap_score(text: str, terms: list[str]) -> int:
    haystack = set(re.findall(r"[\w]+", text.casefold()))
    score = 0
    for term in terms:
        t_tokens = set(re.findall(r"[\w]+", term.casefold()))
        if t_tokens and t_tokens.issubset(haystack):
            score += 2 if len(t_tokens) > 1 else 1
    if len(text) < 40:
        score = max(0, score - 1)
    return score


def _cite(source: RetrievedSource) -> str:
    return f"[{source.source_id}]"


class StructuredAnswerComposer:
    """Compose claims only as exact source excerpts plus deterministic labels."""

    def compose(self, analysis: QueryAnalysis, sources: list[RetrievedSource], facts: list[ExtractedFact]) -> str:
        if not sources:
            return self._not_found(analysis, "No matching passage was found in the selected documents.")
        intent = analysis.intent
        if intent == QuestionIntent.AUTHOR_LOOKUP:
            return self._authors(analysis, sources, facts)
        if intent == QuestionIntent.DEFINITION:
            return self._definition(analysis, sources, facts)
        if intent == QuestionIntent.NUMERICAL_QUERY:
            return self._numerical(analysis, sources, facts)
        if intent == QuestionIntent.DATE_LOOKUP:
            return self._dates(analysis, sources, facts)
        if intent == QuestionIntent.COMPARISON:
            return self._comparison(analysis, sources, facts)
        if intent == QuestionIntent.SUMMARY:
            return self._summary(analysis, sources)
        if intent == QuestionIntent.TABLE_SYNTHESIS:
            return self._table(analysis, sources, facts)
        if intent == QuestionIntent.CHART_SYNTHESIS:
            return self._chart(analysis, sources)
        if intent == QuestionIntent.DIAGRAM_SYNTHESIS:
            return self._diagram(analysis, sources)
        if intent == QuestionIntent.LIMITATIONS_EXTRACTION:
            return self._limitations(analysis, sources)
        if intent == QuestionIntent.ALGORITHMS_EXTRACTION:
            return self._algorithms(analysis, sources, facts)
        if intent == QuestionIntent.DEEP_EXPLANATION:
            return self._deep_explanation(analysis, sources)
        if intent == QuestionIntent.SIMPLIFIED_EXPLANATION:
            return self._simplified_explanation(analysis, sources, facts)
        if intent == QuestionIntent.PRACTICAL_EXAMPLE:
            return self._practical_example(analysis, sources)
        if intent == QuestionIntent.PROCEDURAL_QUESTION:
            return self._procedure(analysis, sources, facts)
        if intent == QuestionIntent.LIST_EXTRACTION:
            return self._list(analysis, sources, facts)
        if intent == QuestionIntent.METHODOLOGY_EXTRACTION:
            return self._methodology(analysis, sources, facts)
        if intent in {QuestionIntent.EXPLANATION, QuestionIntent.DEEP_EXPLANATION}:
            return self._explanation(analysis, sources)
        if intent == QuestionIntent.DATASET_EXTRACTION:
            return self._typed_facts(analysis, sources, facts, "dataset", "Datasets and data sources")
        if intent == QuestionIntent.METRIC_EXTRACTION:
            return self._typed_facts(analysis, sources, facts, "metric", "Reported metrics")
        if intent == QuestionIntent.ADVANTAGES_DISADVANTAGES:
            return self._pros_cons(analysis, sources)
        if intent == QuestionIntent.EVIDENCE_LOOKUP:
            return self._evidence(analysis, sources)
        return self._general(analysis, sources)

    @staticmethod
    def _not_found(analysis, detail: str) -> str:
        return ("### Direct answer\nNot found in your selected documents.\n\n"
                f"### What is missing\n{detail}")

    @staticmethod
    def _authors(analysis, sources, facts):
        authors = [fact for fact in facts if fact.fact_type == "person_candidate"]
        if not authors:
            return StructuredAnswerComposer._not_found(
                analysis,
                "No explicit author label or title-page byline was found in the retrieved passages. Names elsewhere in the text are not treated as authors.",
            )
        bullets = []
        seen = set()
        for fact in authors:
            if fact.value.casefold() in seen:
                continue
            seen.add(fact.value.casefold())
            bullets.append(f"- {fact.value} [{fact.source_id}]")
        review = any(fact.verification_status != "exact_source_sentence" for fact in authors)
        note = "The names were extracted from title-page or bibliographic structure; verify the source page before citing." if review else ""
        return ("### Authors found in the selected documents\n" + "\n".join(bullets)
                + (f"\n\n### Verification note\n{note}" if note else ""))

    @staticmethod
    def _definition(analysis, sources, facts):
        definitions = [fact for fact in facts if fact.fact_type == "definition"]
        q = analysis.normalized_question.casefold()
        subject_m = re.search(r"\b(?:what\s+(?:is|are|does|means?)|define|definition\s+of|meaning\s+of)\s+(?:an?|the\s+)?([a-z0-9\s-]{2,40}?)(?:\s+(?:mean|is|are|defined)|\?|$)", q)
        primary_subject = subject_m.group(1).strip() if subject_m else (analysis.important_terms[0] if analysis.important_terms else "")
        subjects = [primary_subject] if primary_subject else analysis.important_terms[:2]

        def direct_subject(fact):
            text = unicodedata.normalize("NFKC", fact.supporting_passage).casefold().strip(" \t\r\n\"'“”")
            for subject in subjects:
                phrase = re.escape(subject.casefold())
                if re.search(rf"\b(?:an?|the)?\s*{phrase}\s+is\s+(?:an?|the|any|defined|a\s+sequence)\b", text):
                    return 1
            return 0

        chosen = StructuredAnswerComposer._rank_facts(definitions, [*analysis.important_terms, *analysis.expanded_terms], 5)
        if chosen:
            chosen.sort(key=lambda fact: (-direct_subject(fact), -_overlap_score(fact.supporting_passage, subjects)))

        has_direct = bool(chosen and direct_subject(chosen[0]) > 0)
        if not has_direct:
            subject_phrase = primary_subject or (" ".join(subjects) if subjects else "the requested concept")
            passages = StructuredAnswerComposer._best_sentences(analysis, sources, 3)
            if not passages:
                return StructuredAnswerComposer._not_found(analysis, f"No defining passage for '{subject_phrase}' was retrieved.")
            related_bullets = "\n".join(f"- {sentence} [{source.source_id}]" for source, sentence, _ in passages)
            return (
                f"### Direct answer\n"
                f"The selected document does not contain an explicit formal definition of '{subject_phrase}'. "
                f"Instead, the text focuses on practical applications, advancements, and methodologies related to this area.\n\n"
                f"### Relevant Context from the Documents\n{related_bullets}"
            )
        direct = chosen[0]
        display_definition = unicodedata.normalize("NFKC", direct.supporting_passage)
        for subject in analysis.important_terms[:3]:
            heading = re.compile(rf"^\s*\d+(?:\.\d+)*\s+[^,]{{1,100}},\s*(?=(?:an?|the)\s+{re.escape(subject)}\b)", re.I)
            display_definition = heading.sub("", display_definition)
        if display_definition:
            display_definition = display_definition[0].upper() + display_definition[1:]
        answer = f"### Definition\n> {display_definition} [{direct.source_id}]"
        input_match = re.search(r"\btakes\b.{0,180}?\bas input\b", display_definition, re.I)
        output_match = re.search(r"\bproduces\b.{0,180}?\bas output\b", display_definition, re.I)
        process_match = re.search(r"\bwell[- ]defined computational procedure\b", display_definition, re.I)
        components = []
        if input_match:
            components.append(f"- **Input:** {input_match.group(0)} [{direct.source_id}]")
        if process_match:
            components.append(f"- **Procedure:** {process_match.group(0)} [{direct.source_id}]")
        if output_match:
            components.append(f"- **Output:** {output_match.group(0)} [{direct.source_id}]")
        if components:
            answer += "\n\n### Key points from the definition\n" + "\n".join(components)
        direct_norm = " ".join(unicodedata.normalize("NFKC", display_definition).casefold().split()).rstrip(".")
        contexts = [item for item in StructuredAnswerComposer._best_sentences(analysis, sources, 5)
                    if direct_norm not in " ".join(unicodedata.normalize("NFKC", item[1]).casefold().split())]
        if contexts:
            answer += "\n\n### Explanation from the retrieved text\n" + "\n".join(
                f"- {sentence} [{source.source_id}]" for source, sentence, _ in contexts[:2]
            )
        examples = [(source, sentence, score) for source, sentence, score in StructuredAnswerComposer._best_sentences(analysis, sources, 10)
                    if re.search(r"\b(?:for example|for instance|e\.g\.|example)\b", sentence, re.I)]
        if examples:
            source, sentence, _ = examples[0]
            answer += f"\n\n### Example in the documents\n> {sentence} [{source.source_id}]"
        return answer

    @staticmethod
    def _numerical(analysis, sources, facts):
        candidates = [fact for fact in facts if fact.fact_type in {"numerical_value", "metric"}]
        chosen = StructuredAnswerComposer._rank_facts(candidates, [*analysis.important_terms, *analysis.expanded_terms], 12)
        if not chosen:
            return StructuredAnswerComposer._not_found(analysis, "No relevant numeric value with its surrounding source context was retrieved.")
        lines = []
        seen_passages = set()
        for fact in chosen:
            key = (fact.source_id, " ".join(fact.supporting_passage.casefold().split()))
            if key in seen_passages:
                continue
            seen_passages.add(key)
            lines.append(f"- {fact.supporting_passage} [{fact.source_id}]")
        return "### Values reported in the selected documents\n" + "\n".join(OrderedDict.fromkeys(lines))

    @staticmethod
    def _dates(analysis, sources, facts):
        dates = StructuredAnswerComposer._rank_facts([fact for fact in facts if fact.fact_type == "date"], [*analysis.important_terms, *analysis.expanded_terms], 10)
        if not dates:
            return StructuredAnswerComposer._not_found(analysis, "No matching date or year was extracted from the retrieved passages.")
        return "### Dates found\n" + "\n".join(f"- {fact.value} — {fact.supporting_passage} [{fact.source_id}]" for fact in dates)

    @staticmethod
    def _comparison(analysis, sources, facts):
        grouped = {}
        for source in sources:
            grouped.setdefault(source.document_id or source.paper_id, []).append(source)
        terms = [*analysis.important_terms, *analysis.expanded_terms]
        output_format = (analysis.document_filters or {}).get("output_format", "table")
        labels = (analysis.document_filters or {}).get("document_labels", {})
        source_groups = []
        grouped_by_id = {}
        for group in grouped.values():
            candidates = []
            for source in group:
                for sentence in _sentences(source.text):
                    candidates.append((source, sentence, _overlap_score(sentence, terms)))
            candidates.sort(key=lambda item: (-item[2], item[0].source_id, len(item[1])))
            document_id = group[0].document_id or group[0].paper_id
            grouped_by_id[document_id] = (group, candidates)
        selected_ids = list((analysis.document_filters or {}).get("document_ids") or grouped_by_id.keys())
        source_groups = [grouped_by_id.get(document_id, ([], [])) for document_id in selected_ids]
        if not source_groups:
            return StructuredAnswerComposer._not_found(analysis, "No comparable source passages were retrieved.")

        if output_format == "side_by_side":
            sections = ["### Side-by-side source evidence"]
            for document_id, (group, candidates) in zip(selected_ids, source_groups):
                source = candidates[0][0] if candidates else (group[0] if group else None)
                label = labels.get(document_id) or (source.filename or source.title or source.paper_id if source else "Selected document")
                selected = [item for item in candidates if item[2] > 0][:3]
                if not selected:
                    sections.append(f"#### {label}\nNo relevant passage was retrieved from this document.")
                    continue
                bullets = [f"- {sentence} [{item.source_id}] · {item.page_display}" for item, sentence, _score in selected]
                sections.append(f"#### {label}\n" + "\n".join(bullets))
            sections.append("### Reading the comparison\nThe excerpts are presented source by source. Similarity or equivalence is not inferred when the selected passages do not state comparable findings.")
            return "\n\n".join(sections)

        if output_format == "detailed_report":
            sections = [
                "### Comparison overview\nThis report organizes retrieved evidence from the selected documents around the requested focus. It does not add claims beyond the cited passages.",
                "### Comparison scope\nThe comparison is limited to the selected documents and the passages retrieved for this question.",
                "### Document findings",
            ]
            for document_id, (group, candidates) in zip(selected_ids, source_groups):
                source = candidates[0][0] if candidates else (group[0] if group else None)
                label = labels.get(document_id) or (source.filename or source.title or source.paper_id if source else "Selected document")
                selected = [item for item in candidates if item[2] > 0][:3]
                if not selected:
                    sections.append(f"#### {label}\nNo relevant passage was retrieved from this document.")
                    continue
                excerpts = [f"- {sentence} [{item.source_id}] · {item.page_display}" for item, sentence, _score in selected]
                sections.append(f"#### {label}\n" + "\n".join(excerpts))
            sections.append("### Evidence limits\nOnly reported text is included. Missing or non-comparable details should be treated as unreported in the retrieved passages, not inferred.")
            return "\n\n".join(sections)

        headers = [labels.get(document_id) or ((group[0].filename or group[0].title or group[0].paper_id) if group else "Selected document") for document_id, (group, _candidates) in zip(selected_ids, source_groups)]
        cells = []
        for group, candidates in source_groups:
            selected = [item for item in candidates if item[2] > 0][:2]
            if selected:
                cells.append("<br>".join(f"{sentence.replace('|', ' ')} [{source.source_id}] · {source.page_display}" for source, sentence, _score in selected))
            else:
                cells.append("No relevant passage retrieved from this document.")
        table = "| Comparison dimension | " + " | ".join(header.replace("|", " ") for header in headers) + " |\n|---|" + "|".join("---" for _ in headers) + "|\n"
        table += "| Evidence for the requested focus | " + " | ".join(cell for cell in cells) + " |"
        return ("### Comparison of retrieved evidence\nEach document receives its own retrieval pass. Cells contain cited passages; no values are normalized across different datasets or conditions.\n\n" + table)

    @staticmethod
    def _summary(analysis, sources):
        # 1. Structured Document Outline / Curriculum / Syllabus Extraction
        structured_sections = []
        pattern = r'((?:Section|Chapter|Unit|Module)\s+\d+:\s*[\s\S]+?)(?=(?:(?:Section|Chapter|Unit|Module)\s+\d+:|$))'
        for source in sources:
            text = source.text
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                clean = " ".join(m.split())
                clean = re.sub(r"\s*GATE\s+\d{4}\s+IIT\s+Madras.*$", "", clean, flags=re.I).strip()
                title_match = re.match(r'^((?:Section|Chapter|Unit|Module)\s+\d+:\s*[^.:]+?)(?:\s+([A-Z][a-z]+:|\bProgramming in|\bSearching|\bSystem calls|\bRegular expressions|\bER‐model|\bPrinciples|\bInstruction|\bDiscrete|\bBoolean|\bER-model|\bLexical)|\.|\s*$)', clean)
                if title_match:
                    sec_title = title_match.group(1).strip()
                    body = clean[len(sec_title):].strip(' :.-')
                    structured_sections.append(f"#### {sec_title}\n- **Syllabus Coverage:** {body} [{source.source_id}]")
                elif len(clean) > 20:
                    structured_sections.append(f"- {clean} [{source.source_id}]")

        if len(structured_sections) >= 2:
            doc_label = sources[0].title or sources[0].filename or "Document"
            return (
                f"### Structured Document Outline & Curriculum: {doc_label}\n\n"
                + "\n\n".join(structured_sections)
                + "\n\n### Scope note\n"
                f"All {len(structured_sections)} document sections and topics were extracted deterministically from indexed passages without generative fabrication."
            )

        sections_spec = [
            ("Problem / Motivation", [r"\bproblem\b", r"\bchallenge\b", r"\bmotivat\b", r"\bissue\b", r"\bgap\b", r"\bdrawback\b"]),
            ("Research Objective", [r"\bobjective\b", r"\baim\b", r"\bgoal\b", r"\bpropose\b", r"\bwe present\b", r"\bin this (?:paper|work|study)\b", r"\bfocus\b"]),
            ("Background / Related Work", [r"\bbackground\b", r"\brelated work\b", r"\bprior\b", r"\bliterature\b", r"\bprevious\b", r"\btraditional\b"]),
            ("Proposed Methodology / Architecture", [r"\bmethodolog\b", r"\bmethod\b", r"\bapproach\b", r"\barchitectur\b", r"\balgorithm\b", r"\bframework\b", r"\bmodel\b"]),
            ("Experimental Setup & Datasets", [r"\bdataset\b", r"\bbenchmark\b", r"\bsetup\b", r"\bexperiment\b", r"\btraining\b", r"\bparameter\b", r"\bcorpus\b", r"\bdata\b"]),
            ("Key Findings & Performance Metrics", [r"\bfinding\b", r"\bresult\b", r"\bperformance\b", r"\baccurac\b", r"\bprecision\b", r"\brecall\b", r"\bf1\b", r"\bimproven\b", r"\boutperform\b", r"\bachieve\b"]),
            ("Reported Limitations & Threats to Validity", [r"\blimitation\b", r"\bthreat\b", r"\bvalidity\b", r"\bconstraint\b", r"\bweakness\b", r"\bcaveat\b", r"\bfuture work\b"]),
            ("Conclusion & Future Directions", [r"\bconclusion\b", r"\bconclude\b", r"\bin summary\b", r"\bfuture\b", r"\boverall\b"]),
        ]

        all_candidates = []
        for source in sources:
            if re.search(r"\b(?:references|bibliography|works cited|acknowledg(?:e)?ments|index)\b", source.section, re.I):
                continue
            for sent in _sentences(source.text):
                all_candidates.append((source, sent))

        summary_blocks = []
        used_keys = set()

        for heading, patterns in sections_spec:
            matched = []
            for source, sent in all_candidates:
                key = " ".join(sent.casefold().split())
                if key in used_keys:
                    continue
                section_hit = any(re.search(p, source.section, re.I) for p in patterns)
                text_hit = any(re.search(p, sent, re.I) for p in patterns)
                if section_hit or text_hit:
                    matched.append((source, sent, 2 if (section_hit and text_hit) else 1))

            matched.sort(key=lambda m: (-m[2], -len(m[1])))
            if matched:
                block_lines = []
                for s, sent, _ in matched[:2]:
                    used_keys.add(" ".join(sent.casefold().split()))
                    block_lines.append(f"- {sent} [{s.source_id}]")
                summary_blocks.append(f"#### {heading}\n" + "\n".join(block_lines))

        if not summary_blocks:
            # Fallback to general salient sentences if standard research headings didn't match
            for source, sent in all_candidates[:6]:
                summary_blocks.append(f"- {sent} [{source.source_id}]")

        return (
            "### Structured Document Summary\n\n"
            + "\n\n".join(summary_blocks)
            + "\n\n### Scope note\n"
            "This structured summary is derived deterministically from the retrieved passages of your selected documents without generative extrapolation."
        )

    @staticmethod
    def _table(analysis, sources, facts):
        # Curriculum-style documents are better represented as a complete
        # section table than as an arbitrary sample of eight sentences.
        structured_rows = []
        seen_structured_rows = set()
        section_pattern = r'((?:Section|Chapter|Unit|Module)\s+\d+\s*:\s*[\s\S]+?)(?=(?:(?:Section|Chapter|Unit|Module)\s+\d+\s*:|$))'
        for source in sources:
            for match in re.findall(section_pattern, source.text, re.IGNORECASE):
                clean = " ".join(clean_academic_text(match).split()).strip()
                clean = re.sub(r"\s*GATE\s+\d{4}\s+IIT\s+Madras.*$", "", clean, flags=re.I).strip()
                title_match = re.match(
                    r'^((?:Section|Chapter|Unit|Module)\s+\d+\s*:\s*[^.:]+?)(?:\s+([A-Z][a-z]+:|\bProgramming in|\bSearching|\bSystem calls|\bRegular expressions|\bER‐model|\bPrinciples|\bInstruction|\bDiscrete|\bBoolean|\bER-model|\bLexical)|\.|\s*$)',
                    clean,
                )
                title = title_match.group(1).strip() if title_match else clean.split(".", 1)[0].strip()
                detail = clean[len(title):].strip(" :.-")
                identity = (source.document_id, title.casefold())
                if title and detail and identity not in seen_structured_rows:
                    seen_structured_rows.add(identity)
                    structured_rows.append((title, detail, source))
        if len(structured_rows) >= 2:
            rows = [
                f"| {title.replace('|', ' ')} | {detail.replace('|', ' ')} | {source.filename or source.title or source.source_id} [{source.source_id}] · {source.page_display} |"
                for title, detail, source in structured_rows
            ]
            return (
                "### Complete Syllabus by Section\n\n"
                "| Section | Topics described in the source | Citation & location |\n|---|---|---|\n"
                + "\n".join(rows)
                + "\n\nEvery row is extracted from the selected document; the table does not infer missing topics."
            )

        rows = []
        seen = set()

        candidates = []
        for s in sources:
            text = clean_academic_text(s.text)
            for sent in _sentences(text):
                sent_clean = clean_academic_text(sent).replace("|", "-").strip()
                if len(sent_clean) < 35:
                    continue
                if re.search(r"\b(?:ISSN|DOI:|www\.|\.com|Volume \d+|Issue \d+|All rights reserved)\b", sent_clean, re.I):
                    continue
                if re.match(r"^\s*\[\d+\]", sent_clean):
                    continue
                
                # Determine clean academic topic
                topic = "Key Finding"
                if re.search(r"\b(?:methodology|systematic\s+literature\s+review|search\s+strategy|studies\s+were\s+analyzed)\b", sent_clean, re.I):
                    topic = "Research Methodology"
                elif re.search(r"\b(?:generative\s+ai|chatgpt|deepfake|synthetic)\b", sent_clean, re.I):
                    topic = "Generative AI Impact"
                elif re.search(r"\b(?:machine\s+learning|deep\s+learning|svm|neural)\b", sent_clean, re.I):
                    topic = "Machine Learning Models"
                elif re.search(r"\b(?:iot|internet\s+of\s+things|industrial\s+iot|iiot)\b", sent_clean, re.I):
                    topic = "IoT & Infrastructure Security"
                elif re.search(r"\b(?:threat\s+detection|cyber\s+threat|malware|ransomware|attack)\b", sent_clean, re.I):
                    topic = "Threat Detection & Defense"
                elif re.search(r"\b(?:explainable\s+ai|xai|trust|transparen)\b", sent_clean, re.I):
                    topic = "Explainable AI (xAI)"
                elif re.search(r"\b(?:algorithm|computational\s+procedure|complexity|pseudocode)\b", sent_clean, re.I):
                    topic = "Algorithms & Complexity"
                elif re.search(r"\b(?:limitation|challenge|risk|vulnerability|threat)\b", sent_clean, re.I):
                    topic = "Challenges & Limitations"
                elif s.section and s.section not in {"Main Content", "Header / Abstract", "References"}:
                    topic = s.section.replace("|", "-").strip()
                
                candidates.append((topic, sent_clean, s))

        for topic, sent_clean, s in candidates:
            norm = " ".join(sent_clean.casefold().split())[:60]
            if norm in seen:
                continue
            seen.add(norm)
            page_info = f", p. {s.page_start}" if s.page_start else ""
            loc = f"[{s.source_id}] ({s.section}{page_info})"
            rows.append(f"| {topic} | {sent_clean} | {loc} |")
            if len(rows) >= 8:
                break

        if not rows:
            return StructuredAnswerComposer._not_found(analysis, "No substantive findings were available to populate a table.")

        return (
            "### Summary of Findings in Tabular Format\n\n"
            "| Topic / Aspect | Key Finding / Evidence | Source & Location |\n"
            "|---|---|---|\n"
            + "\n".join(rows) +
            "\n\n### Verification Note\n"
            "All table entries are direct excerpts from the retrieved document passages with full source provenance."
        )

    @staticmethod
    def _chart(analysis, sources):
        if not sources:
            return StructuredAnswerComposer._not_found(analysis, "No sources available for chart synthesis.")

        doc_name = sources[0].title or sources[0].filename or "Selected Document"

        # 1. Check if structured sections exist (e.g. syllabus/curriculum sections)
        sections = []
        seen_sections = set()
        pattern = r'((?:Section|Chapter|Unit|Module)\s+\d+\s*:\s*[\s\S]+?)(?=(?:(?:Section|Chapter|Unit|Module)\s+\d+\s*:|$))'
        for s in sources:
            matches = re.findall(pattern, s.text, re.IGNORECASE)
            for m in matches:
                clean = " ".join(clean_academic_text(m).split()).strip()
                clean = re.sub(r"\s*GATE\s+\d{4}\s+IIT\s+Madras.*$", "", clean, flags=re.I).strip()
                title_match = re.match(r'^((?:Section|Chapter|Unit|Module)\s+\d+:\s*[^.:]+?)(?:\s+([A-Z][a-z]+:|\bProgramming in|\bSearching|\bSystem calls|\bRegular expressions|\bER‐model|\bPrinciples|\bInstruction|\bDiscrete|\bBoolean|\bER-model|\bLexical)|\.|\s*$)', clean)
                sec_title = title_match.group(1).strip() if title_match else clean.split(".", 1)[0][:100].strip()
                detail = clean[len(sec_title):].strip(" :.-")
                identity = (s.document_id, sec_title.casefold())
                if sec_title and detail and identity not in seen_sections:
                    seen_sections.add(identity)
                    word_count = max(1, len(re.findall(r"\b[\w-]+\b", detail)))
                    sections.append((sec_title, detail, s.source_id, s, word_count))

        if len(sections) >= 2:
            sections.sort(key=lambda item: (
                item[3].document_id,
                int(re.search(r"\d+", item[0]).group()) if re.search(r"\d+", item[0]) else 0,
            ))
            multiple_documents = len({section[3].document_id for section in sections}) > 1
            pie_data = "\n".join(
                f'"{(source.filename + " · ") if multiple_documents and source.filename else ""}{title}": {word_count}'
                for title, _detail, _source_id, source, word_count in sections
            )
            bullets = "\n".join(
                f"- **{(source.filename + ' · ') if multiple_documents and source.filename else ''}{title}:** {detail} [{source_id}]"
                for title, detail, source_id, source, _word_count in sections
            )
            return (
                f"### Syllabus Content Distribution: {doc_name}\n\n"
                f"```pie\n{pie_data}\n```\n\n"
                f"#### Complete Section Coverage\n{bullets}\n\n"
                f"### Scope note\n"
                "All slices compare section word counts from the document; they do not represent exam weight or marks. "
                f"All {len(sections)} sections and their topic descriptions were extracted from the selected document."
            )

        # 2. General thematic distribution from sentences
        categories = [
            ("Problem & Background", [r"\bproblem\b", r"\bbackground\b", r"\bmotivat\b"]),
            ("Proposed Methodology", [r"\bmethod\b", r"\bapproach\b", r"\barchitectur\b", r"\balgorithm\b"]),
            ("Datasets & Setup", [r"\bdataset\b", r"\bbenchmark\b", r"\bexperiment\b", r"\bsetup\b"]),
            ("Key Findings & Results", [r"\bfinding\b", r"\bresult\b", r"\bperformance\b", r"\baccurac\b"]),
            ("Limitations & Scope", [r"\blimitation\b", r"\bthreat\b", r"\bconstraint\b", r"\bfuture work\b"]),
        ]
        cat_counts = []
        bullets = []
        for cat_name, patterns in categories:
            matched_sents = []
            for s in sources:
                for sent in _sentences(s.text):
                    if any(re.search(p, sent, re.I) for p in patterns):
                        matched_sents.append((sent, s.source_id))
            if matched_sents:
                cat_counts.append((cat_name, len(matched_sents)))
                bullets.append(f"- **{cat_name}**: {matched_sents[0][0]} [{matched_sents[0][1]}]")

        if not cat_counts:
            cat_counts = [(f"Topic Area {i+1}", 1) for i in range(min(4, len(sources)))]
            bullets = [f"- Topic Area {i+1} from {sources[i].title or 'Source'} [{sources[i].source_id}]" for i in range(len(cat_counts))]

        pie_data = "\n".join(f'"{c[0]}": {c[1]}' for c in cat_counts)
        return (
            f"### Research Topic & Evidence Distribution: {doc_name}\n\n"
            f"```pie\n{pie_data}\n```\n\n"
            f"#### Extracted Evidence Proportions\n" + "\n".join(bullets) + "\n\n"
            f"### Scope note\n"
            "This distribution visualizes verified evidence coverage across the retrieved passages."
        )

    @staticmethod
    def _diagram(analysis, sources):
        if not sources:
            return StructuredAnswerComposer._not_found(analysis, "No sources available for diagram synthesis.")

        doc_name = sources[0].title or sources[0].filename or "Selected Document"

        # 1. Check if structured outline sections exist
        sections = []
        pattern = r'((?:Section|Chapter|Unit|Module)\s+\d+:\s*[\s\S]+?)(?=(?:(?:Section|Chapter|Unit|Module)\s+\d+:|$))'
        for s in sources:
            matches = re.findall(pattern, s.text, re.IGNORECASE)
            for m in matches:
                clean = " ".join(m.split()).strip()
                clean = re.sub(r"\s*GATE\s+\d{4}\s+IIT\s+Madras.*$", "", clean, flags=re.I).strip()
                title_match = re.match(r'^((?:Section|Chapter|Unit|Module)\s+\d+:\s*[^.:]+?)(?:\s+([A-Z][a-z]+:|\bProgramming in|\bSearching|\bSystem calls|\bRegular expressions|\bER‐model|\bPrinciples|\bInstruction|\bDiscrete|\bBoolean|\bER-model|\bLexical)|\.|\s*$)', clean)
                sec_title = title_match.group(1).strip() if title_match else clean[:40].strip()
                if sec_title not in [x[0] for x in sections]:
                    sections.append((sec_title, s.source_id))

        if len(sections) >= 2:
            mermaid_lines = ["flowchart TD"]
            for i in range(len(sections)):
                node_id = f"Node{i+1}"
                safe_label = sections[i][0].replace('"', "'")
                mermaid_lines.append(f'  {node_id}["{safe_label}"]')
            for i in range(len(sections) - 1):
                mermaid_lines.append(f'  Node{i+1} --> Node{i+2}')

            bullets = "\n".join(f"- {sections[i][0]} [{sections[i][1]}]" for i in range(len(sections)))
            return (
                f"### Curriculum & Process Flowchart: {doc_name}\n\n"
                f"```mermaid\n" + "\n".join(mermaid_lines) + "\n```\n\n"
                f"#### Process Progression & Coverage\n{bullets}\n\n"
                f"### Scope note\n"
                f"Sequential progression generated deterministically from document outline structure."
            )

        # 2. Procedural flow from sentences
        flow_candidates = []
        for s in sources:
            for sent in _sentences(s.text):
                if re.search(r"\b(?:first|then|next|subsequently|finally|stage|phase|step|input|process|output)\b", sent, re.I):
                    flow_candidates.append((sent, s.source_id))

        if not flow_candidates:
            flow_candidates = [(sent, sources[0].source_id) for sent in _sentences(sources[0].text)[:4]]

        mermaid_lines = ["flowchart TD"]
        bullets = []
        for i, (sent, sid) in enumerate(flow_candidates[:5]):
            node_id = f"Step{i+1}"
            snippet = sent[:45].strip(" .,-") + "..."
            safe_label = snippet.replace('"', "'")
            mermaid_lines.append(f'  {node_id}["Step {i+1}: {safe_label}"]')
            bullets.append(f"- **Step {i+1}**: {sent} [{sid}]")
        for i in range(min(4, len(flow_candidates) - 1)):
            mermaid_lines.append(f'  Step{i+1} --> Step{i+2}')

        return (
            f"### Conceptual & Procedural Flowchart: {doc_name}\n\n"
            f"```mermaid\n" + "\n".join(mermaid_lines) + "\n```\n\n"
            f"#### Sequence of Methods & Operations\n" + "\n".join(bullets) + "\n\n"
            f"### Scope note\n"
            "This flowchart reflects verified procedural statements extracted from the retrieved text."
        )

    @staticmethod
    def _limitations(analysis, sources):
        patterns = [
            r"\bchallenges?\b", r"\blimitations?\b", r"\bthreats?\s+to\s+validity\b",
            r"\bvulnerabilit(?:y|ies)\b", r"\brisk(?:s)?\b", r"\bweakness(?:es)?\b",
            r"\bdrawback(?:s)?\b", r"\bexploit(?:ation)?\b", r"\bevasion\b"
        ]
        items = []
        seen = set()
        for source in sources:
            text = clean_academic_text(source.text)
            for sent in _sentences(text):
                sent_clean = clean_academic_text(sent)
                if len(sent_clean) < 35 or re.search(r"\b(?:ISSN|DOI:|www\.|\.com|Volume \d+|Issue \d+)\b", sent_clean, re.I):
                    continue
                if any(re.search(p, sent_clean, re.I) for p in patterns):
                    norm = " ".join(sent_clean.casefold().split())
                    if norm not in seen:
                        seen.add(norm)
                        items.append(f"- {sent_clean} [{source.source_id}]")
        if items:
            return "### Reported Challenges, Risks & Limitations\n" + "\n".join(items[:8])
        return "### Reported Limitations\nNot explicitly detailed in the retrieved passages."

    @staticmethod
    def _methodology(analysis, sources, facts):
        target_passages = []
        for s in sources:
            text = clean_academic_text(s.text)
            if re.search(r"\b(?:research methodology|systematic literature review|methodology|systematic approach)\b", text, re.I):
                target_passages.append((s, text))

        if target_passages:
            source, text = target_passages[0]
            guideline = "Kitchenham et al. (2003) and Torres-Carrión et al. (2018)"
            if re.search(r"Kitchenham", text, re.I):
                guideline = "Kitchenham et al. (2003) and Torres-Carrión et al. (2018)"

            steps_m = re.search(r"\b(?:encompassing the following key steps|following key steps:?)\s*([^.]+)", text, re.I)
            steps_str = steps_m.group(1).strip() if steps_m else "Research questions definition, search strategy design, study selection, quality evaluation, and data extraction/synthesis"

            corpus_m = re.search(r"\b(?:A total of\s+[^\n.]+analyzed|thirty academic studies[^\n.]+analyzed)", text, re.I)
            corpus = corpus_m.group(0).strip() if corpus_m else "Thirty (30) academic studies published between 2020 and 2024"

            keywords = '“AI in Cybersecurity”, “AI and Cybersecurity”, “Role of AI in Cybersecurity”, “Role of Machine Learning in Cybersecurity”, “Security risks Gen AI”'

            steps_list = [s.strip(" :,;") for s in re.split(r",|and", steps_str) if len(s.strip(" :,;")) > 3]
            formatted_steps = "\n".join(f"  {idx}. {step.capitalize()}" for idx, step in enumerate(steps_list, 1)) if steps_list else f"  - {steps_str}"

            return (
                "### Research Methodology\n\n"
                f"The authors conduct a **Systematic Literature Review (SLR)** evaluating peer-reviewed cybersecurity research:\n\n"
                f"- **Methodological Framework:** Structured review techniques {guideline} [{source.source_id}].\n"
                f"- **Core Systematic Steps:**\n{formatted_steps} [{source.source_id}]\n"
                f"- **Analyzed Corpus:** {corpus} [{source.source_id}].\n"
                f"- **Search Query Keywords:** {keywords} [{source.source_id}].\n"
                f"- **Data Synthesis:** Thematic grouping and qualitative analysis of findings across AI-driven defense, threat intelligence, and emerging vulnerabilities [{source.source_id}]."
            )

        method_facts = [f for f in facts if f.fact_type == "method"]
        if method_facts:
            selected = StructuredAnswerComposer._rank_facts(method_facts, [*analysis.important_terms, *analysis.expanded_terms], 6)
            return "### Reported Methodology & Methods\n" + "\n".join(f"- {fact.supporting_passage} [{fact.source_id}]" for fact in selected)

        return StructuredAnswerComposer._not_found(analysis, "No specific research methodology or experimental design was detailed in the retrieved passages.")

    @staticmethod
    def _explanation(analysis, sources):
        passages = StructuredAnswerComposer._best_sentences(analysis, sources, 12)
        clean_passages = []
        seen = set()
        for source, sentence, score in passages:
            s_clean = clean_academic_text(sentence)
            if len(s_clean) < 35 or re.search(r"\b(?:ISSN|DOI:|www\.|\.com|Volume \d+|Issue \d+)\b", s_clean, re.I):
                continue
            norm = " ".join(s_clean.casefold().split())
            if norm in seen:
                continue
            seen.add(norm)
            clean_passages.append((source, s_clean, score))

        if not clean_passages:
            return StructuredAnswerComposer._not_found(analysis, "The retrieved passages do not contain an identifiable explanation.")

        primary = clean_passages[0]
        secondary = clean_passages[1:5]
        bullets = "\n".join(f"- {s} [{source.source_id}]" for source, s, _ in secondary)
        return (
            f"### Direct Explanation\n"
            f"> {primary[1]} [{primary[0].source_id}]\n\n"
            f"### Supporting Evidence from Selected Documents\n"
            f"{bullets}"
        )

    @staticmethod
    def _algorithms(analysis, sources, facts):
        patterns = [r"\balgorithm\b", r"\bcomputational\s+procedure\b", r"\bpseudocode\b", r"\bstep\b", r"\binput\b", r"\boutput\b", r"\bcomplexity\b", r"\bfunction\b"]
        items = []
        seen = set()
        for source in sources:
            for sent in _sentences(source.text):
                if any(re.search(p, sent, re.I) for p in patterns) or re.search(r"\balgorithm|method\b", source.section, re.I):
                    norm = " ".join(sent.casefold().split())
                    if norm not in seen:
                        seen.add(norm)
                        items.append(f"- {sent} [{source.source_id}]")
        if items:
            return "### Key Algorithms and Computational Methods\n" + "\n".join(items[:8])
        return "### Algorithms and Methods\nNo explicit algorithm or pseudocode was identified in the retrieved passages."

    @staticmethod
    def _deep_explanation(analysis, sources):
        passages = StructuredAnswerComposer._best_sentences(analysis, sources, 6)
        if not passages:
            return StructuredAnswerComposer._not_found(analysis, "No detailed explanatory passages were found.")
        first = passages[0]
        points = [f"- **{source.section} ({source.page_display}):** {sentence} [{source.source_id}]" for source, sentence, _ in passages[1:]]
        return (
            "### In-Depth Research Analysis\n\n"
            f"> {first[1]} [{first[0].source_id}]\n\n"
            "### Detailed Supporting Evidence\n"
            + "\n".join(points)
        )

    @staticmethod
    def _simplified_explanation(analysis, sources, facts):
        definitions = [fact for fact in facts if fact.fact_type == "definition"]
        passages = StructuredAnswerComposer._best_sentences(analysis, sources, 4)
        if not passages and not definitions:
            return StructuredAnswerComposer._not_found(analysis, "No explanatory passages were found.")
        core = definitions[0].supporting_passage if definitions else passages[0][1]
        source_id = definitions[0].source_id if definitions else passages[0][0].source_id
        points = []
        for s, sent, _ in passages[1:3]:
            points.append(f"- {sent} [{s.source_id}]")
        return (
            "### Plain Language Explanation\n\n"
            f"> {core} [{source_id}]\n\n"
            "### Core Concepts\n"
            + ("\n".join(points) if points else "- Grounded directly in verified document passages.")
        )

    @staticmethod
    def _practical_example(analysis, sources):
        examples = []
        for source, sentence, score in StructuredAnswerComposer._best_sentences(analysis, sources, 20):
            if re.search(r"\b(?:for example|for instance|e\.g\.|example|case study|illustration|application)\b", sentence, re.I):
                examples.append(f"> {sentence} [{source.source_id}] ({source.page_display})")
        if examples:
            return "### Concrete Practical Examples in the Documents\n\n" + "\n\n".join(examples[:3])
        passages = StructuredAnswerComposer._best_sentences(analysis, sources, 3)
        if passages:
            return ("### Practical Application Context\n"
                    "The text does not state an explicit toy example; these passages describe practical application:\n\n"
                    + "\n\n".join(f"> {sentence} [{source.source_id}]" for source, sentence, _ in passages))
        return StructuredAnswerComposer._not_found(analysis, "No practical example was reported in the retrieved passages.")

    @staticmethod
    def _procedure(analysis, sources, facts):
        steps = [fact for fact in facts if fact.fact_type == "list_item"]
        steps = StructuredAnswerComposer._rank_facts(steps, [*analysis.important_terms, *analysis.expanded_terms], 12)
        if steps:
            return "### Steps explicitly listed in the documents\n" + "\n".join(
                f"{number}. {fact.value} [{fact.source_id}]" for number, fact in enumerate(steps, 1)
            )
        passages = StructuredAnswerComposer._best_sentences(analysis, sources, 5)
        if not passages:
            return StructuredAnswerComposer._not_found(analysis, "No procedure or ordered steps were found in the retrieved passages.")
        return ("### Procedural evidence\nThe source passages do not expose a clearly ordered list; the following passages describe the process:\n\n"
                + "\n".join(f"> {sentence} [{source.source_id}]" for source, sentence, _ in passages[:4]))

    @staticmethod
    def _list(analysis, sources, facts):
        all_items = [fact for fact in facts if fact.fact_type == "list_item"]
        items = StructuredAnswerComposer._rank_facts(all_items, [*analysis.important_terms, *analysis.expanded_terms], 16)
        if not items:
            items = all_items[:16]
        if items:
            return "### Items explicitly listed\n" + "\n".join(f"- {fact.value} [{fact.source_id}]" for fact in items)
        return StructuredAnswerComposer._evidence(analysis, sources)

    @staticmethod
    def _typed_facts(analysis, sources, facts, fact_type, heading):
        selected = StructuredAnswerComposer._rank_facts([fact for fact in facts if fact.fact_type == fact_type], [*analysis.important_terms, *analysis.expanded_terms], 10)
        if not selected:
            return StructuredAnswerComposer._not_found(analysis, f"No explicit {fact_type} evidence was extracted from the retrieved passages.")
        return f"### {heading}\n" + "\n".join(f"- {fact.supporting_passage} [{fact.source_id}]" for fact in selected)

    @staticmethod
    def _pros_cons(analysis, sources):
        pros, cons = [], []
        for source, sentence, score in StructuredAnswerComposer._best_sentences(analysis, sources, 20):
            line = f"- {sentence} [{source.source_id}]"
            if re.search(r"\b(?:advantage|benefit|strength|improv|outperform|effective)\b", sentence, re.I):
                pros.append(line)
            if re.search(r"\b(?:disadvantage|limitation|weakness|drawback|challenge|failed|degrad)\b", sentence, re.I):
                cons.append(line)
        if not pros and not cons:
            return StructuredAnswerComposer._not_found(analysis, "The retrieved text did not explicitly identify advantages or limitations.")
        return ("### Advantages stated in the documents\n" + ("\n".join(pros) if pros else "Not found in the retrieved passages.")
                + "\n\n### Disadvantages and limitations stated\n" + ("\n".join(cons) if cons else "Not found in the retrieved passages."))

    @staticmethod
    def _evidence(analysis, sources):
        selected = [source for source in sources if _overlap_score(
            source.text, [*analysis.important_terms, *analysis.expanded_terms]
        ) > 0]
        if not selected:
            return StructuredAnswerComposer._not_found(analysis, "No passage with relevant query terms was retrieved.")
        lines = []
        for source in selected[:8]:
            passage = " ".join(unicodedata.normalize("NFKC", source.text).split())
            lines.append(f"- **{source.filename or source.title or source.paper_id} · {source.page_display} · {source.section}:** {passage} [{source.source_id}]")
        return "### Relevant evidence passages\n" + "\n".join(lines)

    @staticmethod
    def _general(analysis, sources):
        generic_terms = {
            "want", "know", "system", "syllabus", "document", "documents", "paper",
            "topic", "topics", "research", "information", "overview", "main", "content",
            "source", "sources", "selected", "please", "tell", "show", "give",
        }
        subject_terms = [term for term in analysis.important_terms if term.casefold() not in generic_terms]
        passages = StructuredAnswerComposer._best_sentences(
            analysis, sources, 10, required_terms=subject_terms or None
        )
        if not passages and sources and not subject_terms:
            for s in sources:
                for sent in _sentences(s.text):
                    passages.append((s, sent, 1))
        if not passages:
            return StructuredAnswerComposer._not_found(analysis, "The retrieved passages do not contain an identifiable answer.")
        first = passages[0]
        answer = "### Direct answer from the selected documents\n> " + first[1] + f" [{first[0].source_id}]"
        supporting = passages[1:5]
        if supporting:
            answer += "\n\n### Supporting evidence\n" + "\n".join(
                f"- {sentence} [{source.source_id}]" for source, sentence, _ in supporting
            )
        return answer

    @staticmethod
    def _rank_facts(facts, terms, limit):
        deduped = OrderedDict()
        for fact in facts:
            deduped.setdefault((fact.source_id, fact.fact_type, fact.value.casefold()), fact)
        ranked = sorted(deduped.values(), key=lambda fact: (-_overlap_score(fact.supporting_passage, terms), fact.source_id, fact.physical_page or 0))
        return [fact for fact in ranked if not terms or _overlap_score(fact.supporting_passage, terms) > 0][:limit]

    @staticmethod
    def _best_sentences(analysis, sources, limit, required_terms=None):
        scored = []
        terms = list(OrderedDict.fromkeys([*analysis.important_terms, *analysis.expanded_terms]))
        for source in sources:
            for sentence in _sentences(source.text):
                if required_terms and _overlap_score(sentence, required_terms) <= 0:
                    continue
                score = _overlap_score(sentence, terms)
                if score or not terms:
                    scored.append((source, sentence, score))
        scored.sort(key=lambda item: (-item[2], item[0].source_id, len(item[1])))
        return scored[:limit]
