#!/usr/bin/env python3
"""
W3-D4: 用 Playwright 把一个 SVG/HTML 渲染成 PWA 图标
- 输出 docs/preview/icons/icon-{192,512,maskable}.png
- 设计：白底 + 蓝色 #1a73e8 + "六网"中心枢纽图（六色环 + 中央 NSP）
- 不依赖 PIL/cairosvg（项目 venv 里 PIL 损坏，cairosvg 未装）
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

PREVIEW = Path(__file__).resolve().parents[1] / "docs" / "preview"
ICONS = PREVIEW / "icons"
ICONS.mkdir(parents=True, exist_ok=True)

# 颜色（与 index.html :root 一致）
PRIMARY = "#1a73e8"
SCOPES = {
    "grid":    "#34a853",
    "water":   "#4285f4",
    "compute": "#ea4335",
    "telecom": "#fbbc04",
    "pipe":    "#9c27b0",
    "logi":    "#00acc1",
}

def make_html(size: int, maskable: bool = False) -> str:
    """
    设计原则（修复上一轮 vision 反馈）：
    - 留 10% 边距（iOS 圆角裁剪、maskable 圆形裁剪通用）
    - 6 节点半径缩小至 34%，绝不触边
    - 节点之间不重叠（电/水/算/通/管/物均匀分布）
    - 无底部文字（品牌信息在 manifest.name 里）
    - maskable 安全区 = 中间 80%
    """
    import math
    cx = cy = size / 2
    # 关键：外环半径按 size 比例算后扣 8% 边距
    radius_outer = size * 0.34          # 上一轮 0.42 → 0.34
    radius_inner = size * 0.14          # 中心枢纽半径
    node_r       = size * 0.075         # 外环节点半径
    line_w       = size * 0.012

    labels = ["电", "水", "算", "通", "管", "物"]
    scopes = list(SCOPES.values())

    nodes = []
    for i in range(6):
        angle = math.radians(i * 60 - 90)  # 从正上方开始，顺时针
        x = cx + radius_outer * math.cos(angle)
        y = cy + radius_outer * math.sin(angle)
        nodes.append((x, y, scopes[i], labels[i]))

    nodes_html = "\n".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{node_r:.1f}" fill="{c}" />'
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="{size*0.095:.1f}" font-family="sans-serif" font-weight="700" fill="#fff">{l}</text>'
        for (x, y, c, l) in nodes
    )

    lines_html = "\n".join(
        f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
        f'stroke="{c}" stroke-width="{line_w:.1f}" opacity="0.55" />'
        for (x, y, c, _) in nodes
    )

    text_size = size * 0.135

    bg_fill = "#1a73e8" if maskable else "#ffffff"
    bg_rx = "" if maskable else f'rx="{size*0.22:.1f}"'

    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
  html, body {{ margin:0; padding:0; background:{bg_fill}; }}
  body {{ display:flex; align-items:center; justify-content:center;
         width:{size}px; height:{size}px; }}
  svg {{ display:block; width:{size}px; height:{size}px; }}
</style></head><body>
<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="{size}" height="{size}" {bg_rx} fill="{bg_fill}" />
  {lines_html}
  {nodes_html}
  <circle cx="{cx}" cy="{cy}" r="{radius_inner}" fill="{PRIMARY}" />
  <text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="central"
        font-size="{text_size:.1f}" font-weight="800" fill="#fff"
        font-family="-apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif">NSP</text>
</svg>
</body></html>"""


def render(page, html: str, size: int, out: Path):
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(html, wait_until="load")
    page.screenshot(path=str(out), omit_background=False, clip={"x":0,"y":0,"width":size,"height":size})
    print(f"  → {out.name}  ({size}x{size}, {out.stat().st_size} bytes)")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # 192 普通
        render(page, make_html(192, maskable=False), 192, ICONS / "icon-192.png")
        # 512 普通
        render(page, make_html(512, maskable=False), 512, ICONS / "icon-512.png")
        # 512 maskable（Android 12+ 圆形遮罩安全）
        render(page, make_html(512, maskable=True), 512, ICONS / "icon-512-maskable.png")
        # 额外给一个 180 iOS apple-touch-icon（单尺寸足够 iOS）
        render(page, make_html(180, maskable=False), 180, ICONS / "apple-touch-icon.png")
        browser.close()
    print(f"✅ 图标生成完毕 → {ICONS}")


if __name__ == "__main__":
    main()