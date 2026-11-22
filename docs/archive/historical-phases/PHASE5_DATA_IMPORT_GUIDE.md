# Phase 5 Data Import and Review Guide

## 1. Apply the additive migration

The graph CLI requires revision `0005`. Run the migration against the intended application database after checking the configured `DATABASE_URL`:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

The graph migration was tested on a temporary isolated SQLite database with `alembic check`. It has not been applied to the configured app database. Downgrading to `0004` drops all Phase 5 graph tables and their contents; do that only when intentionally removing graph data and after a backup.

## 2. Prepare one Phase 4 extraction

Use the existing Phase 4 CLI on a selected document. Review and approve records there first. List successful runs and select the **current successful run**; Phase 5 rejects older superseded runs.

```powershell
.\.venv\Scripts\python.exe -m rag.document_intelligence.cli runs --document-id DOCUMENT_ID
.\.venv\Scripts\python.exe -m rag.document_intelligence.cli show --document-id DOCUMENT_ID --run-id RUN_ID
```

The `document-id` must identify a document in the authenticated user's library. Pending or rejected Phase 4 records are skipped.

## 3. Preview then import

The local CLI reads DB settings unless `--db-url` overrides them. Global options go before the command.

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli import-dry-run --owner-id USER_ID --document-id DOCUMENT_ID --run-id RUN_ID
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli import --owner-id USER_ID --document-id DOCUMENT_ID --run-id RUN_ID --confirm
```

For a private Phase 4 source, explicitly opt in for each import and later graph review operation:

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli import-dry-run --owner-id USER_ID --document-id DOCUMENT_ID --run-id RUN_ID --allow-private
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli import --owner-id USER_ID --document-id DOCUMENT_ID --run-id RUN_ID --allow-private --confirm
```

Imports create pending candidates only. Repeating an identical import is idempotent. If preview or import reports excluded records, review its reasons before proceeding.

## 4. Review candidates and create accepted nodes/edges

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli candidates --owner-id USER_ID
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli candidate --owner-id USER_ID --candidate-id CANDIDATE_ID
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli review-candidate --owner-id USER_ID --candidate-id CANDIDATE_ID --action approve-node --node-type METHOD --name "Example Method" --reviewer "local reviewer"
```

Assign an existing canonical node instead of creating one:

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli review-candidate --owner-id USER_ID --candidate-id CANDIDATE_ID --action approve-node --node-type METHOD --existing-node-id NODE_ID --reviewer "local reviewer"
```

Create a directed relationship only after selecting both approved endpoints and checking the exact cited passage:

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli add-edge --owner-id USER_ID --candidate-id CANDIDATE_ID --source-node-id PAPER_NODE_ID --relationship USES_METHOD --target-node-id METHOD_NODE_ID --reviewer "local reviewer"
```

The relationship endpoint types are validated. The system does not infer the triple from text or co-occurrence. API review attribution comes from the authenticated user identity; CLI reviewer text is for a trusted local operator.

## 5. Query, audit, and correct

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli search --owner-id USER_ID --query "algorithm" --type METHOD
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli neighborhood --owner-id USER_ID --node-id NODE_ID --depth 2 --relationship-types USES_METHOD,PROPOSES --node-types PAPER,METHOD
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli path --owner-id USER_ID --source-id DATASET_NODE_ID --target-id METHOD_NODE_ID --max-depth 2 --relationship-types EVALUATED_ON,USES_METHOD --node-types PAPER,METHOD
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli evidence --owner-id USER_ID --node-id NODE_ID
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli audit --owner-id USER_ID
```

Depth is capped at four and results at 200. Path and neighborhood results include evidence text and source pages. Other review operations include `correct-node`, `correct-edge`, `edge-status`, `add-alias`, `identity-suggestions`, `reject-match`, `merge-nodes`, `undo-merge`, and `history`.

An import can be rolled back only while all candidates remain pending; the import history is retained:

```powershell
.\.venv\Scripts\python.exe -m backend.app.services.knowledge_graph_cli rollback-import --owner-id USER_ID --import-run-id IMPORT_ID --reviewer "local reviewer" --reason "review withdrew import"
```

Merge undo uses the recorded decision ID and restores original relationship endpoints and evidence/alias mappings.

## Authenticated API

All endpoints are under `/api/v1/knowledge-graph` and require the existing bearer-token authentication. Key routes include `/status`, `/imports/dry-run`, `/imports` (`confirm: true` required), `/candidates`, `/nodes`, `/nodes/{id}/evidence`, `/nodes/{id}/neighborhood`, `/paths`, `/identity/merge`, and `/audit` (via `/status`). Every query is scoped to the authenticated owner's library; API reviewer identity is assigned from the token, not client input.
