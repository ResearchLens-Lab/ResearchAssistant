# ResearchLens — Active Research Runtime Execution Trace

**Document Version:** 1.0.0  
**Phase:** Phase A Runtime Architecture Audit  
**Date:** 2026-11-12  
**Target Environment:** Localhost (`http://localhost:3000` / `http://127.0.0.1:8000`)  
**Engine:** Phase 1–7 Evidence-First Integration Audit  

---

## 1. Executive Summary & Root Cause Analysis

A runtime execution trace was conducted across the frontend (Next.js 15) and backend (FastAPI + Python RAG subsystem) to identify why the application exhibits legacy chat behavior (invoking local Qwen / Ollama, displaying raw `S1`/`S2` tags, desynchronizing the Evidence counter to `0`, and returning incomplete `Answer:`/`Explanation:` blocks on table requests).

### The Exact Root Cause Chain

```text
User Submits Question in Research Desk (/chat)
    |
    v
Frontend: ChatInputBar.jsx (Default: answerMode = "DOCUMENTS_GENERAL")
    |
    v
POST /api/v1/chat/stream -> ChatService.stream_message
    |
    v
RAGGateway.ask_question -> RAGClient.ask_question
    |
    v
QueryPipeline.answer_question
    |
    +---> [DECISION POINT 1]: settings.rag_engine_mode == "legacy" (DEFAULT in rag/config/settings.py)
    |     Result: self._independent_engine is BYPASSED completely!
    |
    v
Legacy QueryPlanner & ResearchRetriever (Dense + BM25 Hybrid)
    |
    v
[DECISION POINT 2]: is_ollama_requested check in QueryPipeline (lines 447-450)
    |     Condition: settings.llm_provider in ("ollama", "qwen") or settings.rag_answer_mode == "LOCAL_QWEN"
    |     Result: TRUE (defaults: llm_provider="ollama", rag_answer_mode="LOCAL_QWEN")
    |
    v
Instantiates OllamaLLMClient(model="qwen3.5:0.8b")
    |
    +---> Emits SSE Event: {"type": "generation_started", "provider": "ollama"}
    |     Frontend useChat.js maps to: "Generating with local Qwen; CPU answers can take a little longer…"
    |
    +---> If Ollama fails or claims unverified:
    |     Calls ExtractiveAnswerEngine.generate_extractive_answer()
    |     Result: Generates "**Direct Answer:**\n...\n\n**Explanation:**\n..." and labels "Extractive Fallback"
    |
    v
Citation Formatting: Formats sources as internal keys "S1", "S2"
    |
    v
Message Persisted & Stream Completed
    |
    +---> CitationStore Desynchronization: useCitationStore is only updated on non-pending messages
          during conversation load, leaving top toolbar showing "Evidence (0)"
```

---

## 2. Detailed Runtime Component Audit

### 2.1 Frontend Components

| Component | File Path | Current Observed Behavior | Defect / Gap |
| :--- | :--- | :--- | :--- |
| **Research Desk Workbench** | `frontend/src/components/chat/ThreePaneChatWorkbench.jsx` | Renders 3 panes: history, chat, citation rail. Top toolbar shows `Evidence ({sources.length})`. | `sources` is read from `useCitationStore()`, which is initialized to `[]` and not updated when messages finish streaming or switch. Shows `Evidence (0)`. |
| **Chat Input Bar** | `frontend/src/components/chat/ChatInputBar.jsx` | Dropdown defaults to `"DOCUMENTS_GENERAL"`. Prompt action buttons insert text into textarea. | Defaulting to `"DOCUMENTS_GENERAL"` signals the backend to allow generative general knowledge rather than strictly deterministic evidence. |
| **Message Item** | `frontend/src/components/chat/MessageItem.jsx` | Inspects `meta.answer_mode` and displays badges: `Local Qwen (qwen3.5:0.8b)`, `Extractive Fallback`. | Does not handle `independent_documents_only` as primary, displays fallback badges when Qwen is bypassed. |
| **Citation Badge** | `frontend/src/components/citations/CitationBadge.jsx` | Renders literal text `{sourceId}` (`S1`, `S2`). | Does not format true academic citations (`[Author, Year, p. X]`). |
| **Stream Event Listener** | `frontend/src/hooks/useChat.js` | Maps `generation_started` with provider `ollama` to `"Generating with local Qwen; CPU answers can take a little longer…"`. | Hardcoded status string for Ollama rather than reflecting deterministic research engine stages. |

### 2.2 Backend Routes & Services

