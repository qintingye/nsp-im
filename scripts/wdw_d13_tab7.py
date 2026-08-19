"""V3.0 D13 WDW self-verification — Tab7: 5 export buttons, no JS errors."""
import asyncio, json, os
from playwright.async_api import async_playwright

FILE = r"D:\hermes-dev-team\nsp-im\docs\preview\index.html"
URL = "file:///" + FILE.replace("\\", "/")

async def run(p, viewport, label):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(
        viewport=viewport,
        accept_downloads=True,
    )
    page = await ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(f"[pageerror] {e}"))
    page.on("console", lambda m: errs.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
    await page.goto(URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(500)

    r = {"label": label, "viewport": viewport, "errors": list(errs)}

    # gate login
    r["gate_visible"] = await page.is_visible("#gate")
    await page.fill("#gate-input", "nsp2026")
    await page.click("button:has-text('进入')")
    await page.wait_for_timeout(300)
    r["correct_pwd_accepted"] = not await page.is_visible("#gate")

    # switch to Tab7
    await page.click('.tab-btn[data-view="view-7"]')
    await page.wait_for_timeout(200)

    # count Tab7 buttons
    btns = await page.query_selector_all(".t7btn")
    r["T7_btn_count"] = len(btns)
    r["T7_btn_ids"] = []
    for b in btns:
        bid = await b.get_attribute("id")
        btext = (await b.text_content() or "").strip()
        r["T7_btn_ids"].append({"id": bid, "text": btext})

    # generate brief
    await page.click("#btn-gen")
    await page.wait_for_timeout(400)
    after = await page.text_content("#brief-content")
    r["T7_after_gen_length"] = len(after or "")
    r["T7_has_data"] = "26.9" in (after or "") or "5 网" in (after or "")

    # 1) Copy button — toast
    await page.click("#btn-copy")
    await page.wait_for_timeout(300)
    r["T7_copy_toast"] = await page.is_visible("#t7toast.show")

    # 2) Export Markdown — download
    try:
        async with page.expect_download(timeout=5000) as dl_info:
            await page.click("#btn-export")
        dl = await dl_info.value
        r["T7_md_filename"] = dl.suggested_filename
        r["T7_md_ok"] = dl.suggested_filename.endswith(".md")
    except Exception as e:
        r["T7_md_filename"] = f"ERR: {type(e).__name__}: {e}"
        r["T7_md_ok"] = False

    # 3) Export HTML — download
    try:
        async with page.expect_download(timeout=5000) as dl_info:
            await page.click("#btn-export-html")
        dl = await dl_info.value
        r["T7_html_filename"] = dl.suggested_filename
        r["T7_html_ok"] = dl.suggested_filename.endswith(".html")
        # save it and inspect a few bytes to confirm content
        save_path = os.path.join(os.path.dirname(FILE), "_wdw_html_probe.html")
        await dl.save_as(save_path)
        with open(save_path, "rb") as f:
            head = f.read(200)
        r["T7_html_starts_with_doctype"] = head.lstrip().lower().startswith(b"<!doctype html>")
        r["T7_html_has_charset"] = b"charset" in head.lower()
        os.remove(save_path)
    except Exception as e:
        r["T7_html_filename"] = f"ERR: {type(e).__name__}: {e}"
        r["T7_html_ok"] = False

    # 4) Export PDF — opens new window with auto-print. Block the print dialog
    # and confirm the window wrote our payload.
    pdf_window_seen = {"ok": False, "title": "", "len": 0}
    def _on_page(p2):
        # New page = print popup
        async def _capture():
            try:
                await p2.wait_for_load_state("domcontentloaded", timeout=3000)
                title = await p2.title()
                body = await p2.text_content("body")
                pdf_window_seen["title"] = title
                pdf_window_seen["len"] = len(body or "")
                pdf_window_seen["ok"] = "NSP-IM" in title or "NSP-IM" in (body or "")
            except Exception:
                pass
        asyncio.create_task(_capture())
    ctx.on("page", lambda p2: _on_page(p2))

    try:
        await page.click("#btn-export-pdf")
        await page.wait_for_timeout(1500)
        r["T7_pdf_window_opened"] = pdf_window_seen["ok"]
        r["T7_pdf_window_title"] = pdf_window_seen["title"]
        r["T7_pdf_window_body_len"] = pdf_window_seen["len"]
    except Exception as e:
        r["T7_pdf_window_opened"] = f"ERR: {e}"

    # final error count
    r["final_errors"] = list(errs)
    r["zero_js_errors"] = len(errs) == 0

    # no horizontal overflow
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
        for label, vp in [
            ("PC",      {"width": 1440, "height": 900}),
            ("Tablet",  {"width": 768,  "height": 1024}),
            ("Mobile",  {"width": 375,  "height": 812}),
        ]:
            try:
                out[label] = await run(p, vp, label)
            except Exception as e:
                out[label] = {"err": str(e)[:300]}
        return out

result = asyncio.run(main())
print(json.dumps(result, ensure_ascii=False, indent=2))
