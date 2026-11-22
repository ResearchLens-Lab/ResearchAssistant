# Contributing to ResearchLens

This document outlines the guidelines for contributing to ResearchLens.

---

## Architectural Principles

All contributions must preserve the following system properties:

1. **Deterministic and Model-Free Default**: The primary research engine must function without requiring external cloud inference APIs, neural weights, or dedicated GPUs.
2. **Evidence Grounding**: Factual answers must provide explicit citation tags (`[S1]`, `[S2]`) pointing to exact document page numbers and section headers.
3. **Academic Abstention**: When information is absent from selected documents, the engine must state that the information was not found rather than inferring or approximating.
4. **Tenant Isolation**: All database operations and queries must enforce `owner_id` scoping to prevent data exposure across local user accounts.

---

## Development Setup

### Prerequisites

- Python 3.11 or 3.12
- Node.js 18 or 20
- Git

### Installation

```bash
git clone https://github.com/ResearchLens-Lab/ResearchAssistant.git
cd ResearchAssistant

python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
alembic -c backend/alembic.ini upgrade head
```

### Running Tests

All automated tests must pass before opening a pull request:

```bash
pytest backend/tests/ rag/tests/ -v
npm test --prefix frontend
```

---

## Branching Strategy

ResearchLens maintains two primary branches:

- `main`: Release baseline. Tagged production code only.
- `develop`: Integration branch. All features and fixes target this branch.

Work in branch types prefixed with their purpose:

- `feature/<name>`: New capabilities or enhancements.
- `fix/<name>`: Bug fixes and test repairs.
- `docs/<name>`: Documentation updates.
- `chore/<name>`: Build, dependency, or maintenance tasks.

### Pull Request Requirements

- Target `develop` for all functional pull requests.
- Ensure all test suites pass without regressions.
- Add test coverage for new functionality or bug fixes.
- Avoid introducing hardcoded user profile paths.

---

## Project Governance & Team

ResearchLens is a collaborative team-developed product created under the **ResearchLens-Lab** organization, led by Gorav Gumber:

- **Gorav Gumber** — Project Lead, Technical Architect and RAG Lead.
- **Himanshu Kumawat** — Frontend Lead.
- **Harendra Godara** — Knowledge Graph Lead.
- **Abhay Kumar Singh** — Backend and Database Contributor.

Community contributions are welcomed and coordinated via pull requests targeting the `develop` branch.

---

## Licensing of Contributions

By submitting a pull request to ResearchLens, you agree that your contribution is provided under the terms of the **GNU Affero General Public License v3.0** (AGPL-3.0), as published in [LICENSE](../LICENSE).

All contributors certify that:
1. The contribution was created in whole or in part by them, and they have the right to submit it under the open-source license indicated in the file; or
2. The contribution is based upon previous work that, to the best of their knowledge, is covered under an appropriate open-source license and they have the right under that license to submit that work with modifications; or
3. The contribution was provided directly to them by some other person who certified (1) or (2) and they have not modified it.

We recommend including a Developer Certificate of Origin (DCO) sign-off line in your commit messages:
`Signed-off-by: Random J Developer <random@developer.example.org>`