| Service / Route | File Path | Role in Execution Trace |
| :--- | :--- | :--- |
| **Chat Route** | `backend/app/routes/chat.py` | Receives POST `/api/v1/chat` and `/api/v1/chat/stream`. Passes `CurrentUser` and `ChatRequest` to `ChatService`. |
| **Chat Service** | `backend/app/services/chat_service.py` | Validates user paper ownership, retrieves prior conversation context, calls `RAGGateway.ask_question`, streams progress events via SSE queue, and persists assistant message with sources. |
| **RAG Gateway** | `backend/app/integrations/rag_gateway.py` | Dispatches calls in background executor threads to avoid blocking asyncio event loop. Enforces timeouts. |
| **RAG Client** | `backend/app/integrations/rag_client.py` | Bridges backend to RAG subsystem. Calls `QueryPipeline.answer_question()`. |
| **Query Pipeline** | `rag/pipelines/query_pipeline.py` | **Core branching point.** Line 160 checks `settings.rag_engine_mode == "independent"`. Because setting is `"legacy"`, it bypasses `IndependentResearchEngine` and runs `QueryPlanner` + `ResearchRetriever` + `OllamaLLMClient`. |
| **Independent Research Engine** | `rag/independent/engine.py` | Phase 1 deterministic engine. Features intent classification, BM25 retrieval without neural embeddings, fact extraction, structured answer composition, and conflict/evidence validation. **Currently inactive in application runtime.** |

---

## 3. Configuration Analysis & Precedence

Inspection of the actual settings in memory reveals:

1. **`backend/app/core/config.py`**:
   - `rag_engine_mode` is **missing** from the backend `Settings` class definition.
   - `rag_answer_mode` defaults to `"LOCAL_QWEN"`.
   - `ollama_model` defaults to `"qwen3.5:0.8b"`.

2. **`rag/config/settings.py`**:
   - `rag_engine_mode: Literal["legacy", "independent"] = "legacy"` (Line 49).
   - `rag_answer_mode: Literal["EXTRACTIVE", "LOCAL_QWEN"] = "LOCAL_QWEN"`.
   - `llm_provider: Literal["local", "mock", "gemini", "ollama", "openai"] = "ollama"`.

3. **`backend/.env.local`**:
   - Contains database connection and upload directory.
   - Does **not** set `RAG_ENGINE_MODE=independent`.

### Precedence Result
Because neither `.env.local` nor the environment variables set `RAG_ENGINE_MODE=independent`, Python pydantic-settings falls back to `rag/config/settings.py` default: `"legacy"`.

---

## 4. Why Follow-Up Table Requests Return `Answer:` / `Explanation:`

When a user clicks **"Use a table"**, the query text submitted is:
`"Present the relevant findings in a concise table with citations."`

In the legacy execution path:
1. `QueryPlanner` classifies intent as `"direct"` or `"summary"`.
2. `QueryPipeline` tries local Qwen. If Qwen times out, is slow, or claim verification fails, it falls back to `ExtractiveAnswerEngine.generate_extractive_answer()`.
3. In `ExtractiveAnswerEngine` (lines 340–350):
   It attempts to extract keywords from `"Present the relevant findings in a concise table with citations."`. Since almost all words are stopwords (`present`, `relevant`, `findings`, `table`, `citations`), `keywords` is empty!
4. With empty keywords, `salient_points` defaults to the first sentence of the top source, but `direct_ans` and `explanation` receive minimal text or empty strings.
5. The template formats:
   ```markdown
   **Direct Answer:**
   {direct_ans}

   **Explanation:**
   {explanation}
   ```
   Producing an empty or nearly blank block with no actual table!

---

## 5. Architectural Corrective Plan

1. **Make `rag_engine_mode = "independent"` the Absolute Default** across `rag/config/settings.py` and `backend/app/core/config.py`.
2. **Expose Mode Controls Cleanly:**
   - Mode 1 (Default): Deterministic Evidence-First. No Qwen/Ollama calls.
   - Mode 2: Documents + General Knowledge (explicit user selection).
   - Mode 3: Optional Local AI (explicit user selection with disclosed model).
3. **Enhance Independent Answer Composer (`StructuredAnswerComposer`):**
   - Add native support for Table synthesis requests (`QuestionIntent.TABLE`).
   - Format complete markdown tables (`Topic | Finding | Evidence / Citation`).
   - Add structured academic summary templates (Problem, Objective, Methodology, Setup, Findings, Limitations, Conclusion).
4. **Implement Academic Citation Contract:**
   - Map citations to `[Author et al., Year, p. X]` using genuine verified paper and chunk metadata.
   - Synchronize `useCitationStore` on message completion and streaming so `Evidence (N)` correctly displays the number of cited sources.

