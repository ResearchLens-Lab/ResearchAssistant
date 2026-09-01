# ResearchLens-Lab — ResearchAssistant
# Backend Working & Implementation Guide

**Backend Owner:** Abhay Kumar Singh  
**Project Lead / RAG Owner:** Gorav Gumber  
**Frontend Owner:** Himanshu Kumawat  
**Knowledge Graph / Research Intelligence Owner:** Harendra Godara

---

## 1. Purpose

This document is the implementation contract for the **backend + database layer** of ResearchAssistant.

The backend is responsible for:

- FastAPI application
- REST API design
- authentication
- user management
- paper/document metadata
- upload handling
- PostgreSQL persistence
- SQLAlchemy ORM
- Alembic migrations
- conversation/chat persistence
- RAG integration
- API validation
- error handling
- authorization
- backend tests
- API documentation
- integration with frontend and RAG
- integration boundaries for research intelligence

The backend must **not implement the internal RAG algorithms**. RAG internals belong to Gorav.

The backend is the application's central API boundary:

```text
Frontend
   ↓ HTTP/JSON
FastAPI Backend
   ↓
Application Services
   ├── PostgreSQL
   ├── File Storage
   ├── RAG Integration
   └── Research Intelligence Integration
```

---

# 2. Team Architecture

```text
ResearchLens-Lab
└── ResearchAssistant
    │
    ├── frontend/             → Himanshu
    ├── backend/              → Abhay
    ├── rag/                  → Gorav
    ├── knowledge-graph/     → Harendra
    ├── infrastructure/
    ├── docs/
    ├── tests/
    └── scripts/
```

Ownership must remain clear.

### Abhay

Owns the application backend and database.

### Gorav

Owns RAG internals:

```text
chunking
embeddings
ChromaDB
retrieval
context
LLM
grounding
citations
RAG evaluation
```

### Himanshu

Consumes backend APIs from the frontend.

### Harendra

Owns Neo4j and research-intelligence functionality.

---

# 3. Golden Backend Rule

The backend is an **orchestration and application layer**.

It should not contain:

```text
ChromaDB queries
embedding implementation
chunking implementation
LLM prompt logic
citation-ranking logic
```

inside route handlers.

Correct:

```text
FastAPI Route
      ↓
Service
      ↓
RAG Client
      ↓
RAG Pipeline
```

Incorrect:

```text
FastAPI Route
      ↓
ChromaDB
      ↓
LLM
```

---

# 4. Technology Stack

Use the project backend stack:

```text
Python
FastAPI
Pydantic v2
SQLAlchemy
PostgreSQL
Alembic
JWT authentication
pytest
HTTPX
Docker
```

Redis/Celery may be introduced only where they provide a clear prototype benefit, such as background document-processing jobs or caching.

Do not turn the prototype into an unnecessarily distributed system.

---

# 5. Backend Folder Structure

Create:

```text
backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── dependencies.py
│   │   └── exceptions.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── session.py
│   │   └── base.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── paper.py
│   │   ├── document.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   └── research_metadata.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── paper.py
│   │   ├── document.py
│   │   ├── chat.py
│   │   ├── citation.py
│   │   ├── research.py
│   │   └── common.py
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── papers.py
│   │   ├── documents.py
│   │   ├── chat.py
│   │   ├── search.py
│   │   └── research.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── paper_service.py
│   │   ├── document_service.py
│   │   ├── conversation_service.py
│   │   ├── chat_service.py
│   │   └── research_service.py
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── user_repository.py
│   │   ├── paper_repository.py
│   │   ├── document_repository.py
│   │   ├── conversation_repository.py
│   │   └── message_repository.py
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── rag_client.py
│   │   └── knowledge_graph_client.py
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── request_id.py
│   │   └── error_handler.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── pagination.py
│       └── validators.py
│
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_auth.py
│   ├── test_users.py
│   ├── test_papers.py
│   ├── test_documents.py
│   ├── test_chat.py
│   └── test_search.py
│
├── requirements.txt
├── alembic.ini
├── Dockerfile
├── .env.example
└── README.md
```

