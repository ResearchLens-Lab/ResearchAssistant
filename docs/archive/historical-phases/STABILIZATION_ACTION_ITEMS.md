# ResearchLens Phase 1-7 Stabilization - Action Items

**Date**: November 10, 2026  
**Status**: ⚠️ **BLOCKED BY PYTHON ENVIRONMENT**  
**Priority**: 🔴 **CRITICAL SECURITY FIXES REQUIRED**

---

## 🚨 CRITICAL BLOCKER

**ENV-001**: Python virtual environment is broken and preventing all implementation work.

### Immediate Action Required

```powershell
# 1. Install Python 3.12+ from python.org
# Download from: https://www.python.org/downloads/

# 2. Create new virtual environment
python -m venv .venv --clear

# 3. Activate
.venv\Scripts\activate

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt
pip install -r backend/requirements.txt

# 6. Verify
python -m pytest --version
python -c "import rag; import backend; print('✓ Imports successful')"
```

**Estimated Time**: 15 minutes

---

## 🔴 PHASE 1: Security Fixes (CRITICAL - Cannot Deploy Without)

### SEC-001: RAG Owner Isolation (P0 - CRITICAL)

**Risk**: ANY user can query ANY paper if they know the paper_id. Complete cross-user data breach.

**Files to Modify**:

1. **`rag/chunking/metadata.py`** - Add `owner_id` field to `ChunkMetadata`
   - Lines: +5 additions, ~15 modifications
   - See: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 3.2 FIX SEC-001-A

2. **`rag/retrieval/filters.py`** - Make `owner_id` mandatory in filters
   - Lines: +3 additions, ~10 modifications
   - See: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 3.2 FIX SEC-001-B

3. **`rag/retrieval/retriever.py`** - Thread `owner_id` through retrieval
   - Lines: +2 additions, ~5 modifications
   - See: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 3.2 FIX SEC-001-C

4. **`backend/app/integrations/rag_client.py`** - Make `user_id` required
   - Lines: +3 additions, ~5 modifications
   - See: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 3.2 FIX SEC-001-D

5. **`backend/app/integrations/rag_gateway.py`** - Enforce `user_id` at gateway
   - Lines: +3 additions, ~5 modifications
   - See: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 3.2 FIX SEC-001-E

6. **`backend/app/api/routes/query.py`** - Always pass authenticated user
   - Lines: ~10 modifications
   - See: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 3.2 FIX SEC-001-F

**After Code Changes**:

```bash
# Backup vector store
cp -r .chroma ".chroma.backup.$(Get-Date -Format 'yyyyMMdd')"

# Run migration script (DESTRUCTIVE - re-ingests all documents)
python backend/scripts/migrate_vectorstore_add_owner_id.py
# Type 'CONFIRM' when prompted

# Run security tests
pytest backend/tests/security/test_cross_user_isolation.py -v
# ALL TESTS MUST PASS
```

**Estimated Time**: 2-3 hours (code changes + migration + testing)

---

### SEC-002: Rate Limiting (P1 - HIGH)

**Risk**: No protection against API abuse, external API cost explosion.

**Implementation**: ✅ **READY** - File created at `backend/app/middleware/rate_limit.py`

**Integration Required**:

```python
# File: backend/app/main.py

from backend.app.middleware.rate_limit import RateLimitMiddleware

app = FastAPI(...)

# Add BEFORE other middleware
app.add_middleware(RateLimitMiddleware)
```

**Testing**:

```bash
# Create test file
# backend/tests/security/test_rate_limiting.py

pytest backend/tests/security/test_rate_limiting.py -v
```

**Estimated Time**: 30 minutes (integration + testing)

---

### SEC-003: API Resilience (P1 - HIGH)

**Risk**: External API failures cause cascading system failures.

**Files to Create**:

1. **`rag/generation/api_resilience.py`** - Circuit breaker + retry logic
   - See: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 3.5 FIX SEC-003

2. **Update `rag/generation/llm_provider.py`** - Integrate resilience wrapper

**Testing**:

```bash
pytest rag/tests/test_api_resilience.py -v
```

**Estimated Time**: 1-2 hours (implementation + testing)

---

## 🟠 PHASE 2: Database Migrations (HIGH)

### Apply Phase 5-7 Schema Changes

**Prerequisites**: 
- ✅ SEC-001 fixes applied (owner isolation in code)
- ✅ Database backup completed

**Procedure**:

```bash
# 1. Backup database
$env:DATABASE_URL = "postgresql://user:pass@host/db"
pg_dump $env:DATABASE_URL > "backup_phase5-7_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"

# 2. Apply migrations in order
cd backend

alembic upgrade 0005
# Verify: alembic current should show "0005"

alembic upgrade 978943c31f5c
# Verify: alembic current should show "978943c31f5c"

alembic upgrade a8c7d9e2f104
# Verify: alembic current should show "a8c7d9e2f104 (head)"

# 3. Run SQL validation queries
# See: STABILIZATION_IMPLEMENTATION_REPORT.md Section 2.3
```

**Validation Checklist**:

```sql
-- Run these queries after each migration
-- See Section 2.3 of STABILIZATION_IMPLEMENTATION_REPORT.md for full SQL

-- Check owner_id columns exist with NOT NULL constraint
-- Check FK constraints to users.id with CASCADE
-- Check indexes on owner_id columns
```

**Estimated Time**: 1 hour (backup + apply + validate)

---

## 🟡 PHASE 3: Integration (MEDIUM)

### Integrate Phase 4-7 Features into Query Workflow

