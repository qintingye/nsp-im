"""
NSP-IM V3.0 D22 Strict Validation
- PC 1920x1080: Tab5 + Modal + Click-jump test
- Tablet 768x1024: Tab5 no overflow
- Mobile 375x812: Tab5 no overflow (critical)
- Console error capture
- 6+ screenshots
"""
import os, json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://localhost:8080/"
PASSWORD = "nsp2026"
OUT_DIR = Path(r"D:\hermes-dev-team\nsp-im\docs\preview\screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    ("pc", 1920, 1080),
    ("tablet", 768, 1024),
    ("mobile", 375, 812),
]

results = {"tests": [], "console": [], "page_errors": []}

def collect_console(msg, errors):
    entry = f"[{msg.type}] {msg.text}"
    errors.append(entry)

def collect_pageerror(err, errors):
    errors.append(f"[pageerror] {err}")

def run():
    with sync_playwright() as pw:
        for label, w, h in VIEWPORTS:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": w, "height": h})
            page = ctx.new_page()
            errs = []
            page.on("console", lambda m: collect_console(m, errs))
            page.on("pageerror", lambda e: collect_pageerror(e, errs))

            t0 = time.time()
            page.goto(URL, wait_until="networkidle", timeout=15000)
            load_ms = (time.time() - t0) * 1000

            # Login
            page.fill("#gate-input", PASSWORD)
            page.click(".gate-box button")
            page.wait_for_selector(".tab-btn", timeout=5000)
            page.wait_for_timeout(400)

            # Click Tab5
            page.click("[data-view='view-5']")
            page.wait_for_timeout(800)

            # Count match rows
            row_count = page.locator(".match-row").count()
            # Count mode-rec chips total
            chip_count = page.locator(".mode-rec").count()

            # Capture Tab5 overview
            ss1 = OUT_DIR / f"d22_{label}_tab5.png"
            page.screenshot(path=str(ss1), full_page=False)

            # Capture full page (match table extends down)
            ss_full = OUT_DIR / f"d22_{label}_tab5_full.png"
            page.screenshot(path=str(ss_full), full_page=True)

            # Check horizontal overflow
            body_width = page.evaluate("document.documentElement.scrollWidth")
            viewport_width = w
            has_overflow = body_width > viewport_width

            results["tests"].append({
                "viewport": label, "w": w, "h": h,
                "load_ms": round(load_ms, 1),
                "match_rows": row_count,
                "mode_chips": chip_count,
                "expected_rows": 25,
                "expected_chips": 75,
                "rows_ok": row_count == 25,
                "chips_ok": chip_count == 75,
                "overflow": has_overflow,
                "scroll_width": body_width,
                "screenshot": str(ss1),
            })

            # For PC: test modal
            if label == "pc":
                # First close any open modal
                # Click first C1 row's first recommended mode (算电协同)
                # Find C1 row
                c1 = page.locator(".match-row").filter(has_text="C1").first
                if c1.count() > 0:
                    c1.scroll_into_view_if_needed()
                    # First chip is 算电协同 per data
                    chips = c1.locator(".mode-rec")
                    if chips.count() > 0:
                        chips.first.click()
                        page.wait_for_selector(".modal-mask.show", timeout=3000)
                        page.wait_for_timeout(500)
                        ss2 = OUT_DIR / "d22_pc_modal_swot.png"
                        page.screenshot(path=str(ss2), full_page=False)
                        modal_title = page.locator("#modal-content h2").first.text_content() if page.locator("#modal-content h2").count() else "(none)"
                        modal_html = page.locator("#modal-content").inner_html()
                        results["tests"].append({
                            "test": "pc_modal_c1_first",
                            "modal_title": modal_title,
                            "has_swot_terms": any(k in modal_html for k in ["优势", "劣势", "适用", "不适用"]),
                            "has_case": "案例" in modal_html,
                            "screenshot": str(ss2),
                        })
                        # Close modal
                        page.keyboard.press("Escape")
                        try:
                            page.click(".close")
                        except Exception:
                            pass
                        page.wait_for_timeout(400)

                # Click算电协同 card directly (8th mode card)
                mode_cards = page.locator(".m5card")
                if mode_cards.count() >= 8:
                    mode_cards.nth(7).scroll_into_view_if_needed()
                    mode_cards.nth(7).click()
                    page.wait_for_selector(".modal-mask.show", timeout=3000)
                    page.wait_for_timeout(500)
                    ss3 = OUT_DIR / "d22_pc_modal_suandian.png"
                    page.screenshot(path=str(ss3), full_page=False)
                    modal_title2 = page.locator("#modal-content h2").first.text_content() if page.locator("#modal-content h2").count() else "(none)"
                    modal_html2 = page.locator("#modal-content").inner_html()
                    results["tests"].append({
                        "test": "pc_modal_suandian_card",
                        "modal_title": modal_title2,
                        "is_suandian": "算电协同" in (modal_title2 or ""),
                        "has_swot_terms": any(k in modal_html2 for k in ["优势", "劣势", "适用", "不适用"]),
                        "has_case": "案例" in modal_html2,
                        "screenshot": str(ss3),
                    })
                    page.keyboard.press("Escape")
                    try:
                        page.click(".close")
                    except Exception:
                        pass
                    page.wait_for_timeout(400)

                # Close-up of match table area
                page.locator(".m5match").scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                ss4 = OUT_DIR / "d22_pc_match_table.png"
                page.locator(".m5match").screenshot(path=str(ss4))

            # For mobile: take match table screenshot
            if label == "mobile":
                page.locator(".m5match").scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                ss5 = OUT_DIR / "d22_mobile_match.png"
                page.locator(".m5match").screenshot(path=str(ss5))

            results["console"].extend(errs)
            browser.close()

    print(json.dumps(results, ensure_ascii=False, indent=2))

run()