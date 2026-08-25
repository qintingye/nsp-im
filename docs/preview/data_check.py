"""D22 data integrity check via JS evaluation."""
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = ctx.new_page()
    page.goto("http://localhost:8080/", wait_until="networkidle", timeout=15000)
    page.fill("#gate-input", "nsp2026")
    page.click(".gate-box button")
    page.wait_for_selector(".tab-btn", timeout=5000)
    page.wait_for_timeout(300)

    overview = page.evaluate("""() => ({
        MODES_S_count: Object.keys(MODES_S).length,
        MODES_S_keys: Object.keys(MODES_S),
        PROJECT_MODE_MAP_count: Object.keys(PROJECT_MODE_MAP).length,
        PROJECT_MODE_MAP_keys: Object.keys(PROJECT_MODE_MAP),
        C1_sample: PROJECT_MODE_MAP['C1'],
    })""")
    project_check = page.evaluate("""() => {
        const out = {};
        for (const [k, v] of Object.entries(PROJECT_MODE_MAP)) {
            out[k] = {name: v.name, rec_count: v.推荐.length, has_reason: !!v.理由, reason: v.理由};
        }
        return out;
    }""")
    swot_check = page.evaluate("""() => {
        const out = {};
        for (const [k, v] of Object.entries(MODES_S)) {
            out[k] = {
                category: v.category,
                优势_count: v.swot.优势?.length || 0,
                劣势_count: v.swot.劣势?.length || 0,
                适用_count: v.swot.适用?.length || 0,
                不适用_count: v.swot.不适用?.length || 0,
                风险等级: v.swot.风险等级,
                ROE: v.swot.ROE,
                案例_count: v.典型案例?.length || 0,
            };
        }
        return out;
    }""")
    print(json.dumps({
        "overview": overview,
        "project_check": project_check,
        "swot_check": swot_check,
    }, ensure_ascii=False, indent=2))
    browser.close()