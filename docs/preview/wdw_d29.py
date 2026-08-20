"""WDW D29: V3.0 calcScore 10分制公式 + 7 Tab PASS + 0 JS 错误."""
import re
from playwright.sync_api import sync_playwright

URL = "http://localhost:8080/"
PASSWORD = "nsp2026"
EXPECTED = {"water": 8.0, "compute": 8.0, "telecom": 8.5, "pipe": 5.0, "logi": 6.5}
TAB_IDS = ["view-1", "view-2", "view-3", "view-4", "view-5", "view-6", "view-7"]

errors = []
console_errors = []

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1920, "height": 1080})
    p = ctx.new_page()
    p.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    p.on("pageerror", lambda e: console_errors.append(f"PAGEERROR: {e}"))

    p.goto(URL, wait_until="networkidle", timeout=15000)
    p.fill("#gate-input", PASSWORD)
    p.click(".gate-box button")
    p.wait_for_selector(".tab-btn", timeout=5000)

    # ---- 1. 验证 calcScore 返回 5 网分数 ----
    scores = p.evaluate("""() => {
        const order = ['water','compute','telecom','pipe','logi'];
        return order.map(k => [k, calcScore(k)]);
    }""")
    score_map = dict(scores)
    print("[calcScore]", scores)
    for k, v in EXPECTED.items():
        if score_map.get(k) != v:
            errors.append(f"calcScore({k})={score_map.get(k)} expected {v}")

    # ---- 2. Tab1 协同分显示 ----
    nb_html = p.locator("#nb").inner_html()
    for k, v in EXPECTED.items():
        if f">{v}<" not in nb_html and f">{v:.1f}<" not in nb_html:
            errors.append(f"Tab1 missing score {v} for {k}")
    # 耦合值注释保留（COUPLING_MAP D28）
    coupling_pat = re.compile(r"耦合\s+\d+\.\d\d")
    couplings = coupling_pat.findall(nb_html)
    print("[coupling 注释]", couplings)
    if len(couplings) < 5:
        errors.append(f"耦合值注释缺失, 找到 {len(couplings)}/5")

    # ---- 3. 7 Tab 切换 PASS ----
    tab_results = []
    for tab_id in TAB_IDS:
        try:
            p.click(f"[data-view='{tab_id}']", timeout=3000)
            p.wait_for_timeout(250)
            visible = p.eval_on_selector(f"#{tab_id}", "el => getComputedStyle(el).display !== 'none'")
            tab_results.append((tab_id, visible))
        except Exception as e:
            tab_results.append((tab_id, f"ERR: {e}"))
    print("[7 Tabs]", tab_results)
    pass_tabs = sum(1 for _, v in tab_results if v is True)
    if pass_tabs != 7:
        errors.append(f"7 Tab 只通过 {pass_tabs}/7")

    # ---- 4. 0 JS 错误 ----
    real_errors = [e for e in console_errors if "favicon" not in e.lower()]
    print("[JS errors]", real_errors)
    if real_errors:
        errors.append(f"JS 错误: {real_errors}")

    b.close()

print("\n========= D29 WDW RESULT =========")
print(f"calcScore PASS: {len([e for e in EXPECTED if score_map.get(e) == EXPECTED[e]])}/5")
print(f"耦合注释 PASS: {len(couplings)}/5")
print(f"7 Tab PASS: {pass_tabs}/7")
print(f"JS 错误: {len(real_errors)}")
if errors:
    print("❌ FAILURES:")
    for e in errors:
        print("  -", e)
    print("\nD29_WDW: FAIL")
else:
    print("\n✅ D29_WDW: ALL_PASS")
