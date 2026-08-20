"""D30 WDW self-verification: 5网精确分数 + 7 tabs + 0 JS errors."""
from playwright.sync_api import sync_playwright
import json, sys, pathlib

ROOT = pathlib.Path(r"D:\hermes-dev-team\nsp-im")
HTML = ROOT / "docs" / "preview" / "index.html"

EXPECTED = {
    "compute": 9.7, "telecom": 9.6, "water": 8.9, "pipe": 8.8, "logi": 8.0,
}
COUPLING_EXPECTED = {  # D28 retained
    "water": 8.62, "compute": 8.71, "telecom": 8.54, "pipe": 5.88, "logi": 8.64,
}
NET_LABEL = {"water":"水网","compute":"算力网","telecom":"通信网","pipe":"城市地下管网","logi":"物流网"}

js_errors = []
console_msgs = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context()
    page = ctx.new_page()

    page.on("pageerror", lambda e: js_errors.append(f"PAGEERROR: {e}"))
    page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text}") if m.type in ("error","warning") else None)

    page.goto(f"file://{HTML}")
    page.wait_for_load_state("networkidle")

    # Bypass gate: enter password nsp2026 (or hide gate directly)
    try:
        page.fill("#gate-input", "nsp2026")
        page.click("button:has-text('进入')")
        page.wait_for_timeout(300)
    except Exception:
        pass
    # Fallback: hide gate directly via JS in case password changed
    page.evaluate("() => { const g = document.getElementById('gate'); if (g) g.classList.add('hide'); }")
    page.wait_for_timeout(200)

    # Check 1: All 7 tabs exist and clickable
    tab_buttons = page.locator(".tab-btn")
    tab_count = tab_buttons.count()
    tab_views = []
    for i in range(tab_count):
        btn = tab_buttons.nth(i)
        tab_views.append({
            "view": btn.get_attribute("data-view"),
            "label": btn.inner_text().strip(),
        })

    # Check 2: 5网分数 in Tab1 (#nb) and 耦合值 (D28)
    net_scores = page.evaluate("""
        () => {
          const nb = document.getElementById('nb');
          if (!nb) return null;
          const items = nb.querySelectorAll('.nsi');
          const out = {};
          items.forEach(el => {
            const txt = el.innerText;
            const match = txt.match(/(水网|算力网|通信网|城市地下管网|物流网)/);
            const score = txt.match(/(\\d+\\.\\d+)/);
            const coup = txt.match(/耦合\\s*(\\d+\\.\\d+)/);
            if (match && score) {
              out[match[1]] = {score: parseFloat(score[1]), coupling: coup ? parseFloat(coup[1]) : null};
            }
          });
          return out;
        }
    """)

    # Check 3: Click all 7 tabs and verify each renders without JS errors
    tab_results = []
    for i in range(tab_count):
        tab_buttons.nth(i).click()
        page.wait_for_timeout(150)
        view_id = tab_views[i]["view"]
        is_visible = page.evaluate(f"() => {{ const v = document.getElementById('{view_id}'); return v && getComputedStyle(v).display !== 'none'; }}")
        tab_results.append({"view": view_id, "label": tab_views[i]["label"], "visible": is_visible})

    # Check 4: HTML size
    size_bytes = HTML.stat().st_size

    browser.close()

# Build report
report = {
    "html_bytes": size_bytes,
    "html_kb": round(size_bytes/1024, 2),
    "html_under_80kb": size_bytes <= 80 * 1024,
    "tab_count": tab_count,
    "tabs": tab_views,
    "tab_render_results": tab_results,
    "all_tabs_visible": all(t["visible"] for t in tab_results),
    "net_scores_observed": net_scores,
    "net_score_check": {},
    "coupling_check": {},
    "js_errors": js_errors,
    "console_errors": [m for m in console_msgs if "[error]" in m],
    "console_warnings": [m for m in console_msgs if "[warning]" in m],
}

# Verify expected vs observed
KEY_MAP = {"水网":"water","算力网":"compute","通信网":"telecom","城市地下管网":"pipe","物流网":"logi"}
for label, key in KEY_MAP.items():
    obs = net_scores.get(label, {})
    exp_s = EXPECTED[key]
    exp_c = COUPLING_EXPECTED[key]
    report["net_score_check"][key] = {
        "label": label,
        "expected_score": exp_s,
        "observed_score": obs.get("score"),
        "score_match": obs.get("score") == exp_s,
        "expected_coupling": exp_c,
        "observed_coupling": obs.get("coupling"),
        "coupling_match": obs.get("coupling") == exp_c,
    }

# Verdict
all_ok = (
    report["html_under_80kb"]
    and report["tab_count"] == 7
    and report["all_tabs_visible"]
    and all(v["score_match"] for v in report["net_score_check"].values())
    and all(v["coupling_match"] for v in report["net_score_check"].values())
    and len(js_errors) == 0
)
report["VERDICT"] = "PASS" if all_ok else "FAIL"

print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if all_ok else 1)