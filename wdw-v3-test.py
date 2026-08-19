
import asyncio
from playwright.async_api import async_playwright
import json
import os
import re

FILE = r"D:\hermes-dev-team\nsp-im\docs\preview\index.html"
URL = "file:///" + FILE.replace("\\", "/")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        results = {}

        # PC 测试
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()
        page_errors = []
        console_errors = []
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        await page.goto(URL, wait_until="networkidle")

        # 1. 密码门
        gate_visible = await page.is_visible("#gate")
        results["P0_password_gate_visible"] = gate_visible

        # 错误密码测试
        await page.fill("#gate-input", "wrongpass")
        await page.click("button:has-text('进入')")
        err_msg = await page.text_content("#gate-err")
        results["P0_wrong_password_rejected"] = "密码错误" in (err_msg or "")

        # 正确密码
        await page.fill("#gate-input", "nsp2026")
        await page.click("button:has-text('进入')")
        await page.wait_for_timeout(300)
        gate_hidden = not await page.is_visible("#gate")
        results["P0_correct_password_accepted"] = gate_hidden

        # 2. Tab 切换 (6个)
        tab_btns = await page.query_selector_all(".tab-btn")
        results["P0_tab_button_count"] = len(tab_btns)

        tab_names = []
        for b in tab_btns:
            tab_names.append(await b.text_content())
        results["P0_tab_names"] = tab_names

        # 切换每个 Tab
        tab_views = []
        for i, btn in enumerate(tab_btns):
            await btn.click()
            await page.wait_for_timeout(150)
            active_views = await page.query_selector_all(".view.active")
            for av in active_views:
                vid = await av.get_attribute("id")
                tab_views.append(vid)
        results["P0_tab_switch_works"] = len(set(tab_views)) >= 5

        # 3. Tab1 内容
        await page.click('.tab-btn[data-view="view-1"]')
        await page.wait_for_timeout(200)
        nb_count = await page.locator("#nb .nsi").count()
        nbg_count = await page.locator("#nbg .nbx").count()
        results["T1_5_net_boxes"] = nb_count
        results["T1_net_groups"] = nbg_count

        # 4. Tab2 政策
        await page.click('.tab-btn[data-view="view-2"]')
        await page.wait_for_timeout(200)
        policy_cards = await page.locator(".pcard").count()
        results["T2_policy_cards"] = policy_cards

        # 5. Tab3 行动建议
        await page.click('.tab-btn[data-view="view-3"]')
        await page.wait_for_timeout(200)
        actions = await page.locator(".action-card").count()
        results["T3_action_cards"] = actions

        # 6. Tab5 商业模式
        await page.click('.tab-btn[data-view="view-5"]')
        await page.wait_for_timeout(200)
        cats = await page.locator(".m5cat").count()
        cards = await page.locator(".m5card").count()
        coops = await page.locator(".m5coop").count()
        risks = await page.locator(".m5rx").count()
        results["T5_categories"] = cats
        results["T5_modes"] = cards
        results["T5_cooperations"] = coops
        results["T5_risks"] = risks

        # 7. Tab6 真实案例
        await page.click('.tab-btn[data-view="view-6"]')
        await page.wait_for_timeout(200)
        mode_chips = await page.locator(".t6mode").count()
        case_cards = await page.locator(".t6card").count()
        table_rows = await page.locator("#t6rows tr").count()
        results["T6_mode_categories"] = mode_chips
        results["T6_case_cards"] = case_cards
        results["T6_table_rows"] = table_rows

        # 8. Tab7 智能简报
        await page.click('.tab-btn[data-view="view-7"]')
        await page.wait_for_timeout(200)
        # 初始状态
        before = await page.locator("#brief-content").text_content()
        results["T7_initial_empty"] = "生成简报" in (before or "") or "点击" in (before or "")

        # 点生成
        await page.click("#btn-gen")
        await page.wait_for_timeout(300)
        after = await page.locator("#brief-content").text_content()
        results["T7_after_gen_has_content"] = "26.9" in (after or "") and "头条" in (after or "")

        # 9. 弹窗测试
        await page.click('.tab-btn[data-view="view-1"]')
        await page.wait_for_timeout(200)
        # 点水网块
        first_net = page.locator(".nbx").first
        await first_net.click()
        await page.wait_for_timeout(300)
        modal_visible = await page.is_visible("#modal.show")
        results["P0_network_modal_works"] = modal_visible

        # 关闭
        await page.click("#modal .close")
        await page.wait_for_timeout(200)

        # 政策弹窗（实际是 alert）
        # 测试项目弹窗
        await page.click(".nbx")
        await page.wait_for_timeout(200)
        modal2 = await page.is_visible("#modal.show")
        await page.locator(".action-card").first.click()
        await page.wait_for_timeout(300)
        # 项目详情弹窗
        invest_text = await page.text_content("#m-invest")
        results["P0_project_modal_invest"] = invest_text

        await page.click("#modal .close")
        await page.wait_for_timeout(200)

        # 10. 横向溢出检查
        body_w = await page.evaluate("document.body.scrollWidth")
        view_w = await page.evaluate("window.innerWidth")
        results["UI_no_horizontal_overflow_PC"] = body_w <= view_w + 1

        # 11. JS 错误
        results["JS_errors_count"] = len(page_errors) + len(console_errors)
        results["JS_errors_detail"] = page_errors + console_errors

        await browser.close()
        return results

results = asyncio.run(main())
print(json.dumps(results, ensure_ascii=False, indent=2))