If an existing repository already has a different structure, preserve working code and adapt instead of blindly replacing it.

---

# 6. Layer Responsibilities

Use this separation:

```text
routes/
    HTTP handling only

schemas/
    Request/response validation

services/
    Business logic

repositories/
    Database access

models/
    SQLAlchemy ORM models

integrations/
    External subsystem boundaries

core/
    Configuration/security/dependencies

database/
    DB engine/session/base
```

Example:

```text
POST /papers
     ↓
papers.py
     ↓
PaperService
     ↓
PaperRepository
     ↓
PostgreSQL
```

---

# 7. Configuration

Use environment-based configuration.

Create:

```text
backend/.env.example
```

Example:

```text
APP_ENV=development
APP_NAME=ResearchAssistant

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/researchassistant

JWT_SECRET_KEY=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

CORS_ORIGINS=http://localhost:3000

RAG_SERVICE_URL=
RAG_TIMEOUT_SECONDS=60

KNOWLEDGE_GRAPH_URL=

UPLOAD_DIR=./storage/uploads
MAX_UPLOAD_SIZE_MB=25
```

Never commit real secrets.

Use Pydantic Settings.

Do not hard-code:

- database credentials
- JWT secret
- CORS origins
- service URLs
- upload limits
- RAG timeout

---

# 8. Database

Use PostgreSQL.

Use SQLAlchemy ORM.

Use async SQLAlchemy where appropriate:

```text
create_async_engine
AsyncSession
async_sessionmaker
asyncpg
```

Database access must go through a managed session dependency.

---

# 9. Base Model

Use a common declarative base.

All ORM models should derive from the same metadata/base.

Use UUID identifiers for major entities:

```text
user_id
paper_id
document_id
conversation_id
message_id
```

IDs must remain consistent across the whole architecture.

---

# 10. Core Database Entities

The backend prototype should support these core entities:

```text
User
Paper
Document
Conversation
Message
```

Additional research metadata can be added when required.

---

# 11. User Model

Conceptual fields:

```text
User
├── id
├── email
├── hashed_password
├── full_name
├── is_active
├── created_at
└── updated_at
```

Rules:

- email unique
- email indexed
- password never stored in plaintext
- hashed password never returned in API responses
- inactive users cannot use protected endpoints

---

# 12. Paper Model

A paper represents the research work.

Conceptual fields:

```text
Paper
├── id
├── title
├── abstract
├── authors
├── publication_year
├── doi
├── source_url
├── venue
├── created_at
└── updated_at
```

The exact metadata can evolve.

The important requirement is that every paper has one stable `paper_id`.

That ID is shared with:

```text
RAG
ChromaDB metadata
Neo4j
Frontend
```

---

# 13. Document Model

A document represents the uploaded/local representation of a paper.

Conceptual fields:

```text
Document
├── id
├── paper_id
├── filename
├── storage_path
├── content_type
├── file_size
├── processing_status
├── processing_error
├── created_at
└── updated_at
```

Possible status:

```text
uploaded
processing
indexed
failed
```

Do not create a second unrelated status system inside RAG.

RAG should report processing results back to the backend.

---

# 14. Conversation Model

A conversation belongs to a user.

Conceptually:

```text
Conversation
├── id
├── user_id
├── title
├── created_at
└── updated_at
```

It may optionally be associated with selected papers.

---

# 15. Message Model

Conceptually:

```text
Message
├── id
├── conversation_id
├── role
├── content
├── sources
├── created_at
└── metadata
```

Roles:

```text
user
assistant
```

Assistant messages should preserve citation/source information.

Do not store only the final text if source information is available.

---

# 16. Relationships

Basic relationship structure:

```text
User
 │
 ├──< Conversation
 │        │
 │        └──< Message
 │
 └──< Paper/Document ownership where required

Paper
 │
 └──< Document
```

