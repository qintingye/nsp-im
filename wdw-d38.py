"""V3.0 D38 WDW 自验 (HTTP server 版, 验证 fetch 链路)
- 启本地 HTTP server (8181)
- 测 projects.json / policies.json HTTP 200
- 测 fetch 加载成功
- 测 32 项目 (历史 25 + D38 新抓 7) 显示
- 测 0 JS 错误 (除 file:// 限制外)
"""
import asyncio
import http.server
import socketserver
import threading
import os
from playwright.async_api import async_playwright
import json

ROOT = r"D:\hermes-dev-team\nsp-im\docs\preview"
PORT = 8181
URL_BASE = f"http://localhost:{PORT}"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)
    def log_message(self, *args):
        pass  # silence

def start_server():
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd

async def main():
    httpd = start_server()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await ctx.new_page()
            page_errors = []
            console_errors = []
            console_warnings = []
            console_logs = []
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            page.on("console", lambda m: (
                console_errors.append(m.text) if m.type == "error"
                else console_warnings.append(m.text) if m.type == "warning"
                else console_logs.append(m.text)
            ))

            url = f"{URL_BASE}/index.html"
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(500)

            results = {}

            # 0. JSON HTTP 200
            resp1 = await page.request.get(f"{URL_BASE}/data/projects.json")
            results["JSON_projects_status"] = resp1.status
            if resp1.status == 200:
                data = await resp1.json()
                results["JSON_projects_count"] = len(data.get("projects", []))
            resp2 = await page.request.get(f"{URL_BASE}/data/policies.json")
            results["JSON_policies_status"] = resp2.status

            # 1. 密码门
            await page.fill("#gate-input", "nsp2026")
            await page.click("button:has-text('进入')")
            await page.wait_for_timeout(500)
            results["P0_password_ok"] = not await page.is_visible("#gate")

            # 2. 等 fetch 加载完成 (PROJECTS_CACHE 已填)
            await page.wait_for_timeout(1500)

            # 3. PROJECTS_CACHE 应有 32 条
            cache_len = await page.evaluate("PROJECTS_CACHE.length")
            results["PROJECTS_CACHE_len"] = cache_len

            # 4. console 日志验证 fetch 成功
            projects_log = [l for l in console_logs if "项目" in l and "加载" in l]
            policies_log = [l for l in console_logs if "政策" in l and "加载" in l]
            results["CONSOLE_projects_loaded"] = projects_log[0] if projects_log else None
            results["CONSOLE_policies_loaded"] = policies_log[0] if policies_log else None

            # 5. Tab1: 5 网块 + 项目分布 (历史 25 + D38 新 7 = 32)
            await page.click('.tab-btn[data-view="view-1"]')
            await page.wait_for_timeout(300)
            results["T1_nbx_count"] = await page.locator("#nbg .nbx").count()

            # 6. Tab1 渲染文本含 32 项目中至少一个 D38 新项目 id (P-NDRC-20260210-2898)
            body_text = await page.text_content("body")
            results["T1_has_D38_new_project"] = "P-NDRC-20260210-2898" in body_text
            results["T1_has_D38_new_project_2"] = "P-CSG-20260818-4372" in body_text

            # 7. 7 Tab 切换
            tab_btns = await page.query_selector_all(".tab-btn")
            results["P0_tab_button_count"] = len(tab_btns)

            # 8. 点水网 → 弹窗 → 项目列表
            water_box = page.locator(".nbx").first
            await water_box.click()
            await page.wait_for_timeout(400)
            modal_visible = await page.is_visible("#modal.show")
            results["P0_water_modal"] = modal_visible

            # 9. 点水网里的项目卡 → openProject 弹窗 → 投资额
            cards = await page.locator("#modal .action-card").count()
            results["T1_water_project_cards"] = cards
            if cards > 0:
                await page.locator("#modal .action-card").first.click()
                await page.wait_for_timeout(400)
                invest = await page.text_content("#m-invest")
                results["T1_project_modal_invest"] = invest

                # 弹窗里的项目也可能是 D38 新抓 (环北部湾广东水资源)
                title = await page.text_content("#m-title")
                results["T1_project_modal_title"] = title

                # 关键: 弹窗里的 source URL 不能是 # (D38 真抓应当有真 URL)
                src_url = await page.get_attribute("#m-source-url", "href")
                results["T1_project_modal_src_url"] = src_url

                # 推荐分不能是 undefined
                total = await page.text_content("#m-total")
                results["T1_project_modal_total"] = total

                await page.click("#modal .close")
                await page.wait_for_timeout(200)

            # 10. JS 错误
            results["JS_errors_count"] = len(page_errors) + len(console_errors)
            results["JS_page_errors"] = page_errors
            results["JS_console_errors"] = console_errors

            # 11. 横向溢出
            results["UI_no_horizontal_overflow"] = (
                await page.evaluate("document.body.scrollWidth")
                <= await page.evaluate("window.innerWidth") + 1
            )

            await browser.close()
            return results
    finally:
        httpd.shutdown()

results = asyncio.run(main())
print(json.dumps(results, ensure_ascii=False, indent=2))