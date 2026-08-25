"""WDW: 8 mode cards × modal SWOT+case real-rendering check."""
from playwright.sync_api import sync_playwright

URL = "http://localhost:8080/"
PASSWORD = "nsp2026"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1920, "height": 1080})
    p = ctx.new_page()
    p.goto(URL, wait_until="networkidle", timeout=15000)
    p.fill("#gate-input", PASSWORD)
    p.click(".gate-box button")
    p.wait_for_selector(".tab-btn", timeout=8000)
    p.wait_for_timeout(500)
    p.click("[data-view='view-5']", timeout=5000)
    p.wait_for_timeout(700)
    cards = p.locator(".m5card")
    import re
    rows = []
    for i in range(cards.count()):
        # Always reset modal state
        try:
            p.evaluate("document.querySelectorAll('.modal-mask').forEach(m=>m.classList.remove('show'))")
            p.wait_for_timeout(80)
        except Exception:
            pass
        cards.nth(i).scroll_into_view_if_needed()
        cards.nth(i).click(timeout=5000)
        p.wait_for_selector(".modal-mask.show", timeout=4000)
        p.wait_for_timeout(180)
        title = p.locator("#modal-content h2").first.text_content().strip()
        html = p.locator("#modal-content").inner_html()
        swot4 = all(k in html for k in ["优势", "劣势", "适用", "不适用"])
        roe = "ROE" in html
        risk = "风险等级" in html
        cash = "现金特点" in html
        m = re.search(r"典型案例</h3>.*?>([^<]+)</div>", html, re.S)
        case_text = (m.group(1).strip() if m else "(none)")[:80]
        real_case = "央企电网" in case_text or any(
            t in case_text
            for t in ["格兰仕", "广船", "禅城", "珠江", "江苏e+", "湖南", "南网启成",
                      "南网看能", "国网e+", "贵安", "阳江", "环北部湾", "BOT", "长虹",
                      "珠江医院"]
        )
        rows.append((title, swot4, roe, risk, cash, real_case, case_text))
    for r in rows:
        print(r)
    n = len(rows)
    all_swot = sum(1 for r in rows if r[1])
    all_roe = sum(1 for r in rows if r[2])
    all_risk = sum(1 for r in rows if r[3])
    all_cash = sum(1 for r in rows if r[4])
    all_case = sum(1 for r in rows if r[5])
    print(f"\nTOTAL {n}/8 | SWOT4 {all_swot}/8 | ROE {all_roe}/8 | 风险等级 {all_risk}/8 | 现金特点 {all_cash}/8 | 真实案例 {all_case}/8")
    pass5 = all_swot == n and all_case == n and all_roe == n and all_risk == n and all_cash == n
    print("5D_PASS:", pass5)
    b.close()
