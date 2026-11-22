import sys, os
sys.path.insert(0, os.path.abspath("."))
import time
from backend.app.integrations.rag_client import rag_client

user_id = "4526f09d-ae50-47d8-8a73-ffe73e3dc0dd"
paper_ids = ["fb6729c8-49e1-4dd2-b22f-da03b4d198a4", "5d009428-7a4c-4225-9878-ae252140b1c3"]
paper_metadata = {
    "fb6729c8-49e1-4dd2-b22f-da03b4d198a4": {
        "title": "Introduction to Computer Science",
        "authors": ["Thomas H. Cormen", "Charles E. Leiserson"],
        "year": 2022,
    },
    "5d009428-7a4c-4225-9878-ae252140b1c3": {
        "title": "Generative AI in Cybersecurity",
        "authors": ["Vance", "Chen"],
        "year": 2025,
    }
}

print("="*60)
print("TEST 1: 'what is an algorithm'")
res1 = rag_client.ask_question(
    question="what is an algorithm",
    user_id=user_id,
    paper_ids=paper_ids,
    paper_metadata=paper_metadata,
)
print("Answer:\n", res1["answer"][:300], "...")
print("Cited sources count:", len(res1["sources"]))
if res1["sources"]:
    print("Source 1 citation_label:", res1["sources"][0].get("citation_label"))
    print("Source 1 author_metadata:", res1["sources"][0].get("author_metadata"))
print("Metadata answer_mode:", res1["metadata"].get("answer_mode"))
print("Metadata generation_provider:", res1["metadata"].get("generation_provider"))
print("Metadata model_calls:", res1["metadata"].get("model_calls"))

print("="*60)
print("TEST 2: 'Present the relevant findings in a concise table with citations'")
res2 = rag_client.ask_question(
    question="Present the relevant findings in a concise table with citations",
    user_id=user_id,
    paper_ids=paper_ids,
    conversation_context="user: what is an algorithm\nassistant: an algorithm is a sequence of steps",
    paper_metadata=paper_metadata,
)
print("Answer:\n", res2["answer"][:400], "...")
print("Cited sources count:", len(res2["sources"]))
if res2["sources"]:
    print("Source 1 citation_label:", res2["sources"][0].get("citation_label"))

print("="*60)
print("TEST 3: 'give me the summary'")
res3 = rag_client.ask_question(
    question="give me the summary",
    user_id=user_id,
    paper_ids=paper_ids,
    paper_metadata=paper_metadata,
)
print("Answer:\n", res3["answer"][:500], "...")
print("Cited sources count:", len(res3["sources"]))

print("="*60)
print("TEST 4: 'What are the reported limitations?'")
res4 = rag_client.ask_question(
    question="What are the reported limitations?",
    user_id=user_id,
    paper_ids=paper_ids,
    conversation_context="user: what is an algorithm\nassistant: an algorithm is a sequence of steps",
    paper_metadata=paper_metadata,
)
print("Answer:\n", res4["answer"][:400], "...")
print("="*60)
print("ALL TESTS COMPLETED SUCCESSFULLY!")
