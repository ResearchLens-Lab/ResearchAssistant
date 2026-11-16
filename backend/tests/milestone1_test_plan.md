# Milestone 1 Test Plan - Exact Commands

## Prerequisites
```powershell
# Activate virtual environment
.\.venv_stabilization\Scripts\Activate.ps1

# Verify migration applied
cd backend
alembic current
# Should show: 0006_milestone1 (head)
```

## Backend Tests (8 tests)

### 1. New Upload with Valid PDF
**Test**: Upload new PDF, verify hash stored and operation_type set
```powershell
pytest tests/test_document_service.py::test_upload_new_document -v
```
**Expected**: file_hash_sha256 populated, operation_type=INITIAL_UPLOAD

### 2. Duplicate Indexed Document
**Test**: Re-upload already indexed document
```powershell
pytest tests/test_document_service.py::test_upload_duplicate_indexed -v
```
**Expected**: outcome=already_indexed, no new processing job

### 3. Duplicate Processing Document
**Test**: Upload while same document is processing
```powershell
pytest tests/test_document_service.py::test_upload_duplicate_processing -v
```
**Expected**: outcome=existing_job, return existing document

### 4. Cancel Active Processing
**Test**: Cancel document mid-processing, verify cleanup
```powershell
pytest tests/test_document_service.py::test_cancel_active_processing -v
```
**Expected**: Worker lease released after cleanup, status=CANCELLED

### 5. Retry After Cancel
**Test**: Retry cancelled document with cleanup pending
```powershell
pytest tests/test_document_service.py::test_retry_blocked_during_cleanup -v
```
**Expected**: Retry blocked until cleanup completes

### 6. Retry After Failure
**Test**: Retry failed document
```powershell
pytest tests/test_document_service.py::test_retry_after_failure -v
```
**Expected**: operation_type=RETRY, cleanup_status cleared

### 7. Concurrent Upload Prevention
**Test**: Attempt concurrent processing of same document
```powershell
pytest tests/test_worker_leases.py::test_concurrent_processing_prevented -v
```
**Expected**: Second attempt blocked by active lease

### 8. Stale Lease Detection
**Test**: Process document with stale (>5min) lease
```powershell
pytest tests/test_worker_leases.py::test_stale_lease_detection -v
```
**Expected**: Stale lease treated as expired, new lease acquired

## RAG Tests (3 tests)

### 9. Quality Zero Preserved
**Test**: Low-confidence OCR quality score preserved
```powershell
cd ..
pytest rag/tests/test_index_writer.py::test_quality_zero_preserved -v
```
**Expected**: quality_score=0.0 in lexical_metadata, not converted to 1.0

### 10. Heading Cleanup on Reindex
**Test**: No orphaned headings_fts entries after reindex
```powershell
pytest rag/tests/test_index_writer.py::test_heading_cleanup_on_reindex -v
```
**Expected**: Old heading entries deleted before new chunks inserted

### 11. Reindex Failure Preserves Old Index
**Test**: Simulate reindex failure, verify old chunks intact
```powershell
pytest rag/tests/test_ingest_pipeline.py::test_reindex_preserves_old_on_failure -v
```
**Expected**: Old index chunks still present after reindex fails

## Frontend Manual Tests (2 scenarios)

### 12. Mixed Batch Results
**Manual Test**: Upload 3 files (1 new, 1 duplicate, 1 invalid)
```powershell
cd frontend
npm run dev
```
**Actions**:
1. Open Add Sources modal
2. Select 3 files: new PDF, already uploaded PDF, invalid .xyz file
3. Click "Add sources"

**Expected**:
- Modal stays open
- Shows per-file results with icons
- New: ✓ "New" status
- Duplicate: ✓ "Duplicate" status
- Invalid: ✗ Error message
- Success count: 2, Failure count: 1

### 13. Papers Array Reset
**Manual Test**: Verify memoizedPapers prevents re-renders
**Actions**:
1. Open React DevTools
2. Open Add Sources modal
3. Monitor re-render count
4. Add/remove files without changing papers

**Expected**: Component does not re-render when papers array reference changes

## Quick Test Summary
```powershell
# Run all backend tests
cd backend
pytest tests/test_document_service.py tests/test_worker_leases.py -v

# Run all RAG tests
cd ..
pytest rag/tests/test_index_writer.py rag/tests/test_ingest_pipeline.py -v

# Manual frontend testing
cd frontend
npm run dev
# Then follow scenarios 12 & 13 above
```

## Expected Test Results
- Backend: 8/8 passing
- RAG: 3/3 passing
- Frontend Manual: 2/2 verified
- **Total: 13/13 complete**

## Failure Troubleshooting

If tests fail, check:
1. Migration applied: `alembic current` should show `0006_milestone1`
2. Database connection: Verify .env.local has correct DATABASE_URL
3. Test database: Some tests may need `pytest --create-db`
4. Import errors: Verify all new files are in correct locations

## Notes
- Tests may need to be created if they don't exist yet
- Some tests may be combined into test suites
- Manual frontend tests require ResearchLens desktop app running
- User will handle Git operations after tests pass
