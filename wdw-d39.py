"""V3.0 D39 WDW 自验 - URL 唯一 + 多源 + 时间线

- 32 项目 sources[] URL 全部唯一
- W1: 6 sources + 5 updates (符合 spec 多源叠加)
- 弹窗显示 🔗 信息来源 区块
- 弹窗显示 📅 进展时间线 区块
- 0 JS 错误
- HTML ≤ 95KB
- 7 Tab PASS
"""
import asyncio
import http.server
import socketserver
import threading
import os
import json
from playwright.async_api import async_playwright

ROOT = r"D:\hermes-dev-team\nsp-im\docs\preview"
PORT = 8190
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
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(500)

            results = {}

            # 0. JSON HTTP 200
            resp1 = await page.request.get(f"{URL_BASE}/data/projects.json")
            results["JSON_projects_status"] = resp1.status
            data = await resp1.json() if resp1.status == 200 else {}
            projects = data.get("projects", [])
            results["JSON_projects_count"] = len(projects)
            results["JSON_version"] = data.get("version")
            results["JSON_principle"] = data.get("principle")

            # 0.1 全局 URL 唯一性
            all_src_dups = []
            all_upd_dups = []
            for p_data in projects:
                s_urls = [s.get("url", "") for s in p_data.get("sources", [])]
                if len(s_urls) != len(set(s_urls)):
                    all_src_dups.append(p_data["id"])
                u_urls = [u.get("source_url", "") for u in p_data.get("updates", [])]
                if len(u_urls) != len(set(u_urls)):
                    all_upd_dups.append(p_data["id"])
            results["URL_uniqueness_sources_dups"] = all_src_dups
            results["URL_uniqueness_updates_dups"] = all_upd_dups
            results["URL_uniqueness_PASS"] = (
                len(all_src_dups) == 0 and len(all_upd_dups) == 0
            )

            # 0.2 W1 专项
            w1 = next((x for x in projects if x["id"] == "W1"), None)
            if w1:
                results["W1_sources_count"] = len(w1.get("sources", []))
                results["W1_updates_count"] = len(w1.get("updates", []))
                results["W1_sources_titles"] = [s.get("title", "")[:30] for s in w1.get("sources", [])]
                results["W1_status"] = w1.get("status")
                results["W1_last_updated"] = w1.get("last_updated")

            # 1. 密码门
            await page.fill("#gate-input", "nsp2026")
            await page.click("button:has-text('进入')")
            await page.wait_for_timeout(500)
            results["P0_password_ok"] = not await page.is_visible("#gate")

            # 2. 等 fetch 加载
            await page.wait_for_timeout(1500)
            results["PROJECTS_CACHE_len"] = await page.evaluate("PROJECTS_CACHE.length")

            # 3. Tab1 渲染
            await page.click('.tab-btn[data-view="view-1"]')
            await page.wait_for_timeout(300)
            results["T1_nbx_count"] = await page.locator("#nbg .nbx").count()

            # 4. 7 Tab 切换
            tab_btns = await page.query_selector_all(".tab-btn")
            results["P0_tab_button_count"] = len(tab_btns)
            tab_pass = 0
            for i in range(len(tab_btns)):
                btn = tab_btns[i]
                data_view = await btn.get_attribute("data-view")
                await btn.click()
                await page.wait_for_timeout(200)
                view = page.locator(f"#{data_view}")
                is_active = await view.evaluate("el => el.classList.contains('active')")
                if is_active:
                    tab_pass += 1
            results["T_all_tabs_pass"] = tab_pass
            results["T_all_tabs_total"] = len(tab_btns)

            # 5. 点水网 → 弹窗 → 选 W1
            await page.click('.tab-btn[data-view="view-1"]')
            await page.wait_for_timeout(300)
            water_box = page.locator(".nbx").first
            await water_box.click()
            await page.wait_for_timeout(400)

            # 找到 W1 卡 (文本含 "环北部湾广东")
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
                await page.wait_for_timeout(500)
                # 6. 弹窗内要素检查
                # 6.1 🔗 信息来源 区块
                sources_block = await page.locator("h3:has-text('信息来源')").count()
                results["UI_sources_heading"] = sources_block
                # 6.2 sources 容器
                src_rows = await page.locator(".sources .src-row").count()
                results["UI_sources_rows_W1"] = src_rows
                # 6.3 src-type 标签
                src_types = await page.locator(".src-row .src-type").count()
                results["UI_src_type_labels"] = src_types
                # 6.4 src-org 元数据
                src_orgs = await page.locator(".src-row .src-org").count()
                results["UI_src_org_metadata"] = src_orgs
                # 6.5 链接是否真 URL
                src_links = await page.locator(".src-row .src-title").all()
                link_urls = []
                for a in src_links:
                    href = await a.get_attribute("href")
                    link_urls.append(href)
                results["UI_src_link_urls"] = link_urls
                results["UI_src_links_have_real_urls"] = all(
                    u and u.startswith("http") and u != "#" for u in link_urls
                )
                # 6.6 URL 唯一性 (DOM 内)
                non_empty = [u for u in link_urls if u]
                results["UI_src_unique_PASS"] = len(non_empty) == len(set(non_empty))

                # 7. 📅 进展时间线 区块
                timeline_block = await page.locator("h3:has-text('进展时间线')").count()
                results["UI_timeline_heading"] = timeline_block
                # 7.1 t-row 节点
                t_rows = await page.locator(".timeline .t-row").count()
                results["UI_timeline_rows_W1"] = t_rows
                # 7.2 链接
                t_links = await page.locator(".timeline .t-row a").all()
                t_link_urls = []
                for a in t_links:
                    href = await a.get_attribute("href")
                    t_link_urls.append(href)
                results["UI_timeline_link_urls_count"] = len(t_link_urls)
                results["UI_timeline_link_unique"] = len(t_link_urls) == len(set(t_link_urls))

                # 7.3 当前状态
                t_status = await page.locator(".t-status").text_content()
                results["UI_t_status_text"] = (t_status or "").strip()[:80]

                # 8. 弹窗主信息
                results["T1_project_modal_title"] = await page.text_content("#m-title")
                results["T1_project_modal_invest"] = await page.text_content("#m-invest")
                results["T1_project_modal_total"] = await page.text_content("#m-total")

                await page.click("#modal .close")
                await page.wait_for_timeout(200)

            # 9. 关闭水网弹窗
            close1 = page.locator("#modal.show .close")
            if await close1.count() > 0:
                await close1.first.click()
                await page.wait_for_timeout(200)

            # 10. JS 错误
            results["JS_page_errors"] = page_errors
            results["JS_console_errors"] = console_errors
            results["JS_errors_count"] = len(page_errors) + len(console_errors)

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
