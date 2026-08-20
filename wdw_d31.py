"""D31 WDW self-verification: Tab1 耦合分值热力图 + 7 tabs + 0 JS errors."""
from playwright.sync_api import sync_playwright
import json, sys, pathlib

ROOT = pathlib.Path(r"D:\hermes-dev-team\nsp-im")
HTML = ROOT / "docs" / "preview" / "index.html"

# 5×4 heatmap data — expected cell values
EXPECTED_HEATMAP = [
    {"net": "🧮 算力网",      "p": "3.8", "d": "4.0", "r": "1.9", "t": "9.7"},
    {"net": "📡 通信网",      "p": "3.7", "d": "4.0", "r": "1.9", "t": "9.6"},
    {"net": "💧 水网",        "p": "3.9", "d": "3.2", "r": "1.8", "t": "8.9"},
    {"net": "🔧 城市地下管网","p": "3.8", "d": "3.3", "r": "1.7", "t": "8.8"},
    {"net": "🚛 物流网",      "p": "3.4", "d": "3.1", "r": "1.5", "t": "8.0"},
]

js_errors = []
console_msgs = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context()
    page = ctx.new_page()

    page.on("pageerror", lambda e: js_errors.append(f"PAGEERROR: {e}"))
    page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)

    page.goto(f"file://{HTML}")
    page.wait_for_load_state("networkidle")

    # Bypass gate
    try:
        page.fill("#gate-input", "nsp2026")
        page.click("button:has-text('进入')")
        page.wait_for_timeout(300)
    except Exception:
        pass
    page.evaluate("() => { const g = document.getElementById('gate'); if (g) g.classList.add('hide'); }")
    page.wait_for_timeout(200)

    # --- Check 1: 7 tabs exist ---
    tab_buttons = page.locator(".tab-btn")
    tab_count = tab_buttons.count()
    tab_views = []
    for i in range(tab_count):
        btn = tab_buttons.nth(i)
        tab_views.append({
            "view": btn.get_attribute("data-view"),
            "label": btn.inner_text().strip(),
        })

    # --- Check 2: Tab1 contains the heatmap (5 rows × 4 data columns) ---
    heatmap_table_count = page.locator("table.heatmap").count()
    heatmap_rows = page.locator("table.heatmap tbody tr").count()
    heatmap_cells = page.locator("table.heatmap tbody td").count()  # 5 rows × 5 cols = 25 cells

    # Extract cell text per row
    rows_text = page.evaluate("""
        () => {
          const rows = document.querySelectorAll('table.heatmap tbody tr');
          return Array.from(rows).map(r =>
            Array.from(r.querySelectorAll('td')).map(td => td.innerText.trim())
          );
        }
    """)

    # --- Check 3: Color encoding — score cells must have a background color set ---
    # First-column cells (network names) intentionally have no bg color (label column).
    color_check = page.evaluate("""
        () => {
          const rows = document.querySelectorAll('table.heatmap tbody tr');
          const out = [];
          rows.forEach((r, ri) => {
            const cells = r.querySelectorAll('td');
            // Skip first column (network name label)
            for (let i = 1; i < cells.length; i++) {
              const td = cells[i];
              const cs = getComputedStyle(td);
              out.push({
                row: ri,
                col: i,
                text: td.innerText.trim(),
                cls: td.className,
                bg: cs.backgroundColor,
                color: cs.color,
                has_bg: cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent',
              });
            }
          });
          return out;
        }
    """)

    # --- Check 4: heatmap-wrap has overflow-x:auto (mobile scroll) ---
    overflow_check = page.evaluate("""
        () => {
          const w = document.querySelector('.heatmap-wrap');
          if (!w) return null;
          const cs = getComputedStyle(w);
          return { overflowX: cs.overflowX };
        }
    """)

    # --- Check 5: Switch all 7 tabs and verify visible ---
    tab_results = []
    for i in range(tab_count):
        tab_buttons.nth(i).click()
        page.wait_for_timeout(150)
        view_id = tab_views[i]["view"]
        is_visible = page.evaluate(f"() => {{ const v = document.getElementById('{view_id}'); return v && getComputedStyle(v).display !== 'none'; }}")
        tab_results.append({"view": view_id, "label": tab_views[i]["label"], "visible": is_visible})

    # --- Check 6: Click back to Tab1 and screenshot ---
    page.locator('.tab-btn[data-view="view-1"]').click()
    page.wait_for_timeout(150)
    page.screenshot(path=str(ROOT / "screenshots" / "d31_heatmap.png"), full_page=True)

    # --- Check 7: Mobile viewport — table still scrollable ---
    page.set_viewport_size({"width": 375, "height": 800})
    page.wait_for_timeout(200)
    mobile_scroll = page.evaluate("""
        () => {
          const w = document.querySelector('.heatmap-wrap');
          const t = document.querySelector('table.heatmap');
          if (!w || !t) return null;
          return {
            wrap_client_w: w.clientWidth,
            wrap_scroll_w: w.scrollWidth,
            overflows: w.scrollWidth > w.clientWidth,
            overflow_x: getComputedStyle(w).overflowX,
          };
        }
    """)
    page.screenshot(path=str(ROOT / "screenshots" / "d31_heatmap_mobile.png"), full_page=True)

    size_bytes = HTML.stat().st_size
    browser.close()

