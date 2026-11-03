# ResearchAssistant — Backend

**Owner:** Abhay Kumar Singh

The backend is the application's central API boundary: authentication, papers,
document upload, conversations/chat persistence, and the integration
boundaries toward RAG (Gorav) and research intelligence / knowledge graph
(Harendra). The frontend (Himanshu) talks only to this API — never to
PostgreSQL, ChromaDB, the LLM or Neo4j directly.

```text
Frontend ──HTTP/JSON──▶ FastAPI ──▶ Services ──▶ PostgreSQL / File storage
                                        │
                                        ├──▶ RAG boundary (rag_client → rag/ pipelines)
                                        └──▶ Knowledge-graph boundary (stub, 503 for now)
```

## Architecture

Strict layering — routes never contain SQL, RAG logic or prompts:

```text
routes/         HTTP handling only
schemas/        Pydantic request/response validation (ORM models never returned raw)
services/       Business logic, transactions, orchestration
repositories/   All database access
models/         SQLAlchemy ORM models
integrations/   External subsystem boundaries (RAG, knowledge graph)
core/           Config, security (JWT/bcrypt), dependencies, error types
database/       Async engine, session dependency, declarative base
middleware/     X-Request-ID + global error handlers
utils/          Pagination, upload validators
migrations/     Alembic (async) migrations
tests/          pytest suite (isolated in-memory DB, mocked RAG)
```

### RAG integration

`app/integrations/rag_client.py` is **Gorav's boundary contract** (in-process,
synchronous). The backend never calls it directly from routes/services —
everything goes through `app/integrations/rag_gateway.py`, which:

- runs the synchronous pipeline off the event loop (`asyncio.to_thread`),
- applies `RAG_TIMEOUT_SECONDS`,
- maps any failure to a structured `503 RAG_UNAVAILABLE`,
- imports the RAG dependency chain lazily (the API starts and tests run
  without ChromaDB installed).

Shared IDs are sacred: `paper_id` and `document_id` created here flow
unchanged into RAG/ChromaDB metadata, Neo4j and the frontend.

### Knowledge-graph boundary

`app/integrations/knowledge_graph_client.py` defines the interface only
(`get_paper_graph`, `get_related_papers`, `get_citation_network`,
`get_research_trends`). Until Harendra's service is wired in, the
`/api/v1/research/*` endpoints answer `503 KNOWLEDGE_GRAPH_UNAVAILABLE`.

## Environment setup

From the **repository root** (imports resolve against the monorepo):

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows (source .venv/bin/activate on Unix)
pip install -r requirements.txt -r backend/requirements.txt
copy backend\.env.example backend\.env   # then edit values
```

Configuration is environment-based (Pydantic Settings, `backend/app/core/config.py`).
Never commit `.env` or real secrets. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/researchassistant` | Async SQLAlchemy URL |
| `JWT_SECRET_KEY` | `change-me` | Sign JWTs — set a long random value |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | 30 / 7 | Token lifetimes |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated frontend origins |
| `RAG_TIMEOUT_SECONDS` | 60 | Timeout for RAG boundary calls |
| `UPLOAD_DIR` / `MAX_UPLOAD_SIZE_MB` | `./storage/uploads` / 100 | Staged source storage and per-file limit in MiB |
| `MAX_UPLOAD_BATCH_SIZE_MB` / `MAX_UPLOAD_BATCH_FILES` | 500 / 100 | Combined multipart batch limit and file count |
| `MAX_ZIP_ENTRIES` / `MAX_ZIP_ENTRY_SIZE_MB` | 100 / 100 | Archive entry count and per-entry expanded-size limits |
| `MAX_ZIP_EXPANDED_SIZE_MB` / `MAX_ZIP_COMPRESSION_RATIO` | 100 / 200 | Total expanded archive size and maximum compression ratio |

## Database setup & migrations

Start PostgreSQL (see Docker below, or use a local instance), then:

```bash
alembic -c backend/alembic.ini upgrade head
```

Changing models: edit the SQLAlchemy model → create a migration → review →
apply → commit the migration file. Never modify the schema manually.

```bash
alembic -c backend/alembic.ini revision --autogenerate -m "describe change"
alembic -c backend/alembic.ini upgrade head
```

## Running the API

From the repository root:

```bash
uvicorn backend.app.main:app --reload
```

- Liveness: `GET /health` — Readiness (DB check): `GET /health/ready`
- Interactive docs: http://localhost:8000/docs (ReDoc at `/redoc`)

### Docker

```bash
docker compose up            # chroma + postgres + api (migrations run on start)
```

## Running tests

```bash
python -m pytest backend/tests -q
```

Tests use an isolated in-memory SQLite database and a deterministic
`FakeRAGGateway` — they never touch the development database and never call
the real RAG pipeline or an LLM. The suite covers auth (rotation/revocation
included), paper CRUD + ownership, upload validation, chat persistence,
search, error shapes, and one full register→login→paper→upload→chat
integration flow.

## API overview (all under `/api/v1`, JWT bearer auth unless noted)

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/register` `/auth/login` `/auth/me` `/auth/refresh` `/auth/logout` | POST/GET | Auth (register/login are public) |
| `/users/me` | GET/PATCH | Profile |
| `/papers` | POST/GET | Create / list own papers |
| `/papers/{paper_id}` | GET/PATCH/DELETE | Paper CRUD (ownership enforced) |
| `/papers/{paper_id}/summary` | POST | Grounded summary via RAG |
| `/papers/compare` | POST | Multi-paper comparison via RAG |
| `/papers/{paper_id}/documents` | GET | Documents for a paper |
| `/documents/upload` | POST | One supported source upload to RAG indexing |
| `/documents/upload/batch` | POST | Multiple files or ZIP upload to RAG indexing |
| `/documents/by-papers` | POST | Owned-project document statuses in one response |
| `/documents/{document_id}` | GET | Metadata + processing status |
| `/chat` | POST | Grounded Q&A with source persistence |
| `/conversations…` | POST/GET/DELETE | Conversation history |
| `/search` | GET | Metadata search (`q`, `author`, `year`, paging) |
| `/research/…` | GET | Knowledge-graph boundary (503 until integrated) |

### Example: chat

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question": "What is the main contribution?", "paper_ids": ["<paper_id>"], "conversation_id": null}'
```

```json
{
  "conversation_id": "…", "message_id": "…",
  "answer": "The paper proposes… [S1]",
  "sources": [{"source_id": "S1", "paper_id": "…", "document_id": "…",
               "chunk_id": "…", "page": 4, "section": "Methodology",
               "text": "…", "score": 0.87, "title": "…"}],
  "paper_ids": ["…"]
}
```

### Errors

Every error uses one shape (no stack traces leak to clients):

```json
{"error": {"code": "PAPER_NOT_FOUND", "message": "Paper was not found.", "request_id": "req_ab12cd34"}}
```

Codes include `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `PAPER_NOT_FOUND`,
`DOCUMENT_NOT_FOUND`, `VALIDATION_ERROR`, `EMAIL_ALREADY_REGISTERED`,
`RAG_UNAVAILABLE`, `KNOWLEDGE_GRAPH_UNAVAILABLE`, `INTERNAL_ERROR`. Every
response carries an `X-Request-ID` header that also appears in the logs.

## File upload behavior

- The batch endpoint accepts up to 100 files with a combined size of 500 MiB;
  each file (including a ZIP archive) is limited to 100 MiB. Upload bytes are
  staged to disk in bounded chunks. ZIP entries remain capped at 100 files,
  100 MiB per entry and 100 MiB expanded total, with a 200:1 compression-ratio
  limit and path/type checks.

- `POST /api/v1/documents/upload` accepts `multipart/form-data`
  (`file` = PDF, `paper_id` = owning paper).
- Validation: `.pdf` extension, content type, non-empty, `%PDF-` signature,
  size ≤ `MAX_UPLOAD_SIZE_MB`.
- Files are stored as `UPLOAD_DIR/{document_id}.pdf` — user filenames never
  become filesystem paths (no traversal); the original name is kept in the DB.
- Status flow: `uploaded → processing → indexed | failed` (RAG reports the
  result back; ingestion is synchronous for the prototype and can move to a
  background worker without schema changes). Raw file bytes are never sent to
  the frontend.

## Notes for follow-up questions in conversations

Gorav's current `ask_question` contract takes a question + `paper_ids` only —
there is no conversation-history parameter yet. The backend persists full
history, so once the RAG contract grows a bounded-context input the chat
service can pass recent turns without schema changes.
