import sys, os
sys.path.insert(0, os.path.abspath("."))
import re, unicodedata
from collections import OrderedDict
from rag.independent.models import ExtractedFact, QueryAnalysis, QuestionIntent
from rag.retrieval.query import RetrievedSource
from rag.independent.retriever import IndependentRetriever
from rag.independent.intent_classifier import QuestionIntentClassifier
from rag.independent.fact_extractor import FactExtractor

def clean_academic_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(?im)\bInternational\s+Journal\s+of\s+[^\n.,]+(?:\s+and\s+[^\n.,]+)?", " ", text)
    text = re.sub(r"(?im)\bVolume\s+\d+[\s\S]{1,60}?ISSN[^\n.,;]+", " ", text)
    text = re.sub(r"(?im)\bDOI:\s*10\.\d{4,9}/[^\s,;)]+", " ", text)
    text = re.sub(r"(?im)\bwww\.[a-z0-9\-]+\.[a-z]{2,}(?:/[^\s]*)?", " ", text)
    text = re.sub(r"(?im)\bhttps?://[^\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def clean_sentence(sent: str) -> str:
    s = clean_academic_text(sent)
    s = re.sub(r"^\s*(?:\d+(?:\.\d+)*|[A-Z]\.?|\b\d+\b)\s*", "", s) # strip heading numbers like "3.1 " or "1. "
    s = re.sub(r"^\s*[-*•]\s*", "", s)
    return s.strip(" \t\r\n.,;:") + "."

retriever = IndependentRetriever()
classifier = QuestionIntentClassifier()
owner_id = "4526f09d-ae50-47d8-8a73-ffe73e3dc0dd"
paper_id = "5d009428-7a4c-4225-9878-ae252140b1c3"

questions = [
    "What is cybersecurity?",
    "What research methodology did the authors use?",
    "How does the paper describe the role of AI in cybersecurity?",
    "What are the main cybersecurity challenges discussed in the paper?",
    "Present the relevant findings in a concise table with citations",
    "give me the summary"
]

for q in questions:
    analysis = classifier.classify(q)
    sources, _ = retriever.retrieve(analysis, paper_ids=[paper_id], owner_id=owner_id, top_k=5)
    print(f"\n==================================================")
    print(f"QUESTION: {q}")
    print(f"INTENT: {analysis.intent.value}")
    print(f"RETRIEVED {len(sources)} SOURCES")
    for s in sources[:2]:
        print(f"  [{s.source_id}] Sec: {s.section}, Page: {s.page_start}")
        print(f"       Text: {clean_academic_text(s.text)[:160]}...")

