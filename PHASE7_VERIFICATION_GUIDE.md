# Phase 7 verification guide

## API

All routes require the existing bearer authentication and are under `/api/v1/research-intelligence`:

- `GET /readiness`
- `POST /questions/analyze`
- `POST /evidence/synthesize`
- `POST /claims/assess`
- `POST /papers/compare`
- `POST /contradictions/analyze`
- `POST /papers/{paper_id}/verify-source`
- `POST /external/lookup` (explicit internet action)
- `POST /gaps/analyze`
- `POST /papers/{paper_id}/quality-review`
- `GET /runs?limit=50&offset=0`
- `GET /runs/{run_id}`
- `GET /evidence/{evidence_id}` (current approved graph evidence only)
- `GET /runs/{run_id}/evidence/{evidence_id}` (evidence snapshot included in that owner's run)

## CLI

From the repository root:

```powershell
python -m backend.app.services.research_intelligence_cli analyze --owner-id USER_ID --question "Compare these methods"
python -m backend.app.services.research_intelligence_cli synthesize --owner-id USER_ID --question "What datasets are reported?" --paper-ids PAPER_ID --result-limit 15 --offline
python -m backend.app.services.research_intelligence_cli compare --owner-id USER_ID --paper-ids PAPER_A PAPER_B
python -m backend.app.services.research_intelligence_cli lookup --owner-id USER_ID --doi 10.example/id --check-external
python -m backend.app.services.research_intelligence_cli verify --owner-id USER_ID --paper-id PAPER_ID --check-external
```

`lookup` refuses to run without `--check-external`. `--document-ids`, `--paper-ids`, `--result-limit`, and `--max-depth` are available on relevant commands. At this stage `--offline` is a declaration that local workflows are selected; local workflows never call web providers. External provider behavior has not been runtime-validated in this implementation turn.

## Validation and migration

Intended checks (not successfully run in this environment because the configured Python runtime is missing its standard-library `encodings` package):

```powershell
python -m pytest backend/tests/test_research_intelligence.py
python -m pytest backend/tests rag/tests
python -m compileall -q backend rag
```

The configured application database was not modified. Before deployment, back up and verify the target database, then apply the prerequisite migrations in order: Phase 5, Phase 6 revision `978943c31f5c`, and Phase 7 revision `a8c7d9e2f104`. Do not run `alembic upgrade head` until the migration chain and target DSN are verified by the operator. Migration upgrade/downgrade has not been tested in this turn.