# --- Validate heatmap content ---
data_match = True
data_diffs = []
for i, row in enumerate(EXPECTED_HEATMAP):
    if i >= len(rows_text):
        data_match = False
        data_diffs.append(f"Row {i} missing")
        continue
    obs = rows_text[i]
    # Observed: [net, p, d, r, t]
    if obs[0] != row["net"] or obs[1] != row["p"] or obs[2] != row["d"] or obs[3] != row["r"] or obs[4] != row["t"]:
        data_match = False
        data_diffs.append(f"Row {i} mismatch: expected {row}, got {obs}")

# --- Validate color encoding ---
cells_with_bg = sum(1 for c in color_check if c["has_bg"])
all_cells_have_color = cells_with_bg == len(color_check) and len(color_check) > 0

report = {
    "html_bytes": size_bytes,
    "html_kb": round(size_bytes / 1024, 2),
    "html_under_85kb": size_bytes <= 85 * 1024,
    "tab_count": tab_count,
    "tabs": tab_views,
    "tab_render_results": tab_results,
    "all_tabs_visible": all(t["visible"] for t in tab_results),
    "D31_heatmap_table_count": heatmap_table_count,
    "D31_heatmap_rows": heatmap_rows,
    "D31_heatmap_cells": heatmap_cells,
    "D31_heatmap_rows_text": rows_text,
    "D31_heatmap_data_match": data_match,
    "D31_heatmap_data_diffs": data_diffs,
    "D31_heatmap_color_cells_with_bg": cells_with_bg,
    "D31_heatmap_color_all_have_bg": all_cells_have_color,
    "D31_heatmap_color_first_5": color_check[:5],
    "D31_heatmap_overflow_x": overflow_check,
    "D31_mobile_overflow": mobile_scroll,
    "D31_mobile_scroll_works": mobile_scroll and mobile_scroll["overflows"] and mobile_scroll["overflow_x"] == "auto",
    "js_errors": js_errors,
    "console_errors": [m for m in console_msgs if "[error]" in m],
    "console_warnings": [m for m in console_msgs if "[warning]" in m],
}

# Verdict
all_ok = (
    report["html_under_85kb"]
    and report["tab_count"] == 7
    and report["all_tabs_visible"]
    and report["D31_heatmap_table_count"] == 1
    and report["D31_heatmap_rows"] == 5
    and report["D31_heatmap_data_match"]
    and report["D31_heatmap_color_all_have_bg"]
    and report["D31_heatmap_overflow_x"] is not None
    and report["D31_heatmap_overflow_x"]["overflowX"] == "auto"
    and len(js_errors) == 0
)
report["VERDICT"] = "PASS" if all_ok else "FAIL"

print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if all_ok else 1)