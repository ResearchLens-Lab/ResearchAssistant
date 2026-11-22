# Backend Service Architecture

The backend provides the API service layer for ResearchLens, handling user authentication, project organization, document ingestion, session persistence, and retrieval orchestration.

```text
Frontend ──HTTP/JSON──▶ FastAPI Backend ──▶ Services ──▶ SQLite / File Storage
                                                │
                                                └──▶ RAG Client Bridge (rag/ pipelines)
```

---

## Architectural Layering

The backend enforces strict separation of concerns across service boundaries:

```text
routes/         HTTP endpoint routing and status code mapping
schemas/        Pydantic models for request and response validation
services/       Business logic, transaction management, and service orchestration
repositories/   Database queries and persistence operations
models/         SQLAlchemy ORM models
integrations/   Subsystem bridges (RAG client and gateway)
core/           Configuration settings, security, and exception definitions
database/       Database engine, session management, and migrations
middleware/     Request tracking and global error handlers
utils/          Pagination and file validation helpers
migrations/     Alembic database schema migrations
tests/          Pytest test suites
```

---

## Research Engine Integration

The backend interacts with the research engine through `app/integrations/rag_gateway.py`. The gateway executes retrieval and generation pipelines synchronously off the main asynchronous event loop (`asyncio.to_thread`), applies timeouts, and isolates exceptions.

Consistent document identifiers (`paper_id` and `document_id`) are maintained across the relational store, the lexical index, and the frontend client.
