"""V3.0 D40 WDW 自验 - 弹窗不再崩溃

- 真模拟用户: gate 密码 → Tab1 → 水网 → W1 → 弹窗
- 关键断言: m-total (总分) 渲染, m-eval (评语) 渲染, 0 JS 错误
- HTML ≤ 95KB
- 7 Tab PASS
- sources 区块 + timeline 区块 都要在
"""
import asyncio
import http.server
import socketserver
import threading
import os
import json
from playwright.async_api import async_playwright

ROOT = r"D:\hermes-dev-team\nsp-im\docs\preview"
PORT = 8192
URL_BASE = f"http://127.0.0.1:{PORT}"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, *args):
        pass


def start_server():
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


async def main():
    results = {"checks": []}
    httpd = start_server()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await ctx.new_page()
            page_errors = []
            console_errors = []
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            page.on("console", lambda m: (
                console_errors.append(m.text) if m.type == "error" else None
            ))

            url = f"{URL_BASE}/index.html"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(500)

            # 1. 密码门
            await page.fill("#gate-input", "nsp2026")
            await page.click("button:has-text('进入')")
            await page.wait_for_timeout(500)
            gate_ok = not await page.is_visible("#gate")
            results["checks"].append(("密码门", gate_ok, gate_ok))

            # 2. 等 fetch 加载
            await page.wait_for_timeout(2000)
            cache_len = await page.evaluate("PROJECTS_CACHE.length")
            results["PROJECTS_CACHE_len"] = cache_len
            results["checks"].append(("PROJECTS_CACHE loaded", cache_len > 0, cache_len > 0))

            # 3. Tab1 → 水网 → W1
            await page.click('.tab-btn[data-view="view-1"]')
            await page.wait_for_timeout(300)
            water_box = page.locator(".nbx").first
            await water_box.click()
            await page.wait_for_timeout(500)

            # 找 W1 卡
            w1_card = None
            cards = await page.locator("#modal .action-card").all()
            for c in cards:
                txt = await c.text_content()
                if "环北部湾广东" in (txt or ""):
                    w1_card = c
                    break
            results["W1_card_found"] = w1_card is not None

            if w1_card:
                await w1_card.click()
                await page.wait_for_timeout(800)

                # 弹窗可见
                modal_visible = await page.evaluate("""
                    () => {
                        const m = document.getElementById('modal');
                        return m && m.classList.contains('show');
                    }
                """)
                results["checks"].append(("Modal opened", modal_visible, modal_visible))

                # 关键字段: 总分渲染 (toFixed 不抛错)
                total = await page.text_content("#m-total")
                results["modal_total"] = total
                total_ok = total and total.strip() and "undefined" not in total and "NaN" not in total
                results["checks"].append(("modal: 总分 (toFixed OK)", total, total_ok))

                # 推荐理由 4 维
                r1 = await page.text_content("#m-r1")
                r2 = await page.text_content("#m-r2")
                r3 = await page.text_content("#m-r3")
                r4 = await page.text_content("#m-r4")
                results["modal_r1"] = r1
                results["modal_r2"] = r2
                results["modal_r3"] = r3
                results["modal_r4"] = r4
                rec_ok = all(x and x.strip() and "undefined" not in x for x in [r1, r2, r3, r4])
                results["checks"].append(("modal: 4 维度评分", f"{r1}, {r2}, {r3}, {r4}", rec_ok))

                # 评语
                eval_text = await page.text_content("#m-eval")
                results["modal_eval"] = (eval_text or "")[:50]
                eval_ok = eval_text and eval_text.strip() and "undefined" not in eval_text
                results["checks"].append(("modal: 评语", eval_text, eval_ok))

                # 项目标题
                title = await page.text_content("#m-title")
                results["modal_title"] = title
                # D38 fetch 后 project.name 是真实项目名 (例如 "环北部湾广东水资源配置工程")
                # 仅断言标题包含 W1 名称片段, 不硬等
                results["checks"].append(("modal: 标题 (含 W1)", title, title and "环北部湾广东" in title))

                # sources 区块
                sources_block = await page.locator("h3:has-text('来源')").count()
                src_rows = await page.locator(".sources .src-row").count()
                results["sources_block"] = sources_block
                results["sources_rows"] = src_rows
                src_ok = sources_block > 0 and src_rows > 0
                results["checks"].append(("modal: sources 区块", f"{sources_block} 标题, {src_rows} 行", src_ok))

                # timeline 区块
                timeline_block = await page.locator("h3:has-text('进展时间线')").count()
                t_rows = await page.locator(".timeline .t-row").count()
                results["timeline_block"] = timeline_block
                results["timeline_rows"] = t_rows
                tl_ok = timeline_block > 0 and t_rows > 0
                results["checks"].append(("modal: timeline 区块", f"{timeline_block} 标题, {t_rows} 行", tl_ok))

                # 关闭弹窗
                close_btn = page.locator("#modal .close").first
                if await close_btn.count() > 0:
                    await close_btn.click()
                    await page.wait_for_timeout(200)

            # 7 Tab 切换
            tab_btns = await page.query_selector_all(".tab-btn")
            tab_pass = 0
            tab_details = []
            for i in range(len(tab_btns)):
                btn = tab_btns[i]
                data_view = await btn.get_attribute("data-view")
                await btn.click()
                await page.wait_for_timeout(200)
                view = page.locator(f"#{data_view}")
                is_active = await view.evaluate("el => el.classList.contains('active')")
                tab_details.append((i + 1, is_active))
                if is_active:
                    tab_pass += 1
            results["tabs"] = tab_details
            results["tabs_pass"] = f"{tab_pass}/{len(tab_btns)}"
            results["checks"].append(("7 Tab PASS", f"{tab_pass}/{len(tab_btns)}",
                                       tab_pass == len(tab_btns)))

            # 0 JS 错误
            results["page_errors"] = page_errors
            results["console_errors"] = console_errors
            results["checks"].append(("0 JS errors",
                                       f"page={len(page_errors)}, console={len(console_errors)}",
                                       len(page_errors) == 0 and len(console_errors) == 0))

            # HTML ≤ 95KB
            html_size = os.path.getsize(os.path.join(ROOT, "index.html"))
            html_kb = round(html_size / 1024, 1)
            results["html_kb"] = html_kb
            results["checks"].append(("HTML ≤ 95KB", f"{html_kb}KB", html_kb <= 95))

            # 截图
            os.makedirs(os.path.join(ROOT, "screenshots"), exist_ok=True)
            await page.screenshot(path=os.path.join(ROOT, "screenshots", "d40_verify.png"), full_page=False)

            await browser.close()
    finally:
        httpd.shutdown()

    # 汇总
    print("\n" + "=" * 60)
    print("V3.0 D40 WDW 自验 (弹窗不再崩溃)")
    print("=" * 60)
    for name, val, ok in results["checks"]:
        print(f"  [{'✅' if ok else '❌'}] {name}: {val}")
    print(f"\n  Page errors: {results.get('page_errors')}")
    print(f"  Console errors: {results.get('console_errors')}")
    print("=" * 60)

    all_ok = all(ok for _, _, ok in results["checks"])
    print(f"\n{'✅ PASS' if all_ok else '❌ FAIL'}")

    with open("d40_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return 0 if all_ok else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    raise SystemExit(exit_code)
