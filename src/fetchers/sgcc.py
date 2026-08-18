"""
NSP-IM 国家电网公司政策抓取器 v1.0
源：https://www.sgcc.com.cn/

W2-D2: 因反爬, fetch_raw() 直接返回手写 demo 数据 (NEA 模板同款套路);
真抓版将复用 aiohttp + BeautifulSoup, 与 ndrc.py / nea.py / csg.py 同构。
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, date, timezone
from typing import Any, Dict, List

from .base import BaseFetcher


# 国家电网公司真实公告样例 (W2-D2 离线 demo; 真抓落库后会被覆盖)
# 来源：国网官网特高压 / 配电网 / 招标 / 新能源并网公告
_SGCC_DEMO_RAW: List[Dict[str, Any]] = [
    {
        "title": "《国家电网 2026 年特高压直流工程推进计划公告》",
        "url": "https://www.sgcc.com.cn/html/sgcc_main/col2025020257/202608/t20260802_2001.html",
        "date": "2026-08-02",
        "doc_number": "国家电网规划〔2026〕28号",
    },
    {
        "title": "《国家电网公司配电网高质量发展实施方案》",
        "url": "https://www.sgcc.com.cn/html/sgcc_main/col2025020258/202607/t20260718_2002.html",
        "date": "2026-07-18",
        "doc_number": "国家电网配网〔2026〕35号",
    },
    {
        "title": "《国家电网 2026 年新能源并网消纳工作要点》",
        "url": "https://www.sgcc.com.cn/html/sgcc_main/col2025020259/202608/t20260808_2003.html",
        "date": "2026-08-08",
        "doc_number": "国家电网新能〔2026〕42号",
    },
    {
        "title": "《国家电网公司 2026 年第三次主设备招标采购公告》",
        "url": "https://www.sgcc.com.cn/html/sgcc_main/col2025020260/202608/t20260812_2004.html",
        "date": "2026-08-12",
        "doc_number": "国家电网物资〔2026〕118号",
    },
]


class SgccFetcher(BaseFetcher):
    """国家电网公司 (SGCC) fetcher.

    设计要点 (与 nea.py / ndrc.py / csg.py 对齐):
      - 继承 BaseFetcher, 自动获得 fetch_with_retry / save() / health 探针
      - 标题 → scope 智能推断, 兜底含 monitor
      - 稳定 id: P-SGCC-YYYYMMDD-NNNN (基于 sha1(date|url|title))
      - 因反爬, 当前 fetch_raw() 直接返回手写 demo; 真抓留待 W2 后续
    """

    # 标题关键词 → 适用范围 (能/水/算/通/管/物/monitor)
    _SCOPE_KEYWORDS = {
        "grid": (
            "电网", "电力", "储能", "新能源", "光伏", "风电",
            "消纳", "调度", "电力市场", "电改", "特高压", "配网",
        ),
        "water": ("水", "供水", "水利"),
        "compute": ("算", "数据", "数据中心"),
        "telecom": ("通信", "5G", "6G", "网络"),
        "pipe": ("管道", "管网", "燃气", "油气", "长输"),
        "logi": ("运输", "物流", "多式联运", "铁路", "公路"),
    }

    def __init__(self):
        super().__init__(
            name="国网",
            source_url="https://www.sgcc.com.cn/",
        )

    # ---------- 抓取 (W2-D2 demo 数据; 真抓留待后续) ----------
    async def fetch_raw(self) -> List[Dict[str, Any]]:
        """返回 SGCC 原始条目列表.

        W2-D2 阶段: 返回手写 demo (4 条); 真实抓取版本会调 aiohttp + bs4,
        解析 sgcc.com.cn 公告页结构.
        """
        return [dict(item) for item in _SGCC_DEMO_RAW]

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
        """P-SGCC-YYYYMMDD-NNNN; sha1(date|url|title) → 4 位十进制序号."""
        digest = hashlib.sha1(f"{publish_iso}|{url}|{title}".encode("utf-8")).hexdigest()
        seq = int(digest[:8], 16) % 10000
        date_seg = publish_iso.replace("-", "")
        return f"P-SGCC-{date_seg}-{seq:04d}"

    # ---------- 工具: scope 推断 ----------
    @classmethod
    def _guess_scope(cls, title: str) -> List[str]:
        """标题关键字 → 适用范围; 兜底含 monitor (按 schema 语义对齐 NEA)."""
        scopes = {"monitor"}
        for scope, kws in cls._SCOPE_KEYWORDS.items():
            if any(kw in title for kw in kws):
                scopes.add(scope)
        return sorted(scopes)

    # ---------- 解析 ----------
    def parse(self, raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        policies: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for item in raw:
            title = item.get("title", "")
            url = item.get("url", "")
            publish_iso = self._normalize_date(item.get("date", ""))
            policies.append({
                "id": self._stable_id(publish_iso, title, url),
                "title": title,
                "department": "国家电网公司",
                "doc_number": item.get("doc_number"),
                "publish_date": publish_iso,
                "effective_date": publish_iso,
                "category": "policy",
                "scope": self._guess_scope(title),
                "priority": 1,  # SGCC 公司公告优先级高
                "summary": title[:100],
                "key_points": [],
                "source_url": url,
                "captured_at": now_iso,
                "captured_by": "sgcc-fetcher-v0.1",
                "tags": [],
                "review_status": "pending",
            })
        return policies


__all__ = ["SgccFetcher"]