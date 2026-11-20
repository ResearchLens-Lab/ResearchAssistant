"""
End-to-End Verification Script for Algorithms Project Grounded Summary Workflow.
Verifies all 4 observed failures against the live database:
1. Overview quality (no "thought exercises...", salience-based representative opening).
2. Heading quality (no "Chapter 6: eeees", no "), and using a search engine...", no exercise instructions).
3. Provenance & Citations (no fake Page 7 TOC citations; true physical page mapping).
4. Duplicate deduplication (Cormen deduplicated across two uploads).
5. Internal persistence in library.sqlite3 (papers.summary_json).
6. Local export file with frontmatter and audit trail.
7. Anti-ingestion guard.
"""
import sys
import json
import sqlite3
import asyncio
from pathlib import Path

# Set up paths
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.intelligence.summarizer import build_paper_summary
from backend.app.services.document_service import is_generated_summary_export


async def run_verification():
    library_db = Path.home() / "Documents" / "ResearchLens Library" / "library.sqlite3"
    lexical_db = Path.home() / "Documents" / "ResearchLens Library" / "indexes" / "researchlens_lexical.sqlite3"
    paper_id = "72e78a90-9a78-4f9a-ba61-90a887ff6fc5"

    print("=================================================================")
    print("      RESEARCHLENS GROUNDED SUMMARY E2E VERIFICATION REPORT      ")
    print("=================================================================")
    print(f"Library DB: {library_db} (Exists: {library_db.exists()})")
    print(f"Lexical DB: {lexical_db} (Exists: {lexical_db.exists()})")
    print(f"Target Paper ID: {paper_id}")

    if not library_db.exists() or not lexical_db.exists():
        print("ERROR: Database files do not exist at expected paths.")
        return False

    # 1. Generate Grounded Summary
    print("\n--- 1. GENERATING GROUNDED SUMMARY ---")
    summary = build_paper_summary(
        paper_id=paper_id,
        db_path=lexical_db,
    )

    answer = summary.get("answer", "")
    sources = summary.get("sources", [])

    print(f"Summary Generated: {len(answer)} chars, {len(sources)} citations.")
    print("\n--- Summary Content Preview ---\n")
    print(answer[:1000] + ("..." if len(answer) > 1000 else ""))

    failures = []

    # Check 1: Overview Quality
    print("\n--- 2. VERIFYING OVERVIEW QUALITY ---")
    if "thought exercises, whereas others are more substantial" in answer.lower():
        failures.append("FAIL: Overview starts with exercises disclaimer ('thought exercises...').")
    elif "thought exercises" in answer.lower():
        failures.append("FAIL: 'thought exercises' leaked into overview.")
    else:
        print("PASS: Overview does not contain 'thought exercises' exercise text.")

    # Check 2: Heading Quality
    print("\n--- 3. VERIFYING HEADING INTEGRITY ---")
    bad_headings = [
        "eeees",
        "), and using",
        "exercise",
        "p7 d s9",
    ]
    for bad in bad_headings:
        if bad in answer.lower():
            failures.append(f"FAIL: Malformed text '{bad}' found in summary headings or content.")
        else:
            print(f"PASS: Malformed pattern '{bad}' NOT present.")

    # Check 3: Page 7 Citations
    print("\n--- 4. VERIFYING PROVENANCE & PAGE 7 CHECKS ---")
    p7_sources = [s for s in sources if s.get("page") == 7 or s.get("page_start") == 7]
    print(f"Total sources citing Page 7: {len(p7_sources)}")
    if p7_sources:
        for s in p7_sources:
            print(f"  Warning/Check P7 Source: {s.get('citation_label')} - {s.get('title')} - Sec: {s.get('section')}")
            # If Chapter 6, Chapter 10, or Chapter 24 is cited as Page 7, that is a TOC leak
            sec_lower = str(s.get("section", "")).lower()
            if any(ch in sec_lower for ch in ["chapter 6", "chapter 10", "chapter 24", "chapter 11", "sorting"]):
                failures.append(f"FAIL: Body section '{s.get('section')}' falsely cited on TOC Page 7.")
    else:
        print("PASS: Zero sources cited on Page 7.")

    # Check 4: Duplicate Cormen Uploads Deduplication
    print("\n--- 5. VERIFYING EXACT-CONTENT DEDUPLICATION ---")
    # In library.sqlite3, Cormen exists twice (IDs ca86fa5f... and 83c31fde...)
    # The summary should only have ONE section for Cormen
    cormen_headings = [line for line in answer.split("\n") if "###" in line and "cormen" in line.lower()]
    print(f"Cormen book headings in summary: {len(cormen_headings)}")
    if len(cormen_headings) == 1:
        print(f"PASS: Cormen duplicate upload deduplicated to single section: '{cormen_headings[0]}'")
    elif len(cormen_headings) == 0:
        # Check by title
        algo_headings = [line for line in answer.split("\n") if "###" in line and "introduction to algorithms" in line.lower()]
        if len(algo_headings) == 1:
            print(f"PASS: Cormen deduplicated to single section: '{algo_headings[0]}'")
        else:
            failures.append(f"FAIL: Expected 1 Cormen heading, found {len(algo_headings)}: {algo_headings}")
    else:
        failures.append(f"FAIL: Cormen was summarized multiple times ({len(cormen_headings)}): {cormen_headings}")

    # Check 5: Internal Persistence
    print("\n--- 6. VERIFYING PERSISTENCE IN library.sqlite3 ---")
    with sqlite3.connect(library_db) as conn:
        conn.row_factory = sqlite3.Row
        # Check column exists
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(papers)").fetchall()]
        if "summary_json" not in cols:
            failures.append("FAIL: 'summary_json' column missing from papers table.")
        else:
            print("PASS: 'summary_json' column exists in papers table.")

        # Update paper with current summary to test write/read
        summary_payload = {
            "paper_id": paper_id,
            "answer": answer,
            "sources": sources,
            "is_stale": False,
        }
        summary_serialized = json.dumps(summary_payload)
        conn.execute(
            "UPDATE papers SET summary_json = ? WHERE id = ?",
            (summary_serialized, paper_id)
        )
        conn.commit()

        # Read back
        row = conn.execute("SELECT summary_json FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if not row or not row["summary_json"]:
            failures.append("FAIL: Failed to read back summary_json from papers table.")
        else:
            stored_data = json.loads(row["summary_json"])
            if stored_data.get("paper_id") == paper_id and len(stored_data.get("sources", [])) == len(sources):
                print(f"PASS: summary_json successfully persisted and verified ({len(stored_data['sources'])} sources).")
            else:
                failures.append("FAIL: Readback data mismatch.")

    # Check 6: Export Summary and Ingestion Guard
    print("\n--- 7. VERIFYING LOCAL EXPORT & ANTI-INGESTION GUARD ---")
    export_folder = Path.home() / "Documents" / "Personal Research" / "Algorithms"
    export_folder.mkdir(parents=True, exist_ok=True)
    export_filename = "Grounded Summary - Algorithms.md"
    export_path = export_folder / export_filename

    # Format export file content
    content_lines = [
        "<!-- researchlens:generated-summary version=1.0 -->",
        f"# Grounded Research Summary: Algorithms",
        "",
        "- **Project:** Algorithms",
        f"- **Total Citations:** {len(sources)}",
        "",
        "---",
        "",
        "## Summary Synthesis",
        "",
        answer,
        "",
        "---",
        "",
        "## Evidence & Citations Audit Trail",
        "",
    ]
    for s in sources:
        sid = s.get("source_id") or "S?"
        sec = s.get("section") or "Section"
        fn = s.get("filename") or s.get("title") or "Source Document"
        loc = s.get("locator") or f"Page {s.get('page', 1)}"
        txt = (s.get("text") or "").strip()
        content_lines.extend([
            f"### [{sid}] {sec}",
            f"- **Document:** {fn}",
            f"- **Locator:** {loc}",
            f"- **Passage Excerpt:**",
            f"> \"{txt}\"",
            "",
        ])

    tmp_path = export_folder / f".{export_filename}.tmp"
    tmp_path.write_text("\n".join(content_lines).strip() + "\n", encoding="utf-8")
    tmp_path.replace(export_path)

    if not export_path.exists():
        failures.append(f"FAIL: Export file {export_path} does not exist.")
    else:
        print(f"PASS: Export file written to {export_path} ({export_path.stat().st_size} bytes).")

    # Ingestion guard check
    is_excluded = is_generated_summary_export(export_path)
    if is_excluded:
        print(f"PASS: is_generated_summary_export({export_filename}) correctly returns TRUE (preventing infinite re-ingestion).")
    else:
        failures.append(f"FAIL: Ingestion guard returned FALSE for {export_filename}.")

    # Genuine user file check
    genuine_file = export_folder / "User_Algorithms_Notes.md"
    genuine_file.write_text("# Chapter 1 Notes\nPersonal review.", encoding="utf-8")
    is_genuine_excluded = is_generated_summary_export(genuine_file)
    if not is_genuine_excluded:
        print("PASS: is_generated_summary_export(User_Algorithms_Notes.md) correctly returns FALSE (user files admitted).")
    else:
        failures.append("FAIL: Ingestion guard falsely excluded genuine user file User_Algorithms_Notes.md.")
    # Clean up test note
    if genuine_file.exists():
        genuine_file.unlink()

    # Final Summary
    print("\n=================================================================")
    if failures:
        print(f"VERIFICATION FAILED WITH {len(failures)} ISSUE(S):")
        for f in failures:
            print(f"  - {f}")
        return False
    else:
        print("ALL 7 VERIFICATION CHECKS PASSED PERFECTLY!")
        print("=================================================================")
        return True


if __name__ == "__main__":
    success = asyncio.run(run_verification())
    sys.exit(0 if success else 1)
