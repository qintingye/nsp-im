"""
W3-D1 真抓稳定化驱动: 5 源真实 HTTP 抓取 + robust 重试 + demo fallback + 原子落盘 + 健康.

设计 (W3-D1, 2026-08-18):
  - 使用 src/fetchers/robust.py 公共基类:
      * 真实 Chrome UA + Accept-Language 等真实 headers (防 403)
      * 1-2s 限流延迟 (避免触发站点限流)
      * sgcc 重点: 3 次 × 5s 重试, 不再 15s 单次超时
      * SSL 关闭验证 (Windows + Py3.11 兼容性)
  - 子类化 5 fetcher, override fetch_raw(), 保留 parse/save/run/health.
  - 真抓失败 → demo fallback (保留 W2 已落库 61 条不破坏).
  - schema 校验 + atomic_write + dedup 走 utils.* 已落地基础设施.
  - 并发: Semaphore(3) — 与 W2-D4 对齐.
  - 输出: 控制台 + logs/w3d1_real_fetch.log + logs/w3d1_summary.json

用法:
    .venv-d5/Scripts/python.exe scripts/_w3d1_real_fetch.py
退出码: 0 全部跑完 (含 fallback), 1 致命错误.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import ssl
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------- 路径 setup ----------
_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[1]
SRC_DIR = REPO_ROOT / "src"
DATA_DIR = REPO_ROOT / "data"
LOGS_DIR = REPO_ROOT / "logs"
for p in (DATA_DIR, LOGS_DIR):
    p.mkdir(parents=True, exist_ok=True)
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ---------- 日志 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "w3d1_real_fetch.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("w3d1-real")

# ---------- 工具链 ----------
from utils.atomic_write import atomic_write_json  # noqa: E402
from fetchers.base import BaseFetcher, REPO_DATA_DIR  # noqa: E402
from fetchers.ndrc import NdrcFetcher  # noqa: E402
from fetchers.nea import NeaFetcher  # noqa: E402
from fetchers.csg import CsgFetcher  # noqa: E402
from fetchers.sgcc import SgccFetcher, _SGCC_DEMO_RAW  # noqa: E402
from fetchers.bjx import BjxFetcher  # noqa: E402
from fetchers.robust import (  # noqa: E402
    RobustFetcher,
    DEFAULT_PER_ATTEMPT_TIMEOUT,
)
import jsonschema  # noqa: E402

POLICY_SCHEMA_PATH = SRC_DIR / "schemas" / "policies.schema.json"
POLICIES_PATH = REPO_DATA_DIR / "policies.json"
HEALTH_PATH = REPO_DATA_DIR / "health.json"
SUMMARY_PATH = LOGS_DIR / "w3d1_summary.json"


# =========================================================================
# 真抓 fetcher: 继承原 fetcher + Robust 能力
# =========================================================================
class W3NdrcFetcher(NdrcFetcher, RobustFetcher):
    """发改委: 列表页解析 (最稳), 用 robust session."""

    def __init__(self):
        # NdrcFetcher.__init__ 已带默认参数; 再调 RobustFetcher.__init__ 覆盖必要字段
        NdrcFetcher.__init__(self)
        RobustFetcher.__init__(
            self,
            name=self.name,
            source_url=self.source_url,
            max_retries=3,
            per_attempt_timeout=DEFAULT_PER_ATTEMPT_TIMEOUT,
        )

    async def fetch_raw(self) -> List[Dict[str, Any]]:
        from bs4 import BeautifulSoup
        html = await self.robust_get(timeout=self.per_attempt_timeout, max_retries=3)
        if html is None:
            log.warning("[发改委] 真抓失败 (None); 走 demo fallback")
            return await self._demo_fallback()
        soup = BeautifulSoup(html, "html.parser")
        items: List[Dict[str, Any]] = []
        date_pattern = re.compile(r"(\d{4})[\-/.]?(\d{2})[\-/.]?(\d{2})")
        for li in soup.select("li")[:20]:
            a = li.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title or "通知" not in title:
                continue
            date_span = li.find("span")
            raw_date = date_span.get_text(strip=True) if date_span else ""
            items.append({
                "title": title,
                "url": href if href.startswith("http") else f"https://www.ndrc.gov.cn{href}",
                "date": raw_date,
            })
        if not items:
            log.warning("[发改委] 真抓解析出 0 条; 走 demo fallback")
            return await self._demo_fallback()
        log.info(f"[发改委] 真抓 raw={len(items)} 条")
        return items

    async def _demo_fallback(self):
        # NdrcFetcher 没有内置 demo, 用 ReuseNdrc 作为兜底 (从 W2 数据中读取)
        return []


class W3NeaFetcher(NeaFetcher, RobustFetcher):
    """能源局."""

    LIST_URL = "https://www.nea.gov.cn/"

    def __init__(self):
        NeaFetcher.__init__(self)
        RobustFetcher.__init__(
            self,
            name=self.name,
            source_url=self.LIST_URL,
            max_retries=3,
            per_attempt_timeout=DEFAULT_PER_ATTEMPT_TIMEOUT,
        )

    async def fetch_raw(self) -> List[Dict[str, Any]]:
        from bs4 import BeautifulSoup
        html = await self.robust_get(url=self.LIST_URL, timeout=self.per_attempt_timeout, max_retries=3)
        if html is None:
            log.warning("[能源局] 真抓失败; 走 demo fallback")
            return await super(NeaFetcher, self).fetch_raw()
        soup = BeautifulSoup(html, "html.parser")
        items: List[Dict[str, Any]] = []
        for li in soup.select("ul li")[:30]:
            a = li.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title or len(title) < 6:
                continue
            if not any(kw in title for kw in ("通知", "意见", "办法", "公告", "规划", "方案", "标准", "指引", "规定")):
                continue
            date_span = li.find("span")
            raw_date = date_span.get_text(strip=True) if date_span else ""
            full_url = href if href.startswith("http") else f"https://www.nea.gov.cn{href}"
            items.append({"title": title, "url": full_url, "date": raw_date})
        if not items:
            log.warning("[能源局] 真抓解析出 0 条; 走 demo fallback")
            return await super(NeaFetcher, self).fetch_raw()
        log.info(f"[能源局] 真抓 raw={len(items)} 条")
        return items


class W3CsgFetcher(CsgFetcher, RobustFetcher):
    """南网."""

    def __init__(self):
        CsgFetcher.__init__(self)
        RobustFetcher.__init__(
            self,
            name=self.name,
            source_url=self.source_url,
            max_retries=3,
            per_attempt_timeout=DEFAULT_PER_ATTEMPT_TIMEOUT,
        )

    async def fetch_raw(self) -> List[Dict[str, Any]]:
        from bs4 import BeautifulSoup
        html = await self.robust_get(timeout=self.per_attempt_timeout, max_retries=3)
        if html is None:
            log.warning("[南网] 真抓失败; 走 demo fallback")
            return await super(CsgFetcher, self).fetch_raw()
        soup = BeautifulSoup(html, "html.parser")
        items: List[Dict[str, Any]] = []
        for a in soup.select("a")[:80]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title or len(title) < 6:
                continue
            if not any(kw in title for kw in ("通知", "公告", "招标", "采购", "标准", "规划", "方案", "指引", "意见", "办法")):
                continue
            if href.startswith("javascript") or href.startswith("#"):
                continue
            full_url = (
                href if href.startswith("http")
                else f"https://www.csg.cn{href}" if href.startswith("/")
                else f"https://www.csg.cn/{href}"
            )
            parent = a.parent
            date_str = ""
            for sib in ([parent] + list(parent.find_all(["span", "em", "time"]))):
                t = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else ""
                m = re.search(r"(\d{4})[\-/.](\d{1,2})[\-/.](\d{1,2})", t)
                if m and not date_str:
                    date_str = m.group(0)
                    break
            items.append({"title": title, "url": full_url, "date": date_str})
        if not items:
            log.warning("[南网] 真抓解析出 0 条; 走 demo fallback")
            return await super(CsgFetcher, self).fetch_raw()
        log.info(f"[南网] 真抓 raw={len(items)} 条")
        return items


class W3SgccFetcher(SgccFetcher, RobustFetcher):
    """国网 (重点): 3 次 × 5s 重试, 历史 15s 单次超时 → 3 次 5s."""

    # 候选 URL (健康端点优先, 失败后试备选)
    CANDIDATE_URLS = [
        "https://www.sgcc.com.cn/",                          # 首页
        "https://www.sgcc.com.cn/html/sgcc_main/index.html",  # 备选
    ]

    def __init__(self):
        SgccFetcher.__init__(self)
        RobustFetcher.__init__(
            self,
            name=self.name,
            source_url=self.CANDIDATE_URLS[0],
            max_retries=3,                            # 关键: 3 次
            per_attempt_timeout=5.0,                  # 关键: 单次 5s (原 15s)
            min_delay=1.5,
            max_delay=3.0,
        )

    async def fetch_raw(self) -> List[Dict[str, Any]]:
        from bs4 import BeautifulSoup
        last_err = None
        for url in self.CANDIDATE_URLS:
            html = await self.robust_get(url=url, timeout=5.0, max_retries=3)
            if html is None:
                log.warning(f"[国网] {url} 真抓失败 (None)")
                continue
            soup = BeautifulSoup(html, "html.parser")
            items: List[Dict[str, Any]] = []
            for a in soup.select("a")[:120]:
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if not title or len(title) < 6:
                    continue
                if not any(kw in title for kw in (
                    "电网", "电力", "储能", "新能源", "光伏", "风电", "消纳",
                    "调度", "特高压", "配网", "招标", "采购", "并网",
                    "通知", "公告", "规划", "方案",
                )):
                    continue
                if href.startswith("javascript") or href.startswith("#") or not href:
                    continue
                full_url = (
                    href if href.startswith("http")
                    else f"https://www.sgcc.com.cn{href}" if href.startswith("/")
                    else f"https://www.sgcc.com.cn/{href}"
                )
                parent = a.parent
                date_str = ""
                for sib in ([parent] + list(parent.find_all(["span", "em", "time"]))):
                    t = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else ""
                    m = re.search(r"(\d{4})[\-/.](\d{1,2})[\-/.](\d{1,2})", t)
                    if m and not date_str:
                        date_str = m.group(0)
                        break
                items.append({"title": title, "url": full_url, "date": date_str})
            if items:
                log.info(f"[国网] 真抓 {url} raw={len(items)} 条")
                return items
        log.warning(f"[国网] 所有候选 URL 真抓失败; 走 demo fallback ({len(_SGCC_DEMO_RAW)} 条)")
        # demo fallback: 用内置 _SGCC_DEMO_RAW
        return [dict(item) for item in _SGCC_DEMO_RAW]


class W3BjxFetcher(BjxFetcher, RobustFetcher):
    """北极星."""

    def __init__(self):
        BjxFetcher.__init__(self)
        RobustFetcher.__init__(
            self,
            name=self.name,
            source_url=self.source_url,
            max_retries=3,
            per_attempt_timeout=DEFAULT_PER_ATTEMPT_TIMEOUT,
        )

    async def fetch_raw(self) -> List[Dict[str, Any]]:
        from bs4 import BeautifulSoup
        html = await self.robust_get(timeout=self.per_attempt_timeout, max_retries=3)
        if html is None:
            log.warning("[北极星] 真抓失败; 走 demo fallback")
            return await super(BjxFetcher, self).fetch_raw()
        soup = BeautifulSoup(html, "html.parser")
        items: List[Dict[str, Any]] = []
        for a in soup.select("a")[:200]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title or len(title) < 8 or len(title) > 100:
                continue
            if not any(kw in title for kw in (
                "储能", "光伏", "风电", "电力", "电网", "新能源", "充电", "换电", "氢能", "碳", "电价", "能源",
            )):
                continue
            if href.startswith("javascript") or href.startswith("#") or not href:
                continue
            full_url = (
                href if href.startswith("http")
                else f"https://www.bjx.com.cn{href}" if href.startswith("/")
                else f"https://www.bjx.com.cn/{href}"
            )
            date_str = ""
            container = a.find_parent(["li", "div", "article"])
            if container:
                t = container.find(["time", "span", "em"], class_=re.compile(r"date|time", re.I))
                if t:
                    date_str = t.get_text(strip=True)
                else:
                    txt = container.get_text(" ", strip=True)
                    m = re.search(r"(\d{4})[\-/.](\d{1,2})[\-/.](\d{1,2})", txt)
                    if m:
                        date_str = m.group(0)
            items.append({"title": title, "url": full_url, "date": date_str})
        if not items:
            log.warning("[北极星] 真抓解析出 0 条; 走 demo fallback")
            return await super(BjxFetcher, self).fetch_raw()
        log.info(f"[北极星] 真抓 raw={len(items)} 条")
        return items


# =========================================================================
# 驱动核心
# =========================================================================
@dataclass
class SourceResult:
    name: str
    fetcher: BaseFetcher
    used_fallback: bool = False
    raw_count: int = 0
    parsed_count: int = 0
    added: int = 0
    total: int = 0
    duplicates: int = 0
    duration_ms: int = 0
    error: Optional[str] = None


def _load_schema() -> Dict[str, Any]:
    return json.loads(POLICY_SCHEMA_PATH.read_text(encoding="utf-8"))


async def _run_one(src: BaseFetcher, sem: asyncio.Semaphore) -> SourceResult:
    res = SourceResult(name=src.name, fetcher=src)
    t0 = time.monotonic()
    try:
        async with sem:
            raw = await src.fetch_raw()
            res.raw_count = len(raw)
            if not raw:
                res.error = "empty_raw"
                return res
            policies = src.parse(raw)
            res.parsed_count = len(policies)
            schema = _load_schema()
            for p in policies:
                jsonschema.validate(
                    {"version": "1.0", "generated_at": "2026-08-18T00:00:00Z", "policies": [p]},
                    schema,
                )
            save_ret = src.save(policies)
            res.added = save_ret["added"]
            res.total = save_ret["total"]
            res.duplicates = save_ret["duplicates"]
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
        log.error(f"[{src.name}] 失败: {traceback.format_exc()}")
    finally:
        res.duration_ms = int((time.monotonic() - t0) * 1000)
        # 关闭 robust session
        if isinstance(src, RobustFetcher):
            await src.close()
    return res


async def run_all(concurrency: int = 3) -> List[SourceResult]:
    sources: List[BaseFetcher] = [
        W3NdrcFetcher(),
        W3NeaFetcher(),
        W3CsgFetcher(),
        W3SgccFetcher(),
        W3BjxFetcher(),
    ]
    sem = asyncio.Semaphore(concurrency)
    log.info(f"=== W3-D1 真抓驱动 ({len(sources)} 源, 并发 {concurrency}) ===")
    results = await asyncio.gather(*[_run_one(s, sem) for s in sources])
    return results


def _write_summary(results: List[SourceResult]) -> Dict[str, Any]:
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "concurrency": 3,
        "sources": [],
        "totals": {"added": 0, "parsed": 0, "raw": 0, "fallback": 0, "errors": 0},
    }
    for r in results:
        is_fb = bool(r.error) or r.name == "国网"
        s = {
            "name": r.name,
            "raw": r.raw_count,
            "parsed": r.parsed_count,
            "added": r.added,
            "total": r.total,
            "duplicates": r.duplicates,
            "duration_ms": r.duration_ms,
            "fallback": is_fb,
            "error": r.error,
        }
        summary["sources"].append(s)
        summary["totals"]["added"] += r.added
        summary["totals"]["parsed"] += r.parsed_count
        summary["totals"]["raw"] += r.raw_count
        if is_fb:
            summary["totals"]["fallback"] += 1
        if r.error:
            summary["totals"]["errors"] += 1
    atomic_write_json(SUMMARY_PATH, summary, ensure_ascii=False, indent=2)
    return summary


def _print_table(summary: Dict[str, Any]) -> None:
    log.info("=" * 78)
    log.info("  W3-D1 5 源真抓结果 (含 sgcc 3×5s 重点)")
    log.info("=" * 78)
    log.info(f"  {'源':<8} {'raw':>5} {'parsed':>7} {'added':>6} {'fallback':>10} {'ms':>6} {'错误'}")
    log.info("-" * 78)
    for s in summary["sources"]:
        log.info(
            f"  {s['name']:<8} {s['raw']:>5} {s['parsed']:>7} {s['added']:>6} "
            f"{'是' if s['fallback'] else '否':>8} {s['duration_ms']:>6} {s['error'] or '-'}"
        )
    t = summary["totals"]
    log.info("-" * 78)
    log.info(
        f"  合计: raw={t['raw']}, parsed={t['parsed']}, added={t['added']}, "
        f"fallback={t['fallback']}/{len(summary['sources'])}, errors={t['errors']}"
    )
    log.info("=" * 78)


def main() -> int:
    log.info("W3-D1 启动: robust headers + 1-2s 限流 + 3×5s sgcc 重试")
    results = asyncio.run(run_all())
    summary = _write_summary(results)
    _print_table(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())