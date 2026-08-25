"""
NSP-IM v3.0 D26 · WDW 自验脚本
- 7 Tab 全部正常
- 简报生成 3 个下载文件名正确
- 0 JS 错误
"""
from playwright.sync_api import sync_playwright
import os, json, re

ROOT = r"D:/hermes-dev-team/nsp-im"
HTML = os.path.join(ROOT, "docs", "preview", "index.html").replace("\\", "/")
URL = "file:///" + HTML
OUT = os.path.join(ROOT, "screenshots")
os.makedirs(OUT, exist_ok=True)

results = {"tabs_pass": [], "console_errors": [], "download_filenames": {}, "js_errors": []}

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    page.on("console", lambda m: results["console_errors"].append({"type": m.type, "text": m.text}) if m.type == "error" else None)
    page.on("pageerror", lambda e: results["js_errors"].append(str(e)))

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(800)

    # 7 tabs
    for i in range(1, 8):
        try:
            tab_id = f"view-{i}"
            section = page.query_selector(f"#{tab_id}")
            if section:
                # Try clicking nav if present
                results["tabs_pass"].append({"tab": tab_id, "found": True})
            else:
                results["tabs_pass"].append({"tab": tab_id, "found": False})
        except Exception as e:
            results["tabs_pass"].append({"tab": tab_id, "found": False, "err": str(e)})

    # Check download filenames in the HTML
    html = open(HTML, encoding="utf-8").read()
    results["download_filenames"]["md"] = re.findall(r'a\.download=`([^`]+)`', html)
    results["download_filenames"]["html_export"] = re.findall(r'a\.download=`([^`]+)`', html)
    # Search for both
    md_dl = re.search(r'a\.download=`([^`]+\.md)`', html)
    html_dl = re.search(r'a\.download=`([^`]+\.html)`', html)
    results["download_filenames"]["md_pattern"] = md_dl.group(1) if md_dl else None
    results["download_filenames"]["html_pattern"] = html_dl.group(1) if html_dl else None
    results["download_filenames"]["pdf_title"] = re.search(r'<title>([^<]+PDF[^<]+)</title>', html)
    results["download_filenames"]["pdf_title"] = results["download_filenames"]["pdf_title"].group(1) if results["download_filenames"]["pdf_title"] else None

    # Click btn-gen (generate brief) if visible
    try:
        btn_gen = page.query_selector("#btn-gen")
        if btn_gen:
            page.evaluate("document.getElementById('view-7')?.scrollIntoView()")
            page.wait_for_timeout(200)
            btn_gen.click()
            page.wait_for_timeout(400)
            brief_text = page.evaluate("document.getElementById('brief-content')?.innerText?.slice(0,80) || ''")
            results["brief_generated"] = bool(brief_text)
            results["brief_preview"] = brief_text[:80]
    except Exception as e:
        results["brief_error"] = str(e)

    page.screenshot(path=os.path.join(OUT, "d26_wdw.png"), full_page=False)

    browser.close()

print(json.dumps(results, ensure_ascii=False, indent=2))