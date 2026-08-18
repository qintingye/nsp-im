"""
W5-Day3 跨端截图验证（修正版）
- Local HTTP server (file:// 不支持 fetch)
- PC 1920 / Tablet 768 / Mobile 375
- 公网 URL 验证
"""
import asyncio, os, json, time, threading, http.server, socketserver
from playwright.async_api import async_playwright

HTML_DEPLOY_DIR = r"D:\nsp-im-vercel"
HTML_FILE = "index.html"
OUT = r"D:\hermes-dev-team\nsp-im\screenshots"
os.makedirs(OUT, exist_ok=True)
PWD = "nsp2026"
PUBLIC_URL = "https://liuwang-jiankong-d2eatyj479b1861-1471069936.tcloudbaseapp.com/liuwang-jiankong/"
LOCAL_PORT = 8829


def start_server():
    """启动本地 HTTP 服务器（file:// 不支持 fetch）"""
    os.chdir(HTML_DEPLOY_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    # 强制注入 charset
    handler.extensions_map.update({".html": "text/html; charset=utf-8"})
    httpd = socketserver.TCPServer(("127.0.0.1", LOCAL_PORT), handler)
    httpd.serve_forever()


# 启动后台 HTTP server
_server_thread = threading.Thread(target=start_server, daemon=True)
_server_thread.start()
time.sleep(1)
print(f"[HTTP] 本地服务器 http://127.0.0.1:{LOCAL_PORT} 已启动")


async def shoot(browser, w, h, fname, label, url, ua=None, is_mobile=False):
    """通用截图"""
    state = {"pwd_passed": False, "body_visible": False, "grid_exists": False, "cells_count": 0}
    ctx = await browser.new_context(
        viewport={"width": w, "height": h},
        device_scale_factor=2 if is_mobile else 1,
        has_touch=is_mobile,
        is_mobile=is_mobile,
        user_agent=ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
    page = await ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(f"PAGEERR: {e}"))
    page.on("console", lambda m: errs.append(f"[{m.type}] {m.text}") if m.type == "error" else None)

    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        status = resp.status if resp else "no-resp"
        await page.wait_for_timeout(1500)
        print(f"  [{label}] HTTP {status}")

        # 输密码
        try:
            await page.fill('#pwdInput', PWD)
            await page.click('.pwd-box button')
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"  ! pwd step: {e}")

        # 验证
        state = await page.evaluate("""() => {
          const tabs = document.querySelectorAll('.tab');
          const btabs = document.querySelectorAll('.btab');
          const grid = document.querySelector('#matrix-svg, .matrix-svg, .cm-grid, .coupling-grid, #couplingGrid, .matrix-grid, .coupling-matrix, #matrixGrid');
          const cells = document.querySelectorAll('rect.matrix-cell, .cm-cell, .matrix-cell, [data-cell], .cell');
          const pwdPanel = document.querySelector('.pwd-overlay, #pwdPanel');
          const pwdHidden = pwdPanel ? getComputedStyle(pwdPanel).display === 'none' : true;
          return {
            tabs_count: tabs.length,
            btabs_count: btabs.length,
            grid_exists: !!grid,
            cells_count: cells.length,
            pwd_passed: pwdHidden,
            body_visible: document.body.offsetHeight > 100,
            doc_title: document.title.slice(0, 50)
          };
        }""")
        print(f"  [{label}] STATE: {json.dumps(state, ensure_ascii=False)}")

        # 主视图 (Tab1 默认)
        out1 = os.path.join(OUT, fname)
        await page.screenshot(path=out1, full_page=False)
        print(f"  ✓ {out1}")

        # 切到 Tab2（mobile 用 .btab, desktop 用 .tab）
        tab_sel = '.btab[data-btab="2"]' if is_mobile else '.tab[data-tab="2"]'
        try:
            await page.click(tab_sel, timeout=5000)
            await page.wait_for_timeout(2500)
            out2 = os.path.join(OUT, fname.replace(".png", "_tab2.png"))
            await page.screenshot(path=out2, full_page=False)
            print(f"  ✓ {out2}")

            # 弹框测试：找 grid↔compute 单元（最高分 8.71）触发 click
            # 用 JS dispatchEvent 绕过 SVG 文本层拦截
            clicked = await page.evaluate("""() => {
              const rect = document.querySelector('rect.matrix-cell[data-net-a="grid"][data-net-b="compute"]');
              if (!rect) return {ok: false, reason: 'cell not found'};
              rect.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
              return {ok: true, score: rect.parentElement ? 'in_g' : 'orphan'};
            }""")
            print(f"  [{label}] CLICK: {clicked}")
            await page.wait_for_timeout(1500)
            modal_state = await page.evaluate("""() => {
              const m = document.getElementById('coupling-modal');
              if (!m) return {exists: false};
              const r = m.getBoundingClientRect();
              const vis = getComputedStyle(m).display !== 'none' && r.width > 0 && r.height > 0;
              const inner = m.firstElementChild;
              const innerText = inner ? inner.innerText.slice(0, 100) : '';
              return {exists: true, w: r.width, h: r.height, visible: vis, display: getComputedStyle(m).display, inner_preview: innerText};
            }""")
            print(f"  [{label}] MODAL: {json.dumps(modal_state, ensure_ascii=False)}")
            out3 = os.path.join(OUT, fname.replace(".png", "_tab2_modal.png"))
            await page.screenshot(path=out3, full_page=False)
            print(f"  ✓ {out3}")
        except Exception as e:
            print(f"  ! tab2 step: {e}")

        if errs:
            print(f"  ERRORS ({len(errs)}): {errs[:3]}")
    except Exception as e:
        print(f"  [{label}] FAIL: {e}")

    await ctx.close()
    return state, errs


