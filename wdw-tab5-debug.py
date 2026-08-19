"""Tab5 弹窗实测 — PC 1920x1080 + Mobile 375x812"""
from playwright.sync_api import sync_playwright
import json, sys

URL = "http://localhost:8080/"
PWD = "nsp2026"
OUT_DIR = r"D:\hermes-dev-team\nsp-im\screenshots\tab5-debug"

import os
os.makedirs(OUT_DIR, exist_ok=True)

def test_view(p, label, viewport):
    print(f"\n=== {label} {viewport} ===")
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=f"/tmp/chrome-{label}",
        headless=True,
        viewport=viewport,
        device_scale_factor=1,
    )
    page = ctx.new_page()
    console_msgs = []
    page_errors = []
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: page_errors.append(str(e)))

    # 1. 打开页面
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(500)

    # 2. 输入密码
    page.fill('#gate-input', PWD)
    page.click('text=进入')
    page.wait_for_timeout(500)

    # 3. 切到 Tab5
    page.click('button[data-view="view-5"]')
    page.wait_for_timeout(800)

    # 4. 截图：Tab5 默认
    page.screenshot(path=f"{OUT_DIR}/{label}_01_tab5_default.png", full_page=False)

    # 5. 检查 m5cards 是否渲染
    cards = page.query_selector_all('.m5card')
    print(f"  m5card 数: {len(cards)}")

    # 6. 检查第一张卡的 cursor / computed style
    if cards:
        first_card = cards[0]
        cursor_style = first_card.evaluate("el => getComputedStyle(el).cursor")
        print(f"  cursor: {cursor_style}")
        bbox = first_card.bounding_box()
        print(f"  bbox: {bbox}")

        # 7. hover 第一张卡
        first_card.hover()
        page.wait_for_timeout(400)
        page.screenshot(path=f"{OUT_DIR}/{label}_02_tab5_hover.png", full_page=False)
        hover_transform = first_card.evaluate("el => getComputedStyle(el).transform")
        hover_bg = first_card.evaluate("el => getComputedStyle(el).backgroundColor")
        print(f"  hover transform: {hover_transform}")
        print(f"  hover bg: {hover_bg}")

    # 8. click 第一张卡 → 检查弹窗
    if cards:
        cards[0].click()
        page.wait_for_timeout(500)
        modal_visible = page.evaluate("getComputedStyle(document.getElementById('modal')).display")
        modal_class = page.evaluate("document.getElementById('modal').className")
        modal_z = page.evaluate("getComputedStyle(document.getElementById('modal')).zIndex")
        modal_html_len = page.evaluate("document.getElementById('modal-content').innerHTML.length")
        print(f"  modal display: {modal_visible}  class: {modal_class}  z-index: {modal_z}")
        print(f"  modal-content innerHTML 长度: {modal_html_len}")
        page.screenshot(path=f"{OUT_DIR}/{label}_03_tab5_modal.png", full_page=False)

        # 关闭
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

    # 9. 测试 openCoop (合作模式卡)
    coops = page.query_selector_all('.m5coop')
    print(f"  m5coop 数: {len(coops)}")
    if coops:
        coops[0].click()
        page.wait_for_timeout(400)
        modal_class2 = page.evaluate("document.getElementById('modal').className")
        print(f"  合作弹窗 class: {modal_class2}")
        page.screenshot(path=f"{OUT_DIR}/{label}_04_tab5_coop.png", full_page=False)
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

    # 10. 测试 openRisk
    risks = page.query_selector_all('.m5rx')
    print(f"  m5rx 数: {len(risks)}")
    if risks:
        risks[0].click()
        page.wait_for_timeout(400)
        modal_class3 = page.evaluate("document.getElementById('modal').className")
        print(f"  风险弹窗 class: {modal_class3}")
        page.screenshot(path=f"{OUT_DIR}/{label}_05_tab5_risk.png", full_page=False)
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

    # 11. 测试 Tab1 对比
    page.click('button[data-view="view-1"]')
    page.wait_for_timeout(500)
    nbxs = page.query_selector_all('.nbx')
    print(f"  Tab1 nbx 数: {len(nbxs)}")
    if nbxs:
        nbxs[0].click()
        page.wait_for_timeout(400)
        modal_class4 = page.evaluate("document.getElementById('modal').className")
        print(f"  Tab1 nbx 弹窗 class: {modal_class4}")
        page.screenshot(path=f"{OUT_DIR}/{label}_06_tab1.png", full_page=False)
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

    # 12. Console & Errors
    print(f"\n  === console msgs ({len(console_msgs)}) ===")
    for m in console_msgs:
        if m["type"] in ("error", "warning"):
            print(f"    [{m['type']}] {m['text'][:200]}")
    print(f"  === page errors ({len(page_errors)}) ===")
    for e in page_errors:
        print(f"    {e[:200]}")

    ctx.close()

    return {
        "label": label,
        "console_errors": [m for m in console_msgs if m["type"] == "error"],
        "page_errors": page_errors,
    }


results = []
with sync_playwright() as p:
    r1 = test_view(p, "pc", {"width": 1920, "height": 1080})
    results.append(r1)
    r2 = test_view(p, "mobile", {"width": 375, "height": 812})
    results.append(r2)

print("\n\n========== SUMMARY ==========")
for r in results:
    print(f"\n{r['label']}:")
    print(f"  console errors: {len(r['console_errors'])}")
    print(f"  page errors: {len(r['page_errors'])}")
    for e in r["page_errors"][:5]:
        print(f"    {e[:300]}")

# 保存结果
with open(f"{OUT_DIR}/summary.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n截图已保存至 {OUT_DIR}")