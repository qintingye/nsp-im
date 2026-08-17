"""
W1-D3 响应式验证脚本
- 在 3 个 viewport (mobile 375, tablet 768, desktop 1280) 截图
- 3 个 SVG 视图各截一张 (mobile only, to keep it small)
- 验证 3 项核心指标: 无横向溢出 / SVG 可见 / 卡片单列
"""
import os
import sys
import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8765/01-%E5%85%AD%E7%BD%91%E5%8D%8F%E5%90%8C-W1D3-%E5%93%8D%E5%BA%94%E5%BC%8F.html"
OUT_DIR = r"D:\hermes-dev-team\nsp-im\docs\visualization\screenshots"

VIEWPORTS = [
    ("mobile-375",   375, 812,  True),   # 移动端: 375x812 (iPhone X)
    ("tablet-768",   768, 1024, True),   # 平板
    ("desktop-1280", 1280, 800, True),   # 桌面
    ("desktop-1920", 1920, 1080, False), # 桌面大屏 (只截架构总图)
]

# Mobile 极小屏 (TC-03 <480px 节点精简验证)
EXTREME_VIEWPORTS = [
    ("extreme-360", 360, 800),  # 极小屏
]

VIEWS = ["arch", "calc", "com"]  # 3 类 SVG

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp_name, w, h, all_views in VIEWPORTS:
            print(f"\n=== {vp_name} ({w}x{h}) ===")
            ctx = browser.new_context(viewport={"width": w, "height": h})
            page = ctx.new_page()
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=5000)

            # 截全屏 (架构总图, tab 默认)
            shot1 = os.path.join(OUT_DIR, f"{vp_name}_arch_full.png")
            page.screenshot(path=shot1, full_page=True)
            print(f"  [OK] arch full → {shot1}")

            # 验证: 是否有横向溢出
            scroll_w = page.evaluate("() => document.documentElement.scrollWidth")
            client_w = page.evaluate("() => document.documentElement.clientWidth")
            overflow = scroll_w > client_w
            print(f"  [Overflow] scrollW={scroll_w}, clientW={client_w}, overflow={overflow}")
            if overflow:
                print(f"  [WARN] 横向溢出! {vp_name}")

            # 验证: SVG 是否可见
            svg_visible = page.evaluate("""
                () => {
                    const svg = document.getElementById('svg-arch');
                    if (!svg) return null;
                    const rect = svg.getBoundingClientRect();
                    return {w: rect.width, h: rect.height, vis: rect.width > 0 && rect.height > 0};
                }
            """)
            print(f"  [SVG-arch] {svg_visible}")

            # 验证: <768px 卡片是否单列
            if w < 768:
                cols = page.evaluate("""
                    () => {
                        const cards = document.querySelector('.cards');
                        if (!cards) return null;
                        return getComputedStyle(cards).gridTemplateColumns;
                    }
                """)
                print(f"  [Cards grid-template-columns @ {w}px] {cols}")

            if all_views:
                # 切到算力网
                page.click('#tab-calc')
                page.wait_for_timeout(300)
                shot2 = os.path.join(OUT_DIR, f"{vp_name}_calc_full.png")
                page.screenshot(path=shot2, full_page=True)
                print(f"  [OK] calc full → {shot2}")

                # 切到通信网
                page.click('#tab-com')
                page.wait_for_timeout(300)
                shot3 = os.path.join(OUT_DIR, f"{vp_name}_com_full.png")
                page.screenshot(path=shot3, full_page=True)
                print(f"  [OK] com full → {shot3}")

            ctx.close()

        # 极小屏 <480px 验证 (节点精简)
        for vp_name, w, h in EXTREME_VIEWPORTS:
            print(f"\n=== {vp_name} ({w}x{h}) - 极小屏节点精简验证 ===")
            ctx = browser.new_context(viewport={"width": w, "height": h})
            page = ctx.new_page()
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=5000)

            # 验证: node-secondary 是否隐藏
            hidden_count = page.evaluate("""
                () => {
                    const nodes = document.querySelectorAll('.node-secondary');
                    let hidden = 0, visible = 0;
                    nodes.forEach(n => {
                        const cs = getComputedStyle(n);
                        if (cs.display === 'none') hidden++;
                        else visible++;
                    });
                    return {total: nodes.length, hidden, visible};
                }
            """)
            print(f"  [Node-secondary] {hidden_count}")

            arrow_count = page.evaluate("""
                () => {
                    const nodes = document.querySelectorAll('.arrow-secondary');
                    let hidden = 0, visible = 0;
                    nodes.forEach(n => {
                        const cs = getComputedStyle(n);
                        if (cs.display === 'none') hidden++;
                        else visible++;
                    });
                    return {total: nodes.length, hidden, visible};
                }
            """)
            print(f"  [Arrow-secondary] {arrow_count}")

            shot = os.path.join(OUT_DIR, f"{vp_name}_arch_full.png")
            page.screenshot(path=shot, full_page=True)
            print(f"  [OK] {shot}")

            ctx.close()

        browser.close()

    # 列出所有截图
    print(f"\n=== 截图列表 ({OUT_DIR}) ===")
    for f in sorted(os.listdir(OUT_DIR)):
        full = os.path.join(OUT_DIR, f)
        size_kb = os.path.getsize(full) / 1024
        print(f"  {f}  ({size_kb:.1f} KB)")

    print("\n[ALL DONE]")

if __name__ == "__main__":
    main()
