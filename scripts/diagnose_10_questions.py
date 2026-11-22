import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
from backend.app.integrations.rag_client import rag_client

user_id = "4526f09d-ae50-47d8-8a73-ffe73e3dc0dd"
paper_id = "5d009428-7a4c-4225-9878-ae252140b1c3"

questions = [
    "What is cyber security?",
    "What are the main cybersecurity challenges discussed in this paper?",
    "How does the paper describe the role of AI in cybersecurity?",
    "What research methodology did the authors use?",
    "Which datasets are discussed?",
    "What findings are actually reported?",
    "What limitations do the authors explicitly identify?",
    "Who are the authors of this paper?",
    "Summarize this paper.",
    "Present the relevant findings in a concise table with citations.",
]

results = []
for q in questions:
    res = rag_client.ask_question(
        question=q,
        user_id=user_id,
        paper_ids=[paper_id],
    )
    results.append({
        "question": q,
        "intent": res.get("metadata", {}).get("independent_research", {}).get("intent", {}).get("intent"),
        "answer": res.get("answer"),
        "sources_count": len(res.get("sources", [])),
        "sources": [
            {
                "source_id": s.get("source_id"),
                "citation_label": s.get("citation_label"),
                "page": s.get("page_start"),
                "section": s.get("section"),
                "text_snippet": s.get("text", "")[:120],
            }
            for s in res.get("sources", [])[:3]
        ]
    })

with open("docs/quality/diagnostic_baseline_outputs.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("Baseline outputs recorded successfully for all 10 questions.")

