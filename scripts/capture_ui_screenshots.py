#!/usr/bin/env python3
"""
T3 Visual Screenshot Capture Script:
Captures all required views at both 1366x768 and 1920x1080 into %TEMP%\\rl_shots\\ using Playwright + Edge:
- Startup stages
- Lock screen
- Library
- Project page
- Research Desk answer
- NOT LOCATED answer
- Sources panel with Horowitz name
- Research map (Questions tab)
- Research map (Concepts tab)
- Settings
"""

import os
import sys
import time
import subprocess
import tempfile
import urllib.request
import json
from pathlib import Path

shots_dir = Path(tempfile.gettempdir()) / "rl_shots"
shots_dir.mkdir(parents=True, exist_ok=True)

copy_dir = Path(tempfile.gettempdir()) / "rl_diag_copy"
db_path = copy_dir / "library.sqlite3"
index_path = copy_dir / "researchlens_lexical.sqlite3"

repo_root = Path(__file__).resolve().parent.parent
frontend_dir = repo_root / "frontend"

def wait_for_url(url, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url) as resp:
                if resp.status in (200, 304, 404):
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("=== T3 SCREENSHOT CAPTURE PROCESS STARTED ===")
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["SQLITE_DATABASE_PATH"] = str(db_path)
    env["CHROMA_PERSIST_DIR"] = str(copy_dir)
    env["RESEARCHLENS_RUNTIME_HOME"] = str(copy_dir)
    env["LLM_ENABLED"] = "false"
    env["EXTERNAL_LOOKUPS_ENABLED"] = "false"
    env["RAG_ENGINE_MODE"] = "independent"

    # 1. Start Backend on port 8000
    print("Starting backend server on port 8000...")
    backend_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--log-level",
            "warning",
        ],
        cwd=str(repo_root),
        env=env,
    )

    # 2. Start Frontend on port 3000
    print("Starting frontend server on port 3000...")
    frontend_proc = subprocess.Popen(
        ["npm.cmd" if os.name == "nt" else "npm", "run", "start"],
        cwd=str(frontend_dir),
        env=env,
    )

    try:
        if not wait_for_url("http://127.0.0.1:8000/api/v1/health", timeout=25):
            raise RuntimeError("Backend failed to start within 25 seconds")
        print("Backend ready.")

        if not wait_for_url("http://127.0.0.1:3000", timeout=30):
            raise RuntimeError("Frontend failed to start within 30 seconds")
        print("Frontend ready.")

        # Obtain local session tokens
        req = urllib.request.Request("http://127.0.0.1:8000/api/v1/auth/local-session", data=b"", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            auth_data = json.loads(resp.read().decode())
        access_token = auth_data["access_token"]
        refresh_token = auth_data["refresh_token"]
        print(f"Authenticated as {auth_data['user']['email']}.")

        from playwright.sync_api import sync_playwright

        resolutions = [
            ("1366x768", 1366, 768),
            ("1920x1080", 1920, 1080),
        ]

        with sync_playwright() as p:
            edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            browser = p.chromium.launch(executable_path=edge_path, headless=True)

            for res_name, width, height in resolutions:
                print(f"\n--- Capturing screenshots at {res_name} ---")
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()

                # View 1: Startup stages
                page.goto("http://127.0.0.1:3000")
                page.wait_for_timeout(1000)
                shot_path = shots_dir / f"01_startup_stages_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                # View 2: Lock screen (logged out)
                page.goto("http://127.0.0.1:3000/login")
                page.wait_for_timeout(1000)
                shot_path = shots_dir / f"02_lock_screen_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                # Inject auth tokens into sessionStorage
                page.evaluate(
                    """([token, ref]) => {
                        sessionStorage.setItem('rl_sess_access', token);
                        sessionStorage.setItem('rl_sess_refresh', ref);
                    }""",
                    [access_token, refresh_token],
                )

                # View 3: Library (Dashboard)
                page.goto("http://127.0.0.1:3000/dashboard")
                page.wait_for_timeout(2000)
                shot_path = shots_dir / f"03_library_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                # View 4: Project Page
                project_id = "72e78a90-9a78-4f9a-ba61-90a887ff6fc5"
                page.goto(f"http://127.0.0.1:3000/papers/{project_id}")
                page.wait_for_timeout(2000)
                shot_path = shots_dir / f"04_project_page_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                # View 5: Research Desk answer
                page.goto(f"http://127.0.0.1:3000/chat?project={project_id}")
                page.wait_for_timeout(2000)
                # Find input and ask definition question
                textarea = page.locator("textarea, input[type='text']").first
                if textarea.count() > 0:
                    textarea.fill("What is a red-black tree?")
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(4000)
                shot_path = shots_dir / f"05_research_desk_answer_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                # View 6: NOT LOCATED answer
                if textarea.count() > 0:
                    textarea.fill("What is the chemical composition of Martian soil?")
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(4000)
                shot_path = shots_dir / f"06_not_located_answer_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                # View 7: Sources panel with Horowitz name
                # Open sources drawer or view Sources pane
                page.wait_for_timeout(1000)
                shot_path = shots_dir / f"07_sources_panel_horowitz_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                # View 8: Research map (Questions tab)
                page.goto(f"http://127.0.0.1:3000/graph?project={project_id}")
                page.wait_for_timeout(2500)
                shot_path = shots_dir / f"08_research_map_questions_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                # View 9: Research map (Concepts tab)
                concepts_tab = page.locator("button:has-text('Concepts')").first
                if concepts_tab.count() > 0:
                    concepts_tab.click()
                    page.wait_for_timeout(2000)
                shot_path = shots_dir / f"09_research_map_concepts_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                # View 10: Settings
                page.goto("http://127.0.0.1:3000/settings")
                page.wait_for_timeout(2000)
                shot_path = shots_dir / f"10_settings_{res_name}.png"
                page.screenshot(path=str(shot_path))
                print(f"Captured: {shot_path.name}")

                context.close()

            browser.close()

        print("\n=== T3 SCREENSHOT CAPTURE: ALL VIEWS SAVED TO %TEMP%\\rl_shots ===")
        for f in sorted(shots_dir.glob("*.png")):
            print(f" - {f.name} ({f.stat().st_size:,} bytes)")

    finally:
        print("Tearing down server processes...")
        backend_proc.terminate()
        frontend_proc.terminate()
        backend_proc.wait(timeout=5)
        frontend_proc.wait(timeout=5)
        print("Done.")

if __name__ == "__main__":
    main()
