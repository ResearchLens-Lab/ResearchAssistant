## Description

Briefly describe the change and its motivation or context.

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking addition of functionality)
- [ ] Documentation update
- [ ] Code refactoring or cleanup (no functional changes)
- [ ] CI / Build / Packaging enhancement

## Checklist

- [ ] My code adheres to the project's coding standards.
- [ ] Deterministic, model-free offline functionality is preserved.
- [ ] SEC-001 multi-user tenant isolation is maintained.
- [ ] I have added tests that prove my fix is effective or my feature works.
- [ ] All unit and integration tests pass (`pytest backend/tests/ rag/tests/` and `npm test --prefix frontend`).
- [ ] No hardcoded absolute personal paths (e.g. `C:\Users\...`) have been added.
