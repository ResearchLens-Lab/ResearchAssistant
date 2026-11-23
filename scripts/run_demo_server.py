"""
Runs the FastAPI backend for the demo environment on port 8000.
"""

import os
import sys
from pathlib import Path
import uvicorn

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = REPO_ROOT / "temp_demo_env"

db_path = (DEMO_DIR / "library.sqlite3").resolve().as_posix()
docs_path = (DEMO_DIR / "documents").resolve().as_posix()
indexes_path = (DEMO_DIR / "indexes").resolve().as_posix()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
os.environ["UPLOAD_DIR"] = docs_path
os.environ["CHROMA_PERSIST_DIR"] = indexes_path
os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://127.0.0.1:3000"
os.environ["DESKTOP_RUNTIME"] = "false"
os.environ["RAG_ENGINE_MODE"] = "independent"
os.environ["RAG_ANSWER_MODE"] = "INDEPENDENT"
os.environ["RAG_MODE"] = "local"
os.environ["LLM_ENABLED"] = "false"
os.environ["APP_ENV"] = "development"
os.environ["JWT_SECRET_KEY"] = "super-secret-validation-key-32bytes-min!"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, log_level="info")