**Current State**: Phase 4-7 schemas exist but features are NOT user-accessible.

**Files to Create**:

1. **`backend/app/services/query_enrichment.py`** - KG enrichment
2. **`backend/app/services/memory_integration.py`** - Memory retrieval
3. **`backend/app/services/intelligence_integration.py`** - Quality assessment
4. **`backend/app/services/integrated_query.py`** - Orchestration service
5. **`backend/app/api/routes/integrated_query.py`** - HTTP endpoint

**See**: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 5.2 for complete implementations

**Testing**:

```bash
# Create integration tests
pytest backend/tests/integration/test_phase4_7_integration.py -v
```

**Estimated Time**: 4-6 hours (5 services + API route + tests)

---

## 🔵 PHASE 4: Validation & Documentation (LOW)

### 4.1 Test Execution

```bash
# Full test suite
pytest backend/tests/ rag/tests/ -v --tb=short

# Security tests
pytest backend/tests/security/ -v

# Integration tests
pytest backend/tests/integration/ -v

# Coverage report
pytest --cov=backend --cov=rag --cov-report=html
# Target: >80% coverage
```

### 4.2 Documentation

- [ ] API documentation (OpenAPI/Swagger)
- [ ] Deployment runbook
- [ ] Monitoring setup guide
- [ ] Incident response procedures
- [ ] User guides for Phase 4-7 features

**Estimated Time**: 4-6 hours

---

## 📊 Overall Timeline

| Phase | Description | Priority | Est. Time | Blocking |
|-------|-------------|----------|-----------|----------|
| **ENV-001** | Fix Python environment | 🔴 CRITICAL | 15 min | - |
| **Phase 1** | Security fixes | 🔴 CRITICAL | 4-6 hours | ENV-001 |
| **Phase 2** | Database migrations | 🟠 HIGH | 1 hour | Phase 1 |
| **Phase 3** | Phase 4-7 integration | 🟡 MEDIUM | 4-6 hours | Phase 2 |
| **Phase 4** | Testing & docs | 🔵 LOW | 4-6 hours | Phase 3 |
| **TOTAL** | | | **14-20 hours** | |

---

## ✅ Pre-Deployment Checklist

Before deploying to production, verify:

- [ ] **ENV-001**: Python environment working, all tests runnable
- [ ] **SEC-001**: RAG owner isolation implemented and tested
- [ ] **SEC-002**: Rate limiting active and tested
- [ ] **SEC-003**: API resilience implemented
- [ ] **MIG-001**: All migrations applied successfully
- [ ] **Database Validation**: SQL audit queries pass
- [ ] **Security Tests**: All tests in `test_cross_user_isolation.py` pass
- [ ] **Integration Tests**: Phase 4-7 features accessible via API
- [ ] **Test Coverage**: >80% coverage achieved
- [ ] **Documentation**: Deployment runbook complete
- [ ] **Backup**: Database and ChromaDB backups verified
- [ ] **Monitoring**: Alerts configured for security violations

---

## 🆘 Rollback Procedures

### If SEC-001 Migration Fails

```bash
# Restore ChromaDB backup
rm -rf .chroma
cp -r .chroma.backup.YYYYMMDD .chroma

# Users can still query (with security vulnerability)
# Fix code issues and re-run migration
```

### If Database Migration Fails

```bash
# Downgrade to previous migration
cd backend
alembic downgrade -1

# Or restore from backup
psql $DATABASE_URL < backup_phase5-7_TIMESTAMP.sql
```

### If Rate Limiting Causes Issues

```python
# File: backend/app/main.py

# Comment out rate limit middleware temporarily
# app.add_middleware(RateLimitMiddleware)

# Adjust limits and re-deploy
app.add_middleware(
    RateLimitMiddleware,
    query_limit_per_minute=50,  # Increase if needed
    ingest_limit_per_hour=10,
)
```

---

## 📞 Support & Resources

### Key Documentation Files

- **Main Report**: `STABILIZATION_IMPLEMENTATION_REPORT.md` (comprehensive findings + fixes)
- **Audit**: `docs/audits/phase1-7/MASTER_AUDIT_REPORT.md` (original findings)
- **Checklist**: `docs/audits/phase1-7/PRODUCTION_READINESS_CHECKLIST.md`

### Code Reference

- **Security Fixes**: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 3
- **Migration SQL**: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 2.3
- **Integration Architecture**: `STABILIZATION_IMPLEMENTATION_REPORT.md` Section 5
- **Test Specifications**: `backend/tests/security/test_cross_user_isolation.py`

### Created Files (Ready to Use)

✅ `backend/scripts/migrate_vectorstore_add_owner_id.py` - Vector store migration script  
✅ `backend/app/middleware/rate_limit.py` - Rate limiting middleware  
✅ `backend/tests/security/test_cross_user_isolation.py` - Security test suite

---

## 🎯 Success Criteria

Stabilization is complete when:

1. ✅ Python environment operational (ENV-001 resolved)
2. ✅ All security tests pass (no cross-user data leaks)
3. ✅ Migrations applied successfully (Phase 5-7 schemas active)
4. ✅ Rate limiting preventing API abuse
5. ✅ Phase 4-7 features accessible via integrated query API
6. ✅ Test coverage >80%
7. ✅ Documentation complete
8. ✅ No P0 or P1 security findings unresolved

**Current Status**: 2/8 complete (Environment blocked, code specifications ready)

---

**Next Immediate Action**: Fix Python environment (ENV-001) - takes 15 minutes, unblocks everything else.
