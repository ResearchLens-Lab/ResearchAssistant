"""
Playwright script to capture 6 genuine UI screenshots of ResearchLens.
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = Path(r"C:\Users\gorav\.gemini\antigravity\brain\d68d555e-7a4b-4b9f-a8a4-4483e0b184b9")
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def capture_all():
    print("Launching Edge via Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=EDGE_PATH, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Step 1: Login
        print("\n1. Navigating to login page...")
        page.goto("http://localhost:3000/login", wait_until="networkidle")
        time.sleep(1)

        print("   Logging in as 'researcher'...")
        page.fill("#login-identifier", "researcher")
        page.fill("#login-password", "ResearchPass123!")
        page.click("button[type='submit']")

        # Wait for redirect to /papers
        page.wait_for_url("**/papers", timeout=15000)
        time.sleep(2)
        print("   Logged in successfully. On /papers.")

        # Step 2: Screenshot 1 - Research Library
        print("\n2. Capturing screenshot_1_research_library.png...")
        page.wait_for_selector("text=A Comparative Study of Deterministic Algorithmic Paradigms", timeout=10000)
        time.sleep(1)
        s1_path = ARTIFACTS_DIR / "screenshot_1_research_library.png"
        page.screenshot(path=str(s1_path))
        print(f"   Saved: {s1_path}")

        # Step 3: Screenshot 2 - Document Ingestion
        print("\n3. Capturing screenshot_2_document_ingestion.png...")
        # Click on "Add Source" or "Add Documents" or paper menu
        add_btn = page.query_selector("button:has-text('Add Document'), button:has-text('Add source'), button:has-text('Add Paper')")
        if add_btn:
            add_btn.click()
            time.sleep(1)
        else:
            # Click on paper card to view details
            first_card = page.query_selector("text=A Comparative Study")
            if first_card:
                first_card.click()
                time.sleep(1)

        s2_path = ARTIFACTS_DIR / "screenshot_2_document_ingestion.png"
        page.screenshot(path=str(s2_path))
        print(f"   Saved: {s2_path}")

        # Close any open modal
        esc_btn = page.query_selector("button:has-text('Cancel'), button[aria-label='Close'], button:has-text('Close')")
        if esc_btn:
            try:
                esc_btn.click()
                time.sleep(0.5)
            except Exception:
                pass

        # Step 4: Screenshot 3 - Question & Answer
        print("\n4. Navigating to /chat for Question & Answer...")
        page.goto("http://localhost:3000/chat", wait_until="networkidle")
        time.sleep(2)

        # In chat workbench, click 'Select indexed' to scope all available documents
        select_indexed_btn = page.query_selector("button:has-text('Select indexed')")
        if select_indexed_btn:
            print("   Clicking 'Select indexed' to set research scope...")
            select_indexed_btn.click()
            time.sleep(1)

        # Type question
        chat_input = page.query_selector("textarea")
        if chat_input:
            chat_input.fill("What is an algorithm?")
            time.sleep(0.5)
            # Submit via enter or send button
            send_btn = page.query_selector("button:has-text('Send'), button[aria-label='Send message'], button[type='submit']")
            if send_btn:
                send_btn.click()
            else:
                chat_input.press("Enter")

            print("   Waiting for deterministic answer...")
            time.sleep(6)

        s3_path = ARTIFACTS_DIR / "screenshot_3_question_and_answer.png"
        page.screenshot(path=str(s3_path))
        print(f"   Saved: {s3_path}")

        # Step 5: Screenshot 4 - Evidence & Citation Inspection
        print("\n5. Capturing screenshot_4_evidence_citation_inspection.png...")
        # Click on citation pill [S1] or inspect sources button
        citation_pill = page.query_selector("button:has-text('[S1]'), a:has-text('[S1]'), button:has-text('S1')")
        if citation_pill:
            print("   Clicking citation [S1] to open SourceInspectorRail...")
            citation_pill.click()
            time.sleep(2)
        else:
            inspect_btn = page.query_selector("button:has-text('Inspect'), button:has-text('Sources'), button:has-text('Evidence')")
            if inspect_btn:
                inspect_btn.click()
                time.sleep(2)

        s4_path = ARTIFACTS_DIR / "screenshot_4_evidence_citation_inspection.png"
        page.screenshot(path=str(s4_path))
        print(f"   Saved: {s4_path}")

        # Step 6: Screenshot 5 - Multi-Document Comparison
        print("\n6. Navigating to /compare...")
        page.goto("http://localhost:3000/compare", wait_until="networkidle")
        time.sleep(2)

        # Select documents to compare
        checkboxes = page.query_selector_all("button[role='checkbox'], input[type='checkbox']")
        for cb in checkboxes[:2]:
            try:
                cb.click()
                time.sleep(0.3)
            except Exception:
                pass
        time.sleep(0.5)

        compare_btn = page.query_selector("button:has-text('Compare'), button:has-text('Generate Comparison')")
        if compare_btn:
            print("   Generating comparison...")
            compare_btn.click()
            time.sleep(6)

        s5_path = ARTIFACTS_DIR / "screenshot_5_multidoc_comparison.png"
        page.screenshot(path=str(s5_path))
        print(f"   Saved: {s5_path}")

        # Step 7: Screenshot 6 - Honest Abstention
        print("\n7. Navigating back to /chat for Honest Abstention test...")
        page.goto("http://localhost:3000/chat", wait_until="networkidle")
        time.sleep(2)

        select_indexed_btn = page.query_selector("button:has-text('Select indexed')")
        if select_indexed_btn:
            select_indexed_btn.click()
            time.sleep(1)

        chat_input = page.query_selector("textarea")
        if chat_input:
            chat_input.fill("What is the quantum decoherence threshold for surface codes reported in these documents?")
            time.sleep(0.5)
            send_btn = page.query_selector("button:has-text('Send'), button[aria-label='Send message'], button[type='submit']")
            if send_btn:
                send_btn.click()
            else:
                chat_input.press("Enter")

            print("   Waiting for honest abstention response...")
            time.sleep(6)

        s6_path = ARTIFACTS_DIR / "screenshot_6_honest_abstention.png"
        page.screenshot(path=str(s6_path))
        print(f"   Saved: {s6_path}")

        browser.close()
        print("\nAll 6 screenshots captured successfully!")


if __name__ == "__main__":
    capture_all()
