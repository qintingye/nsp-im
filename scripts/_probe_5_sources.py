"""
W2-D5 临时连通性探针 - 仅用于探 5 站是否可达。
输出: stdout JSON 行, 每行一站 {"name", "url", "status", "http", "ms", "len", "title"}.
不修改任何持久文件。退出码: 0=全部跑完 (含失败), 1=脚本自身崩。
"""
import asyncio
import json
import sys
import time
from pathlib import Path

# 让 src.* 可导入 (跟 main_fetcher.py 同样的 setup)
_THIS = Path(__file__).resolve()
SRC_DIR = _THIS.parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

SITES = [
    ("发改委", "https://www.ndrc.gov.cn/xxgk/zcfb/tz/index.html"),
    ("能源局", "https://www.nea.gov.cn/"),
    ("南网",   "https://www.csg.cn/"),
    ("国网",   "https://www.sgcc.com.cn/"),
    ("北极星", "https://www.bjx.com.cn/"),
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


async def probe(name: str, url: str, timeout: float = 15.0) -> dict:
    import aiohttp
    t0 = time.monotonic()
    out = {"name": name, "url": url}
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": UA}) as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                                allow_redirects=True, ssl=False) as resp:
                raw = await resp.read()
                html = raw.decode("utf-8", errors="replace")
                out.update({
                    "status": "ok",
                    "http": resp.status,
                    "ms": int((time.monotonic() - t0) * 1000),
                    "len": len(html),
                })
                # 抓 <title>
                import re
                m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
                out["title"] = (m.group(1).strip()[:80] if m else "(no title)")
    except Exception as e:  # noqa: BLE001
        out.update({"status": "fail", "ms": int((time.monotonic() - t0) * 1000), "error": f"{type(e).__name__}: {e}"})
    return out


async def main():
    results = await asyncio.gather(*[probe(n, u) for n, u in SITES])
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    # 概要: N/N 可达
    n_ok = sum(1 for r in results if r["status"] == "ok")
    print(f"--- summary: {n_ok}/{len(results)} reachable ---", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())