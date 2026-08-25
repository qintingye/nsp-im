"""
V3.0 D27 WDW 自验 - 验证 calcScore v2.1 算法
- Tab1 5 网分数有区分度
- 5 网不全 10.0
- HTML ≤ 80KB
- 0 JS 错误
- 7 Tab 全部 PASS
"""
import asyncio, json, os
from playwright.async_api import async_playwright

FILE = r"D:\hermes-dev-team\nsp-im\docs\preview\index.html"
URL = "file:///" + FILE.replace("\\", "/")
DEPLOY_FILE = r"D:\hermes-dev-team\nsp-im\deploy-pkg\liuwang-jiankong\index.html"

EXPECTED_SCORES = {
    "water": 10.0,
    "compute": 9.8,
    "telecom": 7.2,
    "pipe": 8.5,
    "logi": 6.8,
}

async def run(p, viewport, label):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport=viewport)
    page = await ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(f"[pageerror] {e}"))
    page.on("console", lambda m: errs.append(f"[{m.type}] {m.text}") if m.type == "error" else None)
    await page.goto(URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(500)

    r = {"label": label, "viewport": viewport, "errors": errs[:5]}

    # Gate
    r["gate_visible"] = await page.is_visible("#gate")
    await page.fill("#gate-input", "wrong")
    await page.click("button:has-text('进入')")
    await page.wait_for_timeout(150)
    err = await page.text_content("#gate-err")
    r["wrong_pwd_rejected"] = "密码错误" in (err or "")

    await page.fill("#gate-input", "nsp2026")
    await page.click("button:has-text('进入')")
    await page.wait_for_timeout(300)
    r["correct_pwd_accepted"] = not await page.is_visible("#gate")

    # === D27 calcScore 自验 ===
    # 直接在浏览器里调用 calcScore 取 5 网分数
    scores_raw = await page.evaluate("""() => {
        const nets = ['water','compute','telecom','pipe','logi'];
        const out = {};
        nets.forEach(n => out[n] = calcScore(n));
        return out;
    }""")
    r["D27_scores"] = scores_raw

    # 计算得分列表（保留 1 位小数）
    s_vals = [round(scores_raw[n], 1) for n in ["water","compute","telecom","pipe","logi"]]
    r["D27_score_list"] = s_vals

    # 检查 5 网不全 10
    r["D27_not_all_10"] = not all(abs(v - 10.0) < 0.05 for v in s_vals)

    # 检查 5 网有区分度（有 ≥ 3 个不同值）
    r["D27_differentiated"] = len(set(s_vals)) >= 3

    # Tab1 摘要渲染检查
    r["T1_net_summary"] = await page.locator("#nb .nsi").count()
    r["T1_net_cards"] = await page.locator("#nbg .nbx").count()

    # Tab1 显示分数（.nsi 里的 span 文本）
    spans = await page.locator("#nb .nsi span").all_text_contents()
    r["T1_score_spans"] = spans

    # Tab 切换
    btns = await page.query_selector_all(".tab-btn")
    r["tab_count"] = len(btns)
    for b in btns:
        await b.click()
        await page.wait_for_timeout(60)
    r["no_js_error_after_tab_switch"] = len(errs) == 0

    # 各 Tab 计数
    await page.click('.tab-btn[data-view="view-2"]'); await page.wait_for_timeout(150)
    r["T2_policy_count"] = await page.locator(".pcard").count()

    await page.click('.tab-btn[data-view="view-3"]'); await page.wait_for_timeout(150)
    r["T3_action_count"] = await page.locator(".action-card").count()

    await page.click('.tab-btn[data-view="view-5"]'); await page.wait_for_timeout(150)
    r["T5_cats"] = await page.locator(".m5cat").count()
    r["T5_modes"] = await page.locator(".m5card").count()

    await page.click('.tab-btn[data-view="view-6"]'); await page.wait_for_timeout(150)
    r["T6_modes"] = await page.locator(".t6mode").count()

    await page.click('.tab-btn[data-view="view-7"]'); await page.wait_for_timeout(150)
    initial = await page.text_content("#brief-content")
    r["T7_initial_empty"] = "生成" in (initial or "") or "点击" in (initial or "")
    await page.click("#btn-gen")
    await page.wait_for_timeout(400)
    after = await page.text_content("#brief-content")
    r["T7_after_gen_length"] = len(after or "")
    r["T7_has_26_9"] = "26.9" in (after or "")
    r["T7_has_5nets"] = "5 网协同" in (after or "")

    # 横向溢出
    bw = await page.evaluate("document.body.scrollWidth")
    vw = await page.evaluate("window.innerWidth")
    r["body_w"] = bw
    r["view_w"] = vw
    r["no_horizontal_overflow"] = bw <= vw + 1

    # JS error count
    r["js_error_count"] = len(errs)

    await browser.close()
    return r

async def main():
    # 文件大小检查
    html_size = os.path.getsize(FILE)
    deploy_size = os.path.getsize(DEPLOY_FILE)
    in_sync = (html_size == deploy_size)

    async with async_playwright() as p:
        out = {}
        for label, vp in [("PC",{"width":1440,"height":900}),
                          ("Tablet",{"width":768,"height":1024}),
                          ("Mobile",{"width":375,"height":812})]:
            try:
                out[label] = await run(p, vp, label)
            except Exception as e:
                out[label] = {"err": str(e)[:200]}

    # 综合判定
    print("=" * 60)
    print("V3.0 D27 WDW 自验")
    print("=" * 60)
    print(f"HTML size: {html_size} bytes ({html_size/1024:.2f} KB)")
    print(f"deploy-pkg size: {deploy_size} bytes")
    print(f"in sync: {in_sync}")
    print(f"HTML ≤ 80KB: {html_size <= 81920}")
    print()
    for label in ["PC", "Tablet", "Mobile"]:
        r = out.get(label, {})
        if "err" in r:
            print(f"== {label} == ERR: {r['err']}")
            continue
        scores = r.get("D27_scores", {})
        sl = r.get("D27_score_list", [])
        print(f"== {label} ({r['viewport']['width']}x{r['viewport']['height']}) ==")
        print(f"  calcScore: {scores}")
        print(f"  score_list: {sl}")
        print(f"  T1_net_summary count: {r['T1_net_summary']}")
        print(f"  T1_score_spans: {r['T1_score_spans']}")
        print(f"  5 网不全 10: {r['D27_not_all_10']}")
        print(f"  有区分度 (≥3 不同值): {r['D27_differentiated']}")
        print(f"  Tab 数: {r['tab_count']} (7 expected)")
        print(f"  JS errors: {r['js_error_count']}")
        print(f"  T2/T3/T5/T6/T7: {r['T2_policy_count']}/{r['T3_action_count']}/{r['T5_modes']}/{r['T6_modes']}/len{r['T7_after_gen_length']}")
        print(f"  T7 26.9 + 5网: {r['T7_has_26_9']} / {r['T7_has_5nets']}")
        print(f"  横向溢出: body={r['body_w']} view={r['view_w']} ok={r['no_horizontal_overflow']}")
        print()

    # 输出 JSON 备查
    print("JSON:")
    print(json.dumps({
        "html_size": html_size,
        "deploy_size": deploy_size,
        "in_sync": in_sync,
        "results": out,
    }, ensure_ascii=False, indent=2))

asyncio.run(main())