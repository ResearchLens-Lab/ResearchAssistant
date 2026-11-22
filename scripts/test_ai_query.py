import sys, os
sys.path.insert(0, os.path.abspath("."))
from rag.independent.retriever import IndependentRetriever
from rag.independent.intent_classifier import QuestionIntentClassifier

retriever = IndependentRetriever()
classifier = QuestionIntentClassifier()
q = "How does the paper describe the role of AI in cybersecurity?"
analysis = classifier.classify(q)
print("Intent:", analysis.intent)
print("Important terms:", analysis.important_terms)
sources, _ = retriever.retrieve(analysis, paper_ids=["5d009428-7a4c-4225-9878-ae252140b1c3"], owner_id="4526f09d-ae50-47d8-8a73-ffe73e3dc0dd", top_k=5)
for s in sources:
    print(f"=== Source {s.source_id} (Sec: {s.section}, Page: {s.page_start}) ===")
    print(s.text[:350])

