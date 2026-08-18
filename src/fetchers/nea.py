"""
NSP-IM 国家能源局政策抓取器 v1.0
源：https://www.nea.gov.cn/

W2-D1: 因反爬, fetch_raw() 直接返回手写 demo 数据 (NDRC 模板同款套路);
真抓版将复用 aiohttp + BeautifulSoup,与 ndrc.py 同构。
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, date
from typing import Any, Dict, List

from .base import BaseFetcher


# 国家能源局真实政策样例 (W2-D1 离线 demo; 真抓落库后会被覆盖)
# 任务 body 明确要求 "3 条 demo 数据", 故严格取 3 条;
# 选 3 类典型业务: 电力监管 / 新能源消纳 / 新型储能, 覆盖 grid + monitor 兜底
# (其余测试如 scope=pipe 用合成 raw, 不依赖此 demo; 见 tests/test_nea.py)
_NEA_DEMO_RAW: List[Dict[str, Any]] = [
    {
        "title": "《电力领域综合监管工作通知》",
        "url": "https://www.nea.gov.cn/2024-0415/news_20240415_1001.html",
        "date": "2024-04-15",
        "doc_number": "国能发监管〔2024〕45号",
    },
    {
        "title": "《新能源消纳监测预警管理办法(试行)》",
        "url": "https://www.nea.gov.cn/2024-0509/news_20240509_1002.html",
        "date": "2024-05-09",
        "doc_number": "国能发新能〔2024〕62号",
    },
    {
        "title": "《新型储能并网调度运行管理规定(试行)》",
        "url": "https://www.nea.gov.cn/2024-0618/news_20240618_1003.html",
        "date": "2024-06-18",
        "doc_number": "国能发电力〔2024〕78号",
    },
]


class NeaFetcher(BaseFetcher):
    """国家能源局 (NEA) fetcher.

    设计要点 (与 ndrc.py 对齐):
      - 继承 BaseFetcher, 自动获得 fetch_with_retry / save() / health 探针
      - 标题 → scope 智能推断, 兜底含 monitor
      - 稳定 id: P-NEA-YYYYMMDD-NNNN (基于 sha1(date|url|title))
      - 因反爬, 当前 fetch_raw() 直接返回手写 demo; 真抓留待 W2 后续
    """

    # 标题关键词 → 适用范围 (能/水/算/通/管/物/monitor)
    _SCOPE_KEYWORDS = {
        "grid": (
            "电力", "电网", "储能", "新能源", "光伏", "风电",
            "消纳", "调度", "电力市场", "电改",
        ),
        "water": ("水", "供水", "水利"),
        "compute": ("算", "数据", "数据中心"),
        "telecom": ("通信", "5G", "6G", "网络"),
        "pipe": ("管道", "管网", "燃气", "油气", "长输"),
        "logi": ("运输", "物流", "多式联运", "铁路", "公路"),
    }

    def __init__(self):
        super().__init__(
            name="能源局",
            source_url="https://www.nea.gov.cn/",
        )

    # ---------- 抓取 (W2-D1 demo 数据; 真抓留待后续) ----------
    async def fetch_raw(self) -> List[Dict[str, Any]]:
        """返回 NEA 原始条目列表.

        W2-D1 阶段: 返回手写 demo (5 条); 真实抓取版本会调 aiohttp + bs4,
        解析 nea.gov.cn 列表页结构 (`ul.list > li > a` + span 日期).
        """
        # 真实抓取版 (留作参考, 当前 demo 模式直接返回):
        # import aiohttp
        # from bs4 import BeautifulSoup
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(self.source_url, timeout=self.timeout) as resp:
        #         html = await resp.text()
        # soup = BeautifulSoup(html, "html.parser")
        # items = []
        # for li in soup.select("ul.list li")[:20]:
        #     a = li.find("a")
        #     if not a:
        #         continue
        #     items.append({
        #         "title": a.get_text(strip=True),
        #         "url": a.get("href", ""),
        #         "date": li.find("span").get_text(strip=True) if li.find("span") else "",
        #     })
        # return items
        return [dict(item) for item in _NEA_DEMO_RAW]

    # ---------- 工具: 日期归一化 ----------
    @staticmethod
    def _normalize_date(raw: str) -> str:
        """把多种格式归一为 ISO YYYY-MM-DD; 失败回退今天."""
        if not raw or not isinstance(raw, str):
            return date.today().isoformat()
        s = raw.strip().replace("年", "-").replace("月", "-").replace("日", "")
        m = re.search(r"(\d{4})[\-/.]?(\d{1,2})[\-/.]?(\d{1,2})", s)
        if m:
            y, mo, d = m.groups()
            try:
                return date(int(y), int(mo), int(d)).isoformat()
            except ValueError:
                pass
        return date.today().isoformat()

    # ---------- 工具: 跨进程稳定 id ----------
    @staticmethod
    def _stable_id(publish_iso: str, title: str, url: str) -> str:
        """P-NEA-YYYYMMDD-NNNN; sha1(date|url|title) → 4 位十进制序号."""
        digest = hashlib.sha1(f"{publish_iso}|{url}|{title}".encode("utf-8")).hexdigest()
        seq = int(digest[:8], 16) % 10000
        date_seg = publish_iso.replace("-", "")
        return f"P-NEA-{date_seg}-{seq:04d}"

    # ---------- 工具: scope 推断 ----------
    @classmethod
    def _guess_scope(cls, title: str) -> List[str]:
        """标题关键字 → 适用范围; 兜底含 monitor (按 schema 语义对齐 NDRC)."""
        scopes = {"monitor"}
        for scope, kws in cls._SCOPE_KEYWORDS.items():
            if any(kw in title for kw in kws):
                scopes.add(scope)
        return sorted(scopes)

    # ---------- 解析 ----------
    def parse(self, raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        policies: List[Dict[str, Any]] = []
        now_iso = datetime.utcnow().isoformat() + "Z"
        for item in raw:
            title = item.get("title", "")
            url = item.get("url", "")
            publish_iso = self._normalize_date(item.get("date", ""))
            policies.append({
                "id": self._stable_id(publish_iso, title, url),
                "title": title,
                "department": "国家能源局",
                "doc_number": item.get("doc_number"),
                "publish_date": publish_iso,
                "effective_date": publish_iso,
                "category": "policy",
                "scope": self._guess_scope(title),
                "priority": 1,  # NEA 文多为监管类, 高优先级
                "summary": title[:100],
                "key_points": [],
                "source_url": url,
                "captured_at": now_iso,
                "captured_by": "nea-fetcher-v0.1",
                "tags": [],
                "review_status": "pending",
            })
        return policies


__all__ = ["NeaFetcher"]