# Contributing to ResearchLens

Thank you for your interest in contributing to **ResearchLens**! We welcome improvements, bug fixes, and documentation updates that align with our core design goals.

---

## 🧭 Core Architectural Philosophy

Before contributing code, please keep in mind our non-negotiable principles:

1. **Deterministic & Model-Free First**: The primary engine must run 100% offline on standard CPU hardware without requiring paid cloud AI APIs, external inference endpoints, or downloading neural weights.
2. **Evidence-Grounded**: Every factual statement in generated answers must have an unambiguous, verbatim inline citation (`[S1]`, `[S2]`) pointing to an exact source page and section.
3. **Strict Academic Abstention**: When evidence is missing, the system must report that the requested information was not found in the selected corpus rather than inferring or approximating.
4. **SEC-001 Tenant Isolation**: Any query, index, or storage operation must strictly enforce `owner_id` scoping. No user or project data may be exposed across accounts.

---

## 🛠️ Development Setup

### 1. Prerequisites
- Python 3.12 (or 3.11)
- Node.js 18+ or 20+
- Git

### 2. Environment Preparation
```bash
# Clone the repository
git clone https://github.com/ResearchLens-Lab/ResearchAssistant.git
cd ResearchAssistant

# Set up Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic -c backend/alembic.ini upgrade head
```

### 3. Running the Test Suite
All PRs must pass the test suite before merging:
```bash
# Run backend and RAG tests
pytest backend/tests/ rag/tests/ -v

# Run frontend tests
npm test --prefix frontend
```

---

## 🌿 Branching and Git Workflow

ResearchLens uses a structured branching model:

- `main`: Permanent release branch. Contains tagged, verified production builds.
- `develop`: Permanent integration branch. All feature and bugfix branches merge here via Pull Request.
- `feature/<name>`: New functionality or architecture enhancements.
- `fix/<name>`: Bug fixes and test corrections.
- `docs/<name>`: Documentation additions and improvements.
- `chore/<name>`: Maintenance, dependency updates, and refactoring.

### Pull Request Checklist
- Branch from `develop` and target `develop` for your PR.
- Ensure all 500+ unit and integration tests pass cleanly.
- Include unit tests covering any new logic or bug fixes.
- Follow existing formatting and typing conventions.
