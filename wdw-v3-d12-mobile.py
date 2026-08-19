import asyncio
from playwright.async_api import async_playwright

FILE = r"D:\hermes-dev-team\nsp-im\docs\preview\index.html"
URL = "file:///" + FILE.replace("\\", "/")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        results = {}

        # Mobile 375 测试
        ctx = await browser.new_context(viewport={"width": 375, "height": 812})
        page = await ctx.new_page()
        page_errors = []
        console_errors = []
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        await page.goto(URL, wait_until="networkidle")

        # 密码
        await page.fill("#gate-input", "nsp2026")
        await page.click("button:has-text('进入')")
        await page.wait_for_timeout(400)

        # 全文档宽度
        body_w = await page.evaluate("document.documentElement.scrollWidth")
        results["M_doc_scrollWidth"] = body_w
        results["M_doc_overflow"] = body_w > 375

        # 切到 Tab6 - 看速览表溢出
        await page.click("button[data-view='view-6']")
        await page.wait_for_timeout(500)
        tab6_w = await page.evaluate("document.documentElement.scrollWidth")
        results["M_Tab6_scrollWidth"] = tab6_w
        results["M_Tab6_overflow"] = tab6_w > 375

        # 测 .t6sum 横向滚动容器
        t6_scroll = await page.evaluate("""
            (() => {
                const el = document.querySelector('.t6sum');
                if (!el) return null;
                return {scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, overflow: el.scrollWidth > el.clientWidth};
            })()
        """)
        results["M_t6sum_scrollcontainer"] = t6_scroll

        # 切到 Tab3 - 26.9 万亿显示
        await page.click("button[data-view='view-3']")
        await page.wait_for_timeout(400)
        v3_visible = await page.is_visible("#view-3")
        v3_h2 = await page.text_content("#view-3 h2")
        v3_chains = await page.locator("#view-3 .chain-card").count()
        v3_phases = await page.locator("#view-3 .phase").count()
        results["M_Tab3_visible"] = v3_visible
        results["M_Tab3_h2"] = v3_h2
        results["M_Tab3_chains"] = v3_chains
        results["M_Tab3_phases"] = v3_phases

        # 切到 Tab4 - 协同方向
        await page.click("button[data-view='view-4']")
        await page.wait_for_timeout(400)
        v4_visible = await page.is_visible("#view-4")
        v4_h2 = await page.text_content("#view-4 h2")
        v4_dirs = await page.locator("#view-4 .dir-card").count()
        v4_dims = await page.locator("#view-4 .dim-grid > span").count()
        v4_batches = await page.locator("#view-4 .batch").count()
        results["M_Tab4_visible"] = v4_visible
        results["M_Tab4_h2"] = v4_h2
        results["M_Tab4_dirs"] = v4_dirs
        results["M_Tab4_dims"] = v4_dims
        results["M_Tab4_batches"] = v4_batches
        tab4_w = await page.evaluate("document.documentElement.scrollWidth")
        results["M_Tab4_scrollWidth"] = tab4_w
        results["M_Tab4_overflow"] = tab4_w > 375

        # 截屏
        await page.screenshot(path="screenshots/v3_d12_mobile_375_tab3.png", full_page=False)
        await page.click("button[data-view='view-4']")
        await page.wait_for_timeout(400)
        await page.screenshot(path="screenshots/v3_d12_mobile_375_tab4.png", full_page=False)
        await page.click("button[data-view='view-6']")
        await page.wait_for_timeout(400)
        await page.screenshot(path="screenshots/v3_d12_mobile_375_tab6.png", full_page=False)

        results["M_JS_errors"] = page_errors
        results["M_console_errors"] = console_errors

        await browser.close()
        print("=== Mobile 375 自检 ===")
        for k, v in results.items():
            print(f"  {k}: {v}")

asyncio.run(main())