"""D33 WDW self-verification: 25 projects + 11 cases source.url → '#' + demo-tip."""
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

    # --- D33 Check 1: 7 tabs exist ---
    tab_buttons = page.locator(".tab-btn")
    tab_count = tab_buttons.count()
    tab_views = []
    for i in range(tab_count):
        btn = tab_buttons.nth(i)
        tab_views.append({
            "view": btn.get_attribute("data-view"),
            "label": btn.inner_text().strip(),
        })

    # --- D33 Check 2: Switch to Tab1, verify 25 project URLs are "#" via PROJECTS array ---
    page.locator('.tab-btn[data-view="view-1"]').click()
    page.wait_for_timeout(300)

    project_urls = page.evaluate("""
        () => {
            // PROJECTS is in scope (file:// works because all is in one html)
            return PROJECTS.map(p => ({
                id: p.id,
                name: p.name,
                url: p.source.url,
                is_hash: p.source.url === "#",
                has_https: typeof p.source.url === "string" && p.source.url.indexOf("https://") === 0
            }));
        }
    """)

    # --- D33 Check 3: Click first project, verify modal renders + demo-tip + URL is "#" ---
    page.evaluate("() => { openProject('C1'); }")
    page.wait_for_timeout(300)

    project_modal = page.evaluate("""
        () => {
            const tip = document.querySelector('#modal-content .demo-tip');
            const link = document.querySelector('#m-source-url');
            return {
                modal_visible: document.getElementById('modal').classList.contains('show'),
                demo_tip_exists: !!tip,
                demo_tip_text: tip ? tip.innerText.trim() : null,
                source_url_href: link ? link.getAttribute('href') : null,
                source_link_text: link ? link.innerText.trim() : null,
            };
        }
    """)
    page.evaluate("() => closeModal()")
    page.wait_for_timeout(200)

    # --- D33 Check 4: Switch to Tab6, click first case, verify demo-tip ---
    page.locator('.tab-btn[data-view="view-6"]').click()
    page.wait_for_timeout(300)

    page.evaluate("() => { openCase(1); }")
    page.wait_for_timeout(300)

    case_modal = page.evaluate("""
        () => {
            const tip = document.querySelector('#modal-content .demo-tip');
            const link = document.querySelector('#modal-content a[href]');
            return {
                modal_visible: document.getElementById('modal').classList.contains('show'),
                demo_tip_exists: !!tip,
                demo_tip_text: tip ? tip.innerText.trim() : null,
                first_link_href: link ? link.getAttribute('href') : null,
            };
        }
    """)
    page.evaluate("() => closeModal()")
    page.wait_for_timeout(200)

    # --- D33 Check 5: All 7 tabs visible ---
    tab_results = []
    for i in range(tab_count):
        tab_buttons.nth(i).click()
        page.wait_for_timeout(150)
        view_id = tab_views[i]["view"]
        is_visible = page.evaluate(f"() => {{ const v = document.getElementById('{view_id}'); return v && getComputedStyle(v).display !== 'none'; }}")
        tab_results.append({"view": view_id, "label": tab_views[i]["label"], "visible": is_visible})

    # --- D33 Check 6: Screenshot Tab1 (project modal demo-tip) ---
    page.locator('.tab-btn[data-view="view-1"]').click()
    page.wait_for_timeout(300)
    page.evaluate("() => { openProject('W1'); }")
    page.wait_for_timeout(400)
    page.screenshot(path=str(ROOT / "screenshots" / "d33_project_demo_tip.png"), full_page=True)
    page.evaluate("() => closeModal()")
    page.wait_for_timeout(200)

    # --- D33 Check 7: Screenshot Tab6 (case modal demo-tip) ---
    page.locator('.tab-btn[data-view="view-6"]').click()
    page.wait_for_timeout(300)
    page.evaluate("() => { openCase(5); }")
    page.wait_for_timeout(400)
    page.screenshot(path=str(ROOT / "screenshots" / "d33_case_demo_tip.png"), full_page=True)

    size_bytes = HTML.stat().st_size
    browser.close()

# --- Validate ---
all_25_urls_hash = len(project_urls) == 25 and all(p["is_hash"] for p in project_urls)
no_25_https = all(not p["has_https"] for p in project_urls)

report = {
    "html_bytes": size_bytes,
    "html_kb": round(size_bytes / 1024, 2),
    "html_under_85kb": size_bytes <= 85 * 1024,
    "tab_count": tab_count,
    "tabs": tab_views,
    "tab_render_results": tab_results,
    "all_tabs_visible": all(t["visible"] for t in tab_results),
    "D33_project_count": len(project_urls),
    "D33_project_urls": project_urls,
    "D33_all_25_urls_hash": all_25_urls_hash,
    "D33_no_https_urls": no_25_https,
    "D33_project_modal": project_modal,
    "D33_project_modal_ok": (
        project_modal.get("modal_visible")
        and project_modal.get("demo_tip_exists")
        and project_modal.get("demo_tip_text", "").find("演示数据") >= 0
        and project_modal.get("source_url_href") == "#"
    ),
    "D33_case_modal": case_modal,
    "D33_case_modal_ok": (
        case_modal.get("modal_visible")
        and case_modal.get("demo_tip_exists")
        and case_modal.get("demo_tip_text", "").find("演示数据") >= 0
        and case_modal.get("first_link_href") == "#"
    ),
    "js_errors": js_errors,
    "console_errors": [m for m in console_msgs if "[error]" in m],
    "console_warnings": [m for m in console_msgs if "[warning]" in m],
}

# Verdict
all_ok = (
    report["html_under_85kb"]
    and report["tab_count"] == 7
    and report["all_tabs_visible"]
    and report["D33_all_25_urls_hash"]
    and report["D33_no_https_urls"]
    and report["D33_project_modal_ok"]
    and report["D33_case_modal_ok"]
    and len(js_errors) == 0
)
report["VERDICT"] = "PASS" if all_ok else "FAIL"

print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if all_ok else 1)