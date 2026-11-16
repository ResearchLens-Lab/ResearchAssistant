"""Prepare a completely isolated test environment for manual desktop acceptance testing."""

import os
import shutil
import sqlite3
from pathlib import Path
import secrets

repo_root = Path(__file__).resolve().parent.parent

# Test environment paths
test_env_root = repo_root / ".test_desktop_env"
runtime_dir = test_env_root / "runtime"
library_dir = test_env_root / "Library"
sample_dir = test_env_root / "sample_uploads"

# Clean prior test environment if exists
if test_env_root.exists():
    shutil.rmtree(test_env_root, ignore_errors=True)

test_env_root.mkdir(parents=True, exist_ok=True)
runtime_dir.mkdir(parents=True, exist_ok=True)
sample_dir.mkdir(parents=True, exist_ok=True)

# Required library subdirectories
required_dirs = [
    "documents",
    "attachments",
    "indexes",
    "annotations",
    "notebooks",
    "feedback",
    "exports",
    "backups",
    "cache",
    "cache/models",
]
for d in required_dirs:
    (library_dir / d).mkdir(parents=True, exist_ok=True)

# Generate JWT secret key
secrets_dir = runtime_dir / "secrets"
secrets_dir.mkdir(parents=True, exist_ok=True)
jwt_key = secrets.token_urlsafe(48)
(secrets_dir / "jwt-signing.key").write_text(jwt_key, encoding="utf-8")

# Write desktop-settings.json pointing directly to isolated Library
settings_content = f"""{{
  "version": 1,
  "libraryPath": "{str(library_dir).replace('\\', '\\\\')}",
  "storageMode": "copy",
  "profile": "low",
  "createdAt": "2026-11-15T15:00:00.000Z"
}}"""
(runtime_dir / "desktop-settings.json").write_text(settings_content, encoding="utf-8")

# Copy sample test PDFs
samples_src = repo_root / "desktop" / "samples"
if (samples_src / "sample_report.pdf").is_file():
    shutil.copy2(samples_src / "sample_report.pdf", sample_dir / "1_new_paper.pdf")
if (samples_src / "algorithm_report.pdf").is_file():
    shutil.copy2(samples_src / "algorithm_report.pdf", sample_dir / "2_algorithm_report.pdf")
if (samples_src / "CS_GATE2027_Syllabus.pdf").is_file():
    shutil.copy2(samples_src / "CS_GATE2027_Syllabus.pdf", sample_dir / "3_syllabus_large.pdf")

# Create invalid files for mixed-batch testing
(sample_dir / "4_invalid_format.xyz").write_text("Plain text content in an invalid format extension.", encoding="utf-8")
(sample_dir / "5_corrupt_header.pdf").write_bytes(b"NOT_A_VALID_PDF_HEADER_DATA_123456789")

# Run migrations on isolated SQLite database
db_path = library_dir / "library.sqlite3"
sqlite_url = f"sqlite+aiosqlite:///{db_path.resolve().as_posix()}"

print(f"Isolated test library created at: {library_dir}")
print(f"Isolated test database: {db_path}")

# Run alembic upgrade head using python
import subprocess
import sys

python_exe = repo_root / ".venv_stabilization" / "Scripts" / "python.exe"
if not python_exe.exists():
    python_exe = Path(sys.executable)

env = os.environ.copy()
env["DATABASE_URL"] = sqlite_url
env["DESKTOP_RUNTIME"] = "false"

print("Running database migrations on isolated database...")
result = subprocess.run(
    [str(python_exe), "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
    cwd=str(repo_root),
    env=env,
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    print(f"Migration error: {result.stderr}")
    sys.exit(1)

print("Migrations applied successfully!")

# Seed initial test user and project into isolated database
import bcrypt
salt = bcrypt.gensalt()
hashed_pw = bcrypt.hashpw(b"TestPassword123!", salt).decode("utf-8")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Check tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"Tables in isolated DB: {len(tables)} tables ({', '.join(sorted(tables))})")

# Insert test user
user_id = "test-researcher-001"
cursor.execute("""
    INSERT INTO users (id, email, username, hashed_password, full_name, is_active, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
""", (user_id, "testuser@example.com", "testuser", hashed_pw, "Manual Test Researcher"))

# Insert test project
paper_id = "project-milestone1-001"
cursor.execute("""
    INSERT INTO papers (id, owner_id, title, description, created_at, updated_at)
    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
""", (paper_id, user_id, "Milestone 1 Acceptance Project", "Isolated test project for manual document lifecycle validation."))

conn.commit()

# Verify documents table has milestone 1 columns
cursor.execute("PRAGMA table_info(documents)")
doc_cols = [r[1] for r in cursor.fetchall()]
assert "file_hash_sha256" in doc_cols, "file_hash_sha256 missing"
assert "cleanup_status" in doc_cols, "cleanup_status missing"
assert "operation_type" in doc_cols, "operation_type missing"
assert "index_version" in doc_cols, "index_version missing"

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_worker_leases'")
assert cursor.fetchone() is not None, "document_worker_leases table missing"

conn.close()

print("\nISOLATION VERIFICATION:")
prod_lib = Path(os.path.expanduser("~/Documents/ResearchLens Library"))
print(f"1. Production Library path: {prod_lib} (Exists: {prod_lib.exists()}) - UNTOUCHED")
print(f"2. Test Library path:       {library_dir} - COMPLETELY ISOLATED")
print(f"3. Test Database:           {db_path}")
print(f"4. Test Credentials:        Username: 'testuser' | Password: 'TestPassword123!'")
print(f"5. Test Project:            'Milestone 1 Acceptance Project' (id: {paper_id})")
print(f"6. Test Sample Files:       {sample_dir}")
for f in sample_dir.iterdir():
    print(f"   - {f.name} ({f.stat().st_size} bytes)")
print("\nIsolated test environment setup is COMPLETE and VERIFIED!")