async def main():
    local_url = f"http://127.0.0.1:{LOCAL_PORT}/{HTML_FILE}"
    print(f"本地 URL: {local_url}")
    summary = {"local": {}, "public": {}}

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)

        # ===== 本地 3 端 =====
        print("\n=== 本地 d5.html (HTTP) 三端截图 ===")
        s_pc, e_pc = await shoot(b, 1920, 1080, "w5_pc_1920.png", "PC 1920", local_url)
        summary["local"]["pc_1920"] = {
            "ok": s_pc["pwd_passed"] and s_pc["body_visible"] and s_pc["grid_exists"] and s_pc["cells_count"] >= 30,
            "state": s_pc, "errors": len(e_pc)
        }
        s_tb, e_tb = await shoot(b, 768, 1024, "w5_tablet_768.png", "TABLET 768", local_url)
        summary["local"]["tablet_768"] = {
            "ok": s_tb["pwd_passed"] and s_tb["body_visible"] and s_tb["grid_exists"] and s_tb["cells_count"] >= 30,
            "state": s_tb, "errors": len(e_tb)
        }
        s_mb, e_mb = await shoot(b, 375, 812, "w5_mobile_375.png", "MOBILE 375", local_url, is_mobile=True)
        summary["local"]["mobile_375"] = {
            "ok": s_mb["pwd_passed"] and s_mb["body_visible"] and s_mb["grid_exists"] and s_mb["cells_count"] >= 30,
            "state": s_mb, "errors": len(e_mb)
        }

        # ===== 公网 PC =====
        print("\n=== 公网 URL (PC) 验证 ===")
        s_pub, e_pub = await shoot(b, 1280, 800, "w5_public_1280.png", "PUBLIC 1280", PUBLIC_URL)
        summary["public"]["pc_1280"] = {
            "ok": s_pub["pwd_passed"] and s_pub["body_visible"],
            "state": s_pub, "errors": len(e_pub)
        }

        await b.close()

    print("\n===== 跨端验证汇总 =====")
    for k, v in summary["local"].items():
        print(f"  {k.upper()}: {'PASS' if v['ok'] else 'FAIL'} (grid={v['state']['grid_exists']}, cells={v['state']['cells_count']})")
    print(f"  PUBLIC: {'PASS' if summary['public']['pc_1280']['ok'] else 'FAIL'} (grid={summary['public']['pc_1280']['state']['grid_exists']}, cells={summary['public']['pc_1280']['state']['cells_count']})")

    # 写汇总 JSON
    with open(os.path.join(OUT, "w5_d3_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n✓ 汇总: {os.path.join(OUT, 'w5_d3_summary.json')}")


asyncio.run(main())
