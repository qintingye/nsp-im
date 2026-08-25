"""Capture clean console evidence for D22 report."""
from playwright.sync_api import sync_playwright
import json

results = {"console_msgs": [], "page_errors": []}

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = ctx.new_page()
    page.on("console", lambda m: results["console_msgs"].append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: results["page_errors"].append(str(e)))

    page.goto("http://localhost:8080/", wait_until="networkidle", timeout=15000)
    page.fill("#gate-input", "nsp2026")
    page.click(".gate-box button")
    page.wait_for_selector(".tab-btn", timeout=5000)
    page.wait_for_timeout(400)
    # navigate through all tabs to surface any deferred errors
    for v in ["view-1", "view-2", "view-3", "view-4", "view-5", "view-6", "view-7"]:
        page.click(f"[data-view='{v}']")
        page.wait_for_timeout(400)
    # Click some chips and open modals
    page.click("[data-view='view-5']")
    page.wait_for_timeout(400)
    page.locator(".m5card").nth(0).click()
    page.wait_for_selector(".modal-mask.show", timeout=3000)
    page.wait_for_timeout(200)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    # Click a recommendation chip
    page.locator(".match-row").first.locator(".mode-rec").first.click()
    page.wait_for_selector(".modal-mask.show", timeout=3000)
    page.wait_for_timeout(200)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    # brief generation
    page.click("[data-view='view-7']")
    page.wait_for_timeout(400)
    page.click("#btn-gen")
    page.wait_for_timeout(800)

    page.screenshot(path=r"D:\hermes-dev-team\nsp-im\docs\preview\screenshots\d22_pc_all_clean.png", full_page=False)

print(json.dumps({
    "console_msg_count": len(results["console_msgs"]),
    "console_msgs": results["console_msgs"],
    "page_error_count": len(results["page_errors"]),
    "page_errors": results["page_errors"],
}, ensure_ascii=False, indent=2))