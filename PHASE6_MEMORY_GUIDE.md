# Phase 6 Local Memory Guide

## Apply the migration when ready

Inspect the configured database and apply only to the intended local database:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

The implementation task left the configured database unchanged.

## API

All endpoints are authenticated under `/api/v1/research-memory`:

- `GET /status`
- `POST /formation/preview` and `POST /formation` with explicit selected `node_ids` / `relationship_ids`
- `POST /search`
- `GET /items/{memory_id}`, `/items/{memory_id}/history`, `/items/{memory_id}/neighborhood`
- `GET /associations/candidates`, `POST /associations/{id}/review`
- `GET /contradictions`, `POST /contradictions/{id}/resolve`
- `GET /gaps`, `POST /gaps`, `POST /gaps/{id}/resolve`
- `POST /feedback`, `GET /audit`
- `POST /sessions/{conversation_id}/opt-in`, `/capture`; `GET` and `DELETE /sessions/memories`

Formation previews source eligibility before any write. Private graph evidence requires explicit `allow_private: true` per request. Associations are suggestions until reviewed. Search labels direct passage evidence separately from connections and unresolved items.

## CLI

Examples run from the repository root. The local CLI is for a trusted operator and requires an explicit owner ID; the API derives owner scope from authentication.

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.research_memory_cli --owner-id USER_ID status
.\.venv\Scripts\python.exe -m backend.app.services.research_memory_cli --owner-id USER_ID preview --node-ids NODE1,NODE2 --relationship-ids EDGE1
.\.venv\Scripts\python.exe -m backend.app.services.research_memory_cli --owner-id USER_ID form --node-ids NODE1,NODE2 --relationship-ids EDGE1 --confirm
.\.venv\Scripts\python.exe -m backend.app.services.research_memory_cli --owner-id USER_ID retrieve --query "algorithm and dataset"
.\.venv\Scripts\python.exe -m backend.app.services.research_memory_cli --owner-id USER_ID associations --status CANDIDATE
.\.venv\Scripts\python.exe -m backend.app.services.research_memory_cli --owner-id USER_ID gaps --status OPEN
.\.venv\Scripts\python.exe -m backend.app.services.research_memory_cli --owner-id USER_ID history --memory-id MEMORY_ID
.\.venv\Scripts\python.exe -m backend.app.services.research_memory_cli --owner-id USER_ID audit
```

The preview and form commands accept only graph IDs chosen by the operator. The service caps one formation at 200 assertions and validates each selected input.

## Evaluation fixture

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_research_memory.py
```

Supply another JSON fixture path to use reviewed gold cases. Results describe only those judgments; they are not real-world accuracy or calibrated probabilities.
