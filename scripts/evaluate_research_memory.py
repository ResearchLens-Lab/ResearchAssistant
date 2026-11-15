"""Evaluate a hand-judged memory fixture: python scripts/evaluate_research_memory.py [fixture.json]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from backend.app.services.research_memory_evaluation import evaluate_memory_fixture

fixture_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "backend/tests/fixtures/phase6_synthetic_memory.json"
print(json.dumps(evaluate_memory_fixture(json.loads(fixture_path.read_text(encoding="utf-8"))), indent=2))
