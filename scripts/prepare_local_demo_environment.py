"""
Setup script to initialize a demo research environment for UI validation.
"""

import asyncio
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = REPO_ROOT / "temp_demo_env"
DEMO_DIR.mkdir(parents=True, exist_ok=True)

db_path = (DEMO_DIR / "library.sqlite3").resolve().as_posix()
docs_path = (DEMO_DIR / "documents").resolve().as_posix()
indexes_path = (DEMO_DIR / "indexes").resolve().as_posix()
Path(docs_path).mkdir(exist_ok=True)
Path(indexes_path).mkdir(exist_ok=True)

# Set environment
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

# Run alembic migrations
from alembic.config import Config
from alembic import command

alembic_cfg = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
print("Running alembic migrations on demo database...")
command.upgrade(alembic_cfg, "head")
print("Migrations complete!")

# Create test user and ingest sample papers
async def seed_data():
    from backend.app.database.session import get_session_factory
    from backend.app.services.auth_service import AuthService
    from backend.app.schemas.auth import RegisterRequest
    from backend.app.models.user import User
    from backend.app.models.paper import Paper
    from backend.app.models.document import Document, DocumentStatus
    from rag.independent.ingest_pipeline import IndependentIngestionPipeline
    from rag.independent.index_writer import IndependentIndexWriter
    import uuid

    lexical_db = Path(indexes_path) / "researchlens_lexical.sqlite3"
    writer = IndependentIndexWriter(db_path=lexical_db)
    ingest_pipe = IndependentIngestionPipeline(index_writer=writer)

    async with get_session_factory()() as db:
        auth_service = AuthService(db)
        try:
            reg_req = RegisterRequest(
                username="researcher",
                email="researcher@example.com",
                password="ResearchPass123!",
                full_name="Research Engineer",
            )
            user_resp = await auth_service.register(reg_req)
            user_id = user_resp.id
            print(f"Created demo user: researcher (id={user_id})")
        except Exception as e:
            print(f"User registration note: {e}")
            from sqlalchemy import select
            res = await db.execute(select(User).filter_by(username="researcher"))
            u = res.scalar_one()
            user_id = u.id

        # Ingest papers
        samples = [
            ("synthetic_algorithms_paper.pdf", "A Comparative Study of Deterministic Algorithmic Paradigms", ["Deterministic Algorithms", "Computational Complexity", "Graph Traversal"]),
            ("algorithm_report.pdf", "ResearchLens Intelligence Brief: What is an algorithm?", ["Algorithm Definition", "Computational Theory"]),
            ("sample_report.pdf", "ResearchLens Intelligence Report: Definition of Algorithm", ["Definitions", "Foundations"]),
        ]

        for fname, title, topics in samples:
            src_file = REPO_ROOT / "desktop" / "samples" / fname
            dest_file = Path(docs_path) / fname
            shutil.copy2(src_file, dest_file)

            paper_id = str(uuid.uuid4())
            doc_id = str(uuid.uuid4())

            paper = Paper(
                id=paper_id,
                title=title,
                authors=["ResearchLens Lab"],
                publication_year=2026,
                owner_id=user_id,
            )
            db.add(paper)
            await db.flush()

            doc = Document(
                id=doc_id,
                paper_id=paper_id,
                filename=fname,
                storage_path=str(dest_file),
                content_type="application/pdf",
                file_size=src_file.stat().st_size,
                file_hash_sha256="hash_" + fname,
                processing_status=DocumentStatus.INDEXED.value,
                processing_progress=100,
                processing_stage="ready",
                processing_completed_units=1,
            )
            db.add(doc)
            await db.commit()

            # Index into FTS5
            res = ingest_pipe.ingest_file(
                file_path=str(dest_file),
                paper_id=paper_id,
                metadata={
                    "document_id": doc_id,
                    "paper_id": paper_id,
                    "owner_id": user_id,
                    "title": title,
                    "filename": fname,
                }
            )
            print(f"Indexed {fname} for paper {paper_id}: {res.chunk_count} chunks, success={res.success}")

    print("Demo environment initialized successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
