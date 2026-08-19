import asyncio, json
from playwright.async_api import async_playwright

FILE = r"D:\hermes-dev-team\nsp-im\docs\preview\index.html"
URL = "file:///" + FILE.replace("\\", "/")

async def run(p, viewport, label):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport=viewport)
    page = await ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append(f"[{m.type}] {m.text}") if m.type in ("error","warning") else None)
    await page.goto(URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(500)

    r = {"label": label, "viewport": viewport, "errors": errs[:5]}

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

    btns = await page.query_selector_all(".tab-btn")
    r["tab_count"] = len(btns)
    for b in btns:
        await b.click()
        await page.wait_for_timeout(80)
    r["no_js_error_after_tab_switch"] = len(errs) == 0

    await page.click('.tab-btn[data-view="view-1"]')
    await page.wait_for_timeout(200)
    r["T1_net_summary"] = await page.locator("#nb .nsi").count()
    r["T1_net_cards"] = await page.locator("#nbg .nbx").count()

    await page.click('.tab-btn[data-view="view-2"]')
    await page.wait_for_timeout(200)
    r["T2_policy_count"] = await page.locator(".pcard").count()

    await page.click('.tab-btn[data-view="view-3"]')
    await page.wait_for_timeout(200)
    r["T3_action_count"] = await page.locator(".action-card").count()
    body = await page.text_content("#view-3")
    r["T3_has_26_9"] = "26.9" in (body or "")
    r["T3_has_chou_xiu"] = "抽水蓄能" in (body or "")

    await page.click('.tab-btn[data-view="view-5"]')
    await page.wait_for_timeout(200)
    r["T5_cats"] = await page.locator(".m5cat").count()
    r["T5_modes"] = await page.locator(".m5card").count()
    r["T5_coops"] = await page.locator(".m5coop").count()
    r["T5_risks"] = await page.locator(".m5rx").count()

    await page.click('.tab-btn[data-view="view-6"]')
    await page.wait_for_timeout(200)
    r["T6_modes"] = await page.locator(".t6mode").count()
    r["T6_cards"] = await page.locator(".t6card").count()
    r["T6_rows"] = await page.locator("#t6rows tr").count()

    await page.click('.tab-btn[data-view="view-7"]')
    await page.wait_for_timeout(200)
    initial = await page.text_content("#brief-content")
    r["T7_initial_empty"] = "生成" in (initial or "") and ("点击" in (initial or "") or "合成" in (initial or ""))

    await page.click("#btn-gen")
    await page.wait_for_timeout(400)
    after = await page.text_content("#brief-content")
    r["T7_after_gen_length"] = len(after or "")
    r["T7_has_26_9"] = "26.9" in (after or "")
    r["T7_has_5nets"] = "5 网协同" in (after or "")
    r["T7_has_4dirs"] = "4 大方向" in (after or "")

    await page.click("#btn-copy")
    await page.wait_for_timeout(300)
    r["T7_copy_toast"] = await page.is_visible("#t7toast.show")

    try:
        async with page.expect_download(timeout=5000) as dl_info:
            await page.click("#btn-export")
        dl = await dl_info.value
        r["T7_export_filename"] = dl.suggested_filename
    except Exception as e:
        r["T7_export_filename"] = f"ERR: {type(e).__name__}"

    # 弹窗：网络
    await page.click('.tab-btn[data-view="view-1"]')
    await page.wait_for_timeout(300)
    await page.locator(".nbx").first.click()
    await page.wait_for_timeout(300)
    r["network_modal_visible"] = await page.is_visible("#modal.show")
    modal_text = await page.text_content("#modal-content")
    r["network_modal_has_W1"] = "W1" in (modal_text or "")
    r["network_modal_has_W2"] = "W2" in (modal_text or "")
    r["network_modal_project_count"] = await page.locator("#modal-content .action-card").count()

    # 用 JS 直接触发 openProject
    await page.evaluate("openProject('W1')")
    await page.wait_for_timeout(300)
    r["project_modal_invest"] = await page.text_content("#m-invest")
    r["project_modal_total"] = await page.text_content("#m-total")
    r["project_modal_eval"] = (await page.text_content("#m-eval") or "")[:60]
    r["project_modal_r1"] = await page.text_content("#m-r1")

    await page.evaluate("closeModal()")
    await page.wait_for_timeout(200)

    # 横向溢出
    bw = await page.evaluate("document.body.scrollWidth")
    vw = await page.evaluate("window.innerWidth")
    r["body_w"] = bw
    r["view_w"] = vw
    r["no_horizontal_overflow"] = bw <= vw + 1

    await browser.close()
    return r

async def main():
    async with async_playwright() as p:
        out = {}
        for label, vp in [("PC",{"width":1440,"height":900}), ("Tablet",{"width":768,"height":1024}), ("Mobile",{"width":375,"height":812})]:
            try:
                out[label] = await run(p, vp, label)
            except Exception as e:
                out[label] = {"err": str(e)[:200]}
        return out

result = asyncio.run(main())
print(json.dumps(result, ensure_ascii=False, indent=2))