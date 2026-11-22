# ResearchLens Architecture & Team Integration Boundaries

This document defines the technical contracts and integration boundaries between team ownership areas in the ResearchLens monorepo.

---

## 1. Team Ownership Map

| Team Member | Role | Primary Responsibility | Directory |
|---|---|---|---|
| **Gorav Gumber** | Project Lead, Technical Architect and RAG Lead | Core RAG, Document Normalization, Chunking, Lexical & Vector Indexing, Extractive Synthesis, Desktop Architecture | `rag/`, `desktop/`, `scripts/` |
| **Abhay Kumar Singh** | Backend and Database Contributor | FastAPI routes, database schemas, User Auth, Async Tasks, Paper CRUD | `backend/` |
| **Himanshu Kumawat** | Frontend Lead | Next.js UI, Paper Viewer, Chat Interface, Citation Drawer | `frontend/` |
| **Harendra Godara** | Knowledge Graph Lead | Neo4j Graph DB, Citation Graph Reasoning, Entity Extraction | `knowledge-graph/` |

---

## 2. Integration Boundary: Backend (Abhay) ↔ RAG (Gorav)

Abhay's FastAPI backend should interact with the RAG engine **strictly** through the boundary wrapper:
`backend/app/integrations/rag_client.py`

### Python Interface:
```python
from backend.app.integrations.rag_client import rag_client

# 1. Ingest Document when uploaded by user
ingest_result = rag_client.ingest_document(
    file_path="/path/to/paper.pdf",
    paper_id="paper_123",
    metadata={"title": "Attention Is All You Need", "year": 2017}
)
# Returns: {"success": True, "status": "indexed", "document_id": "...", "chunk_count": 9, ...}

# 2. Ask Research Question
chat_response = rag_client.ask_question(
    question="What is the BLEU score achieved?",
    paper_ids=["paper_123"],
    top_k=5
)
# Returns: {"answer": "...", "sources": [{"source_id": "S1", "paper_id": "paper_123", "page": 4, "section": "Results", "text": "..."}]}

# 3. Summarize Paper
summary_response = rag_client.summarize_paper(paper_id="paper_123")

# 4. Compare Papers
comparison_response = rag_client.compare_papers(
    paper_ids=["paper_123", "paper_456"],
    focus_area="Compare methodology and efficiency."
)
```

---

## 3. Integration Boundary: Backend (Abhay) ↔ Frontend (Himanshu)

### REST API Chat Contract
`POST /api/v1/chat`

**Request Body**:
```json
{
  "question": "What is the core architecture of the Transformer?",
  "paper_ids": ["paper_123"],
  "conversation_id": null
}
```

**Response Body**:
```json
{
  "answer": "The Transformer replaces recurrence and convolution with self-attention mechanisms [S1].",
  "sources": [
    {
      "source_id": "S1",
      "paper_id": "paper_123",
      "page": 2,
      "page_start": 2,
      "page_end": 2,
      "section": "Introduction",
      "text": "Recurrent neural networks factor computation sequentially... The Transformer allows for significantly more parallelization.",
      "score": 0.89,
      "title": "Attention Is All You Need"
    }
  ],
  "paper_ids": ["paper_123"]
}
```

---

## 4. Integration Boundary: RAG ↔ Knowledge Graph (Harendra)
- **Harendra's Knowledge Graph** operates on entities, authors, and citation links.
- When multi-hop citation graph reasoning is integrated in future sprints, Harendra's service can pass related `paper_ids` to `rag_client.ask_question(question, paper_ids=expanded_graph_paper_ids)`.

---

## 5. Security & Isolation Rules
1. **Frontend never talks to ChromaDB or LLMs directly**: All AI & vector database calls must originate from the server.
2. **No RAG logic inside arbitrary route handlers**: Keep `rag/` modular, decoupled, and standalone.
3. **No hard-coded secrets**: All API keys and connection parameters are loaded via `rag/config/settings.py`.