Use proper foreign keys.

Use indexes on commonly queried foreign keys.

---

# 17. Ownership and Authorization

A user must only be able to access resources they are authorized to access.

For example:

```text
User A
 ↓
Conversation A
 ↓
Messages A
```

User B must not be able to access them by guessing the UUID.

Every protected resource query must enforce ownership/authorization.

Do not rely on frontend restrictions for security.

---

# 18. Authentication

Implement:

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
```

At minimum:

- password hashing
- JWT access tokens
- secure token validation
- protected route dependency
- inactive-user rejection

For the prototype, keep token handling understandable and secure.

If refresh tokens are implemented, use rotation/revocation rather than accepting unlimited long-lived refresh tokens.

---

# 19. Password Security

Never store:

```text
password
```

Store:

```text
hashed_password
```

Never return hashed passwords in response schemas.

Validate password input.

Use a modern password hashing library/configuration supported by the chosen stack.

---

# 20. Authentication Dependency

Create something conceptually equivalent to:

```text
get_current_user()
```

Routes requiring authentication should use it.

Example:

```text
GET /papers
```

may require authenticated user access depending on project policy.

The dependency should:

1. read authorization header
2. validate token
3. extract user ID
4. load user
5. verify active status
6. return user

---

# 21. Paper APIs

Implement core paper operations.

Suggested:

```text
POST   /api/v1/papers
GET    /api/v1/papers
GET    /api/v1/papers/{paper_id}
PATCH  /api/v1/papers/{paper_id}
DELETE /api/v1/papers/{paper_id}
```

For the prototype, delete can be restricted or implemented as soft deletion if required.

---

# 22. Paper Search

Create:

```text
GET /api/v1/search
```

The backend search layer should initially support metadata/database search.

Example query parameters:

```text
q
author
year
page
page_size
```

Do not confuse this with vector retrieval.

Vector retrieval belongs to RAG.

Possible architecture:

```text
Search API
   ├── metadata/database search
   └── future RAG semantic search
```

---

# 23. Document Upload

Suggested:

```text
POST /api/v1/documents/upload
```

Request:

```text
multipart/form-data
```

Accept research paper PDFs for the prototype.

Validate:

- extension/content type
- size
- filename
- empty files

Store file safely.

Create a Document database record.

Do not send raw file bytes directly to the frontend.

---

# 24. Document Processing Flow

Correct flow:

```text
Frontend
   ↓
POST /documents/upload
   ↓
FastAPI
   ↓
Validate file
   ↓
Store file
   ↓
Create Document record
   ↓
processing = processing
   ↓
RAG ingestion
   ↓
RAG returns result
   ↓
processing = indexed / failed
```

For the prototype, this may be synchronous or background execution depending on implementation complexity.

The architecture must allow background processing later.

---

# 25. RAG Integration Boundary

Create:

```text
backend/app/integrations/rag_client.py
```

This is one of the most important files.

It should expose clean operations such as:

```text
ingest_document(...)
answer_question(...)
summarize_paper(...)
compare_papers(...)
```

The backend should not know how:

```text
chunking
embedding
ChromaDB
retrieval
prompt construction
LLM
citation mapping
```

works internally.

It only knows the contract.

---

# 26. RAG Ingestion Contract

Conceptual request:

```json
{
  "document_id": "doc_123",
  "paper_id": "paper_123",
  "file_path": "...",
  "metadata": {}
}
```

Conceptual result:

```json
{
  "status": "indexed",
  "document_id": "doc_123",
  "paper_id": "paper_123",
  "chunk_count": 42,
  "error": null
}
```

The backend uses this result to update Document processing status.

---

# 27. Chat API

Primary endpoint:

```text
POST /api/v1/chat
```

Request:

```json
{
  "question": "What is the main contribution of this paper?",
  "paper_ids": ["paper_123"],
  "conversation_id": null
}
```

Backend flow:

```text
HTTP Request
    ↓
