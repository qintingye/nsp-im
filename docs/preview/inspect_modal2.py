"""Expand details and capture full modal"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = ctx.new_page()
    page.goto("http://localhost:8080/", wait_until="networkidle", timeout=15000)
    page.fill("#gate-input", "nsp2026")
    page.click(".gate-box button")
    page.wait_for_selector(".tab-btn", timeout=5000)
    page.wait_for_timeout(300)
    page.click("[data-view='view-5']")
    page.wait_for_timeout(500)
    cards = page.locator(".m5card")
    cards.nth(7).scroll_into_view_if_needed()
    cards.nth(7).click()
    page.wait_for_selector(".modal-mask.show", timeout=3000)
    page.wait_for_timeout(300)
    # expand details
    details = page.locator("#modal-content details")
    print(f"details count: {details.count()}")
    if details.count() > 0:
        details.first.locator("summary").click()
        page.wait_for_timeout(300)
        page.screenshot(path=r"D:\hermes-dev-team\nsp-im\docs\preview\screenshots\d22_pc_modal_full.png")
        html = page.locator("#modal-content").inner_text()
        print("===== EXPANDED MODAL =====")
        print(html)
        print("===== END =====")
        # Look for the SWOT 4 dimensions in MODES_S
        swot_terms = ["永久所有权", "客户零投入", "稳定年度服务费", "极轻资产"]
        found_any = [t for t in swot_terms if t in html]
        print(f"SWOT data from MODES_S visible: {found_any}")
    browser.close()