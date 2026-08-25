"""D32 WDW self-verification: Demo 政策 URL 404 fix + Tab2 demo-tip banner."""
from playwright.sync_api import sync_playwright
import json, sys, pathlib

ROOT = pathlib.Path(r"D:\hermes-dev-team\nsp-im")
HTML = ROOT / "docs" / "preview" / "index.html"

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

    # --- D32 Check 1: 7 tabs exist ---
    tab_buttons = page.locator(".tab-btn")
    tab_count = tab_buttons.count()
    tab_views = []
    for i in range(tab_count):
        btn = tab_buttons.nth(i)
        tab_views.append({
            "view": btn.get_attribute("data-view"),
            "label": btn.inner_text().strip(),
        })

    # --- D32 Check 2: Switch to Tab2, verify demo-tip banner ---
    page.locator('.tab-btn[data-view="view-2"]').click()
    page.wait_for_timeout(300)

    demo_tip_check = page.evaluate("""
        () => {
            const tip = document.querySelector('.demo-tip');
            if (!tip) return { exists: false };
            const text = tip.innerText.trim();
            return {
                exists: true,
                visible: getComputedStyle(tip).display !== 'none',
                text: text,
                has_demo_keyword: text.indexOf('演示数据') >= 0,
                has_cron_keyword: text.indexOf('cron') >= 0,
                bg_color: getComputedStyle(tip).backgroundColor,
            };
        }
    """)

    # --- D32 Check 3: Verify all 5 policy link hrefs are "#" (no 404) ---
    policy_links = page.evaluate("""
        () => {
            const links = document.querySelectorAll('#plist .pcard .plink');
            return Array.from(links).map(a => ({
                href: a.getAttribute('href'),
                text: a.innerText.trim(),
                target: a.getAttribute('target'),
            }));
        }
    """)

    # --- D32 Check 4: All 7 tabs visible ---
    tab_results = []
    for i in range(tab_count):
        tab_buttons.nth(i).click()
        page.wait_for_timeout(150)
        view_id = tab_views[i]["view"]
        is_visible = page.evaluate(f"() => {{ const v = document.getElementById('{view_id}'); return v && getComputedStyle(v).display !== 'none'; }}")
        tab_results.append({"view": view_id, "label": tab_views[i]["label"], "visible": is_visible})

    # --- D32 Check 5: Switch back to Tab2 and screenshot ---
    page.locator('.tab-btn[data-view="view-2"]').click()
    page.wait_for_timeout(300)
    page.screenshot(path=str(ROOT / "screenshots" / "d32_demo_tip.png"), full_page=True)

    size_bytes = HTML.stat().st_size
    browser.close()

# --- Validate ---
all_links_safe = all(link["href"] == "#" for link in policy_links)
all_links_present = len(policy_links) == 5
no_404 = all_links_safe and all_links_present

report = {
    "html_bytes": size_bytes,
    "html_kb": round(size_bytes / 1024, 2),
    "html_under_85kb": size_bytes <= 85 * 1024,
    "tab_count": tab_count,
    "tabs": tab_views,
    "tab_render_results": tab_results,
    "all_tabs_visible": all(t["visible"] for t in tab_results),
    "D32_demo_tip": demo_tip_check,
    "D32_demo_tip_ok": (
        demo_tip_check
        and demo_tip_check.get("exists")
        and demo_tip_check.get("visible")
        and demo_tip_check.get("has_demo_keyword")
        and demo_tip_check.get("has_cron_keyword")
    ),
    "D32_policy_links": policy_links,
    "D32_policy_link_count": len(policy_links),
    "D32_all_links_have_hash_href": all_links_safe,
    "D32_no_404": no_404,
    "js_errors": js_errors,
    "console_errors": [m for m in console_msgs if "[error]" in m],
    "console_warnings": [m for m in console_msgs if "[warning]" in m],
}

# Verdict
all_ok = (
    report["html_under_85kb"]
    and report["tab_count"] == 7
    and report["all_tabs_visible"]
    and report["D32_demo_tip_ok"]
    and report["D32_no_404"]
    and len(js_errors) == 0
)
report["VERDICT"] = "PASS" if all_ok else "FAIL"

print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if all_ok else 1)