Authentication
    ↓
Validate request
    ↓
Validate paper ownership/access
    ↓
Create/load conversation
    ↓
Call RAG client
    ↓
Receive answer + sources
    ↓
Persist user message
    ↓
Persist assistant message
    ↓
Return response
```

---

# 28. Chat Response Contract

Conceptually:

```json
{
  "conversation_id": "conv_123",
  "message_id": "msg_456",
  "answer": "The paper proposes...",
  "sources": [
    {
      "source_id": "src_001",
      "paper_id": "paper_123",
      "document_id": "doc_123",
      "chunk_id": "chunk_004",
      "page": 4,
      "section": "Methodology",
      "text": "Supporting passage...",
      "score": 0.87
    }
  ]
}
```

The exact schema may evolve.

Do not discard RAG source metadata.

---

# 29. Source/Citation Persistence

Assistant messages should preserve source information.

Possible database representation:

```text
JSON/JSONB
```

or normalized citation tables if needed later.

For prototype simplicity, JSON/JSONB is acceptable.

The source must still contain:

```text
paper_id
document_id
chunk_id
page
section
text
```

---

# 30. Conversation APIs

Suggested:

```text
POST   /api/v1/conversations
GET    /api/v1/conversations
GET    /api/v1/conversations/{conversation_id}
GET    /api/v1/conversations/{conversation_id}/messages
DELETE /api/v1/conversations/{conversation_id}
```

All must enforce ownership.

---

# 31. Conversation + RAG

When the user asks:

```text
What is the main contribution?
```

then:

```text
user message
    ↓
RAG query
    ↓
answer + sources
    ↓
assistant message
```

For follow-up questions:

```text
What dataset did they use?
```

the backend should provide enough conversation context for the RAG/chat service to understand the current conversation.

Do not blindly send the entire conversation forever.

Keep context bounded.

---

# 32. Multi-Paper Chat

The frontend can send:

```json
{
  "question": "Compare the methodologies.",
  "paper_ids": [
    "paper_A",
    "paper_B"
  ],
  "conversation_id": "conv_123"
}
```

Backend must:

1. validate both papers
2. verify user access
3. pass both IDs to RAG
4. receive paper-specific sources
5. preserve source identity
6. persist response

---

# 33. Summary API

Possible:

```text
POST /api/v1/papers/{paper_id}/summary
```

Backend:

```text
validate paper
    ↓
RAG summarize_paper()
    ↓
return grounded summary
```

The backend does not implement summarization logic.

---

# 34. Compare API

Possible:

```text
POST /api/v1/papers/compare
```

Request:

```json
{
  "paper_ids": [
    "paper_A",
    "paper_B"
  ]
}
```

Backend validates access and calls:

```text
RAG.compare_papers(...)
```

---

# 35. Knowledge Graph Integration

Create:

```text
backend/app/integrations/knowledge_graph_client.py
```

Do not implement Neo4j internals here.

The backend only defines the interface.

Possible future operations:

```text
get_paper_graph(...)
get_related_papers(...)
get_citation_network(...)
get_research_trends(...)
```

Harendra owns the implementation behind the boundary.

---

# 36. API Versioning

Use:

```text
/api/v1/
```

Examples:

```text
/api/v1/auth/login
/api/v1/papers
/api/v1/documents/upload
/api/v1/chat
/api/v1/search
```

This prevents future API changes from breaking the frontend immediately.

---

# 37. Response Schemas

Never return raw SQLAlchemy models directly.

Use Pydantic response schemas.

Example:

```text
ORM Model
    ↓
Pydantic Response Schema
    ↓
JSON
```

This prevents accidental exposure of fields such as:

```text
hashed_password
internal paths
private metadata
```

---

# 38. Error Format

Use a consistent API error shape.

Example:

```json
{
  "error": {
    "code": "PAPER_NOT_FOUND",
    "message": "Paper was not found.",
    "request_id": "req_123"
  }
}
```

Possible error codes:

```text
UNAUTHORIZED
FORBIDDEN
NOT_FOUND
VALIDATION_ERROR
PAPER_NOT_FOUND
DOCUMENT_NOT_FOUND
DOCUMENT_PROCESSING_FAILED
RAG_UNAVAILABLE
RAG_NO_EVIDENCE
INTERNAL_ERROR
```

Do not leak stack traces to clients.

---

# 39. HTTP Status Codes

Use sensible status codes:

```text
200 → successful GET/action
201 → created resource
202 → accepted/background processing
204 → successful deletion with no body
400 → bad request
401 → authentication required/invalid
403 → authenticated but forbidden
404 → resource not found
409 → conflict
422 → validation failure
500 → unexpected server error
503 → dependent service unavailable
```

---

# 40. Health Checks

Implement:

```text
GET /health
GET /health/ready
```

`/health` should indicate that the API process is alive.

`/health/ready` should verify critical dependencies where practical:

```text
PostgreSQL
RAG dependency if applicable
```

Do not make a health endpoint unnecessarily expensive.

---

# 41. Request IDs

Add a request ID middleware.

Every request should have or receive:

```text
X-Request-ID
```

Use the request ID in logs and error responses.

This makes debugging frontend → backend → RAG failures much easier.

---

# 42. Logging

Log useful events:

```text
request started
request completed
user authenticated
paper created
document uploaded
RAG ingestion started
RAG ingestion completed
chat request started
RAG query failed
database error
```

Never log:

```text
passwords
JWT secrets
API keys
authorization tokens
```

---

# 43. File Storage

For prototype:

```text
storage/
└── uploads/
```

or configurable `UPLOAD_DIR`.

Store files using generated safe filenames/IDs rather than trusting user-provided filenames as filesystem paths.

Example concept:

```text
storage/uploads/{document_id}.pdf
```

Keep original filename in the database.

Do not allow path traversal.

---

# 44. File Validation

For uploaded PDFs:

Check:

```text
file exists
file is not empty
file size <= configured limit
content type
extension
```

Where practical, inspect file signature rather than trusting extension alone.

Reject unsupported formats cleanly.

---

# 45. Database Migrations

Use Alembic.

Never manually modify production/shared database schemas.

Workflow:

```text
Modify SQLAlchemy model
        ↓
Create migration
        ↓
Review migration
        ↓
Apply migration
```

Commands should follow the project's environment.

Typical:

```bash
alembic revision --autogenerate -m "create paper tables"
alembic upgrade head
```

Commit migration files.

---

# 46. Database Indexes

Index fields frequently used for:

```text
email
paper_id
document_id
user_id
conversation_id
created_at
publication_year
```

Do not add indexes blindly.

Use indexes that support actual queries.

---

# 47. Transactions

Use database transactions for operations that must be atomic.

Example:

```text
Create paper
+
Create document metadata
```

if both are part of one logical operation.

On failure:

```text
rollback
```

Do not leave half-created records.

---

# 48. Repository Pattern

Database access should be isolated in repositories.

Example:

```text
PaperRepository
├── create()
├── get_by_id()
├── list()
├── update()
└── delete()
```

Services decide business behavior.

Routes should not contain long database query logic.

---

# 49. Service Layer

Example:

```text
PaperService
```

responsibilities:

- validate business rules
- call repositories
- coordinate integrations
- handle transactions where appropriate

Example:

```text
ChatService
```

responsibilities:

```text
validate conversation
validate paper access
save user message
call RAG
save assistant message
return response
```

---

# 50. Chat Service Flow

The core implementation should be:

```text
Chat Route
   ↓
Authentication
   ↓
ChatService
   ↓
Validate user
   ↓
Validate paper IDs
   ↓
Load/create conversation
   ↓
Save user message
   ↓
RAGClient.answer_question()
   ↓
Receive RAGResult
   ↓
Save assistant message + sources
   ↓
Return ChatResponse
```

---

# 51. RAG Failure Handling

If RAG is unavailable:

```text
503 RAG_UNAVAILABLE
```

If RAG has no supporting evidence:

```text
200
```

with an answer that clearly indicates insufficient evidence, depending on RAG contract.

Do not invent an answer in the backend.

The backend must never fabricate citations.

---

# 52. RAG Timeout

Use a configured timeout.

If RAG takes too long:

```text
timeout
   ↓
structured error
```

Do not leave HTTP requests hanging indefinitely.

---

# 53. Async Processing

Document ingestion may eventually be asynchronous:

```text
Upload
 ↓
202 Accepted
 ↓
Background worker
 ↓
RAG indexing
 ↓
Document status = indexed
```

For the first prototype, synchronous processing is acceptable if it keeps the implementation simpler and reliable.

Do not introduce Celery just because it sounds production-grade.

Use background processing when document processing actually becomes too slow for a normal request.

---

# 54. Optional Redis

Redis should not become a mandatory dependency unless required.

Potential uses later:

```text
caching
rate limiting
job queue
temporary processing state
```

Do not store core persistent application data only in Redis.

PostgreSQL remains the source of truth for application records.

---

# 55. API Documentation

FastAPI automatically exposes:

```text
/docs
/redoc
```

Use clear:

- endpoint descriptions
- request schemas
- response schemas
- error responses
- authentication requirements

Document the important integration contracts.

---

# 56. CORS

Allow the frontend development origin through configuration.

Example:

```text
http://localhost:3000
```

Do not use unrestricted CORS in the final configuration.

Do not hard-code production origins.

---

# 57. Testing Structure

Backend tests:

```text
tests/
├── conftest.py
├── test_health.py
├── test_auth.py
├── test_users.py
├── test_papers.py
├── test_documents.py
├── test_chat.py
└── test_search.py
```

Test both success and failure cases.

---

# 58. Authentication Tests

Test:

```text
register
duplicate email
login
wrong password
invalid token
expired/invalid token
inactive user
me endpoint
logout/refresh if implemented
```

---

# 59. Paper Tests

Test:

```text
create paper
get paper
list papers
update paper
delete/soft delete
unknown paper
unauthorized access
cross-user access
pagination
```

---

# 60. Document Tests

Test:

```text
valid PDF
empty file
unsupported file
oversized file
document metadata
paper relationship
processing status
RAG ingestion success
RAG ingestion failure
```

Do not require real external LLM calls in unit tests.

Use mocks.

---

# 61. Chat Tests

Test:

```text
new conversation
existing conversation
single-paper question
multi-paper question
unauthorized paper
RAG success
RAG timeout
RAG unavailable
no evidence
source persistence
message persistence
```

Mock `RAGClient`.

---

# 62. Integration Test

At least one integration flow should verify:

```text
Register
   ↓
Login
   ↓
Create/Upload Paper
   ↓
Create Conversation
   ↓
Ask Question
   ↓
RAG Client
   ↓
Persist Assistant Answer
   ↓
Return Sources
```

For the backend test, RAG can be a deterministic mock.

---

# 63. Database Test Isolation

Tests must not corrupt development data.

Use:

```text
test database
```

or an isolated test transaction/database strategy.

Do not run destructive test fixtures against the developer's normal PostgreSQL database.

---

# 64. Docker

The backend should be easy to run locally.

A practical setup can contain:

```text
backend/API
PostgreSQL
```

and optionally:

```text
Redis
worker
```

only when required.

The entire team should eventually be able to start required infrastructure through the repository's Docker setup.

---

# 65. Docker Environment

Example conceptual services:

```text
api
postgres
```

Optional later:

```text
redis
worker
```

Do not create unnecessary services.

---

# 66. Backend README

`backend/README.md` must explain:

```text
Backend purpose
Architecture
Folder structure
Environment setup
Database setup
Migration commands
Running API
Running tests
API documentation
RAG integration
File upload behavior
```

Also provide example API requests.

---

# 67. Backend ↔ Frontend Contract

Himanshu should not need to understand backend internals.

He needs:

```text
endpoint
method
request
response
authentication
errors
```

Example:

```text
POST /api/v1/chat
```

Request:

```json
{
  "question": "...",
  "paper_ids": ["..."],
  "conversation_id": null
}
```

Response:

```json
{
  "conversation_id": "...",
  "message_id": "...",
  "answer": "...",
  "sources": []
}
```

The frontend never calls:

```text
PostgreSQL
ChromaDB
LLM
Neo4j
```

directly.

---

# 68. Backend ↔ RAG Contract

The RAG integration should be documented in:

```text
docs/architecture/integration-boundaries.md
```

Minimum operations:

```text
ingest_document()
answer_question()
summarize_paper()
compare_papers()
```

RAG result must preserve:

```text
answer
sources
metadata
```

Source:

```text
source_id
paper_id
document_id
chunk_id
page
section
text
score
```

---

# 69. Backend ↔ Knowledge Graph Contract

Keep a separate integration boundary.

Possible future operations:

```text
get_citation_network()
get_related_papers()
get_paper_graph()
get_research_trends()
```

The backend should not contain Neo4j query code unless Harendra's implementation specifically requires the integration to live there.

---

# 70. Shared IDs

This is a critical architecture rule.

Use:

```text
paper_id
document_id
chunk_id
conversation_id
message_id
user_id
```

consistently.

For example:

```text
PostgreSQL
    paper_id = P123

RAG
    paper_id = P123

ChromaDB metadata
    paper_id = P123

Neo4j
    paper_id = P123

Frontend
    paper_id = P123
```

Never generate unrelated IDs for the same entity in each subsystem.

---

# 71. Git Rules

Never push directly to:

```text
main
```

Use:

```text
feature/...
bugfix/...
refactor/...
test/...
docs/...
```

Examples:

```text
feature/abhay-auth
feature/abhay-paper-api
feature/abhay-document-upload
feature/abhay-chat-api
feature/abhay-rag-integration

bugfix/abhay-document-validation

test/abhay-chat-api
```

---

# 72. Commit Rules

Use:

```text
feat:
fix:
refactor:
test:
docs:
chore:
```

Examples:

```text
feat: add paper CRUD endpoints
feat: implement JWT authentication
feat: add document upload flow
feat: integrate RAG client

fix: enforce paper ownership on chat requests

test: add document upload validation tests

docs: document chat API contract
```

Avoid:

```text
final
done
changes
update
new code
```

---

# 73. Pull Request Rules

Every backend PR should state:

```text
What changed?
Why?
How was it tested?
Which APIs changed?
Which database models changed?
Which migrations were added?
Does RAG integration change?
Does frontend need changes?
```

If an API contract changes, notify Himanshu.

If the RAG contract changes, notify Gorav.

If the graph contract changes, notify Harendra.

---

# 74. Migration Rules

When changing models:

```text
SQLAlchemy model
    ↓
Alembic migration
    ↓
Test migration
    ↓
Commit migration
```

Never:

```text
manually modify PostgreSQL
```

without a corresponding migration.

---

# 75. Implementation Order

Build in this order:

```text
1. Inspect existing repository
        ↓
2. Establish backend structure
        ↓
3. Configuration
        ↓
4. PostgreSQL connection
        ↓
5. SQLAlchemy base/session
        ↓
6. Core models
        ↓
7. Alembic
        ↓
8. Health endpoint
        ↓
9. Authentication
        ↓
10. Paper APIs
        ↓
11. Document upload
        ↓
12. Conversation/message models
        ↓
13. RAG integration client
        ↓
14. Chat API
        ↓
15. Summary/compare APIs
        ↓
16. Search API
        ↓
17. Knowledge graph integration boundary
        ↓
18. Error handling
        ↓
19. Logging/request IDs
        ↓
20. Tests
        ↓
21. Documentation
        ↓
22. Full integration test
```

---

# 76. First Working Backend Milestone

The backend should first be able to:

```text
Start FastAPI
    ↓
Connect PostgreSQL
    ↓
Run migrations
    ↓
Register user
    ↓
Login
    ↓
Create paper
    ↓
Upload document
```

Only after this is stable should chat/RAG integration be connected.

---

# 77. Chat Working Milestone

Then:

```text
Login
 ↓
Upload paper
 ↓
Document indexed
 ↓
Create conversation
 ↓
POST /chat
 ↓
Backend validates paper
 ↓
RAG client
 ↓
RAG answer + sources
 ↓
Backend stores messages
 ↓
Frontend receives answer + sources
```

---

# 78. Full System Working Flow

The final system should look like:

```text
                 HIMANSHU
                FRONTEND
                    │
                    │ HTTP/JSON
                    ▼
              ┌─────────────┐
              │   ABHAY     │
              │   FASTAPI   │
              └──────┬──────┘
                     │
       ┌─────────────┼──────────────┐
       │             │              │
       ▼             ▼              ▼
 PostgreSQL      RAG Client      Graph Client
       │             │              │
       │             ▼              ▼
       │          GORAV          HARENDRA
       │           RAG             Neo4j
       │             │
       │       ┌─────┴─────┐
       │       ▼           ▼
       │   ChromaDB       LLM
       │
       ▼
 Application Data
```

---

# 79. What Backend Must Never Do

Do not:

```text
put SQL queries in routes
put RAG logic in routes
put LLM prompts in routes
expose database credentials
expose LLM API keys
trust frontend authorization
store plaintext passwords
return ORM models blindly
generate random replacement IDs
bypass migrations
commit .env
```

---

# 80. Prototype Scope

Do not build unnecessarily:

```text
Kubernetes
microservices
complex event buses
large Celery infrastructure
advanced caching
enterprise RBAC
complex billing
production-grade object-storage orchestration
complex distributed tracing
```

The target is:

```text
clean
working
understandable
testable
integration-ready
```

---

# 81. Definition of Done

Backend is considered complete for the prototype when:

```text
[ ] FastAPI starts
[ ] PostgreSQL connection works
[ ] Alembic migrations work
[ ] Health endpoint works
[ ] Authentication works
[ ] User authorization works
[ ] Paper CRUD works
[ ] Paper ownership is enforced
[ ] PDF upload works
[ ] Document metadata is persisted
[ ] Document processing status works
[ ] RAG integration client exists
[ ] Chat endpoint works
[ ] Conversations persist
[ ] Messages persist
[ ] RAG sources persist/return
[ ] Multi-paper chat works
[ ] Summary endpoint works
[ ] Compare endpoint works
[ ] Search endpoint works
[ ] Errors are structured
[ ] Request IDs exist
[ ] Secrets are protected
[ ] Tests pass
[ ] API docs work
[ ] Frontend can consume API contracts
[ ] RAG integration works with Gorav's implementation
[ ] Graph integration boundary is ready
```

---

# 82. Final Backend Responsibility

Abhay's backend should be the **stable bridge between the user-facing application and the intelligence systems**.

The key responsibility is:

```text
Frontend
    ↓
Reliable API
    ↓
Authentication + Authorization
    ↓
Persistent Application State
    ↓
RAG / Research Intelligence
    ↓
Structured Response
    ↓
Frontend
```

The backend should make the rest of the system easy to integrate without taking ownership of their internal implementations.

---

# 83. Final Rule

The backend should answer:

> "Who is the user, what resource are they accessing, what are they asking for, where should that request go, what should be persisted, and what structured result should be returned?"

RAG should answer:

> "What evidence is relevant, what should the model answer, and which sources support that answer?"

Knowledge Graph should answer:

> "What papers, citations, relationships, and research trends are connected?"

Frontend should answer:

> "How should all of this be presented to the user?"

Keep these boundaries clean.

# END