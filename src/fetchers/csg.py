"""
NSP-IM 南方电网 (CSG) 政策/公告抓取器 v0.1
源: https://www.csg.cn/

W2-D3:
  因反爬 + JS 渲染, fetch_raw() 直接返回手写 demo (与 nea.py 同套路);
  真抓版将复用 aiohttp + BeautifulSoup + JS 渲染.
  南方电网是央企, 公告/采购/招标多; 与国网 (sgcc) 形成 5 网电力行业"实施层"
  的双信号源, 是 NSP-IM 项目"电网/储能/算电协同"落地的关键信号.

设计要点 (与 ndrc.py / nea.py / bjx.py 同构):
  - 继承 BaseFetcher, 自动获得 fetch_with_retry / save() / health 探针
  - 标题 → scope 智能推断 (聚焦南方电网主业: 电网/储能/算电协同/绿电)
  - 稳定 id: P-CSG-YYYYMMDD-NNNN (基于 sha1(date|url|title))
  - 央企公告多为南方区域电网调度/储能/招标类, priority 多数为 1
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, date, timezone
from typing import Any, Dict, List

from .base import BaseFetcher


# CSG 南方电网 demo 数据 (W2-D3 离线; 真抓落库后会被覆盖)
# 覆盖 5 网 (重点: grid / compute; 兼 telecom 智能电网 + pipe 西电东送)
_CSG_DEMO_RAW: List[Dict[str, Any]] = [
    {
        # 电网 (grid) — 储能/虚拟电厂
        "title": "《南方区域虚拟电厂接入调度运行管理规定(试行)》",
        "url": "https://www.csg.cn/notice/2024-0422/notice_20240422_3001.html",
        "date": "2024-04-22",
        "doc_number": "南方电网调〔2024〕12号",
    },
    {
        # 算 (compute) — 数据中心绿电直供
        "title": "《南方电网数据中心绿电直供试点方案: 粤港澳大湾区枢纽节点》",
        "url": "https://www.csg.cn/notice/2024-0506/notice_20240506_3002.html",
        "date": "2024-05-06",
        "doc_number": "南方电网市场〔2024〕18号",
    },
    {
        # 通 (telecom) — 智能电网通信
        "title": "《南方电网 5G 专网覆盖 5 省区, 调度自动化通信升级》",
        "url": "https://www.csg.cn/notice/2024-0612/notice_20240612_3003.html",
        "date": "2024-06-12",
        "doc_number": "南方电网信通〔2024〕25号",
    },
    {
        # 电网 + 储能 (BESS)
        "title": "《南方区域新型储能并网调度运行实施细则(试行)》",
        "url": "https://www.csg.cn/notice/2024-0725/notice_20240725_3004.html",
        "date": "2024-07-25",
        "doc_number": "南方电网调〔2024〕33号",
    },
    {
        # 管 (pipe) — 西电东送主网架
        "title": "《南方电网西电东送主网架扩建工程招标公告(云广直流改造)》",
        "url": "https://www.csg.cn/bidding/2024-0808/bidding_20240808_3005.html",
        "date": "2024-08-08",
        "doc_number": "南方电网招标〔2024〕41号",
    },
    {
        # 水 (water) — 抽水蓄能
        "title": "《南方电网抽水蓄能装机规划 2030 年达 4000 万千瓦》",
        "url": "https://www.csg.cn/notice/2024-0905/notice_20240905_3006.html",
        "date": "2024-09-05",
        "doc_number": "南方电网规划〔2024〕52号",
    },
]


class CsgFetcher(BaseFetcher):
    """南方电网 (CSG) fetcher.

    央企公告 + 招标采购双信号源, 与政府源 (NDRC/NEA) 互补, 形成
    "政策方向 → 行业实操 → 招标采购" 的纵向证据链.

    设计要点:
      - 继承 BaseFetcher, 自动获得 fetch_with_retry / save() / health 探针
      - 标题 → scope 智能推断 (聚焦南方电网主业, monitor 兜底)
      - 稳定 id: P-CSG-YYYYMMDD-NNNN (基于 sha1(date|url|title))
      - 央企文号格式: 南方电网XX〔YYYY〕NN号; priority=1 (执行约束力)
    """

    # 标题关键词 → 适用范围 (能/水/算/通/管/物/monitor)
    _SCOPE_KEYWORDS = {
        "grid": (
            "电力", "电网", "储能", "新能源", "光伏", "风电",
            "消纳", "调度", "电力市场", "电改", "虚拟电厂",
            "并网", "调度运行", "BESS", "容量电价",
        ),
        "water": ("水电", "抽水蓄能", "水利"),
        "compute": ("算", "数据", "数据中心", "算电协同", "算力枢纽", "PUE", "绿电直供"),
        "telecom": ("通信", "5G", "6G", "专网", "调度自动化"),
        "pipe": ("管道", "输电", "西电东送", "主网架", "直流"),
        "logi": ("运输", "物流", "招标", "采购", "重卡"),
    }

    def __init__(self):
        super().__init__(
            name="南网",
            source_url="https://www.csg.cn/",
        )

    # ---------- 抓取 (W2-D3 demo 数据; 真抓留待后续) ----------
    async def fetch_raw(self) -> List[Dict[str, Any]]:
        """返回 CSG 原始条目列表.

        W2-D3 阶段: 返回手写 demo (5 条覆盖 4 网 + monitor 兜底);
        真实抓取版本会调 aiohttp + bs4 + JS 渲染, 解析 csg.cn 列表结构.
        """
        # 真实抓取版 (留作参考, 当前 demo 模式直接返回):
        # import aiohttp
        # from bs4 import BeautifulSoup
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(self.source_url, timeout=self.timeout) as resp:
        #         html = await resp.text()
        # soup = BeautifulSoup(html, "html.parser")
        # items = []
        # for li in soup.select("ul.notice-list li")[:20]:
        #     a = li.find("a")
        #     if not a:
        #         continue
        #     items.append({
        #         "title": a.get_text(strip=True),
        #         "url": a.get("href", ""),
        #         "date": li.find("span.date").get_text(strip=True) if li.find("span.date") else "",
        #         "doc_number": li.find("span.doc-no").get_text(strip=True) if li.find("span.doc-no") else None,
        #     })
        # return items
        return [dict(item) for item in _CSG_DEMO_RAW]

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
        """P-CSG-YYYYMMDD-NNNN; sha1(date|url|title) → 4 位十进制序号."""
        digest = hashlib.sha1(f"{publish_iso}|{url}|{title}".encode("utf-8")).hexdigest()
        seq = int(digest[:8], 16) % 10000
        date_seg = publish_iso.replace("-", "")
        return f"P-CSG-{date_seg}-{seq:04d}"

    # ---------- 工具: scope 推断 ----------
    @classmethod
    def _guess_scope(cls, title: str) -> List[str]:
        """标题关键字 → 适用范围; 兜底含 monitor (按 schema 语义对齐 NDRC/NEA/BJX)."""
        scopes = {"monitor"}
        for scope, kws in cls._SCOPE_KEYWORDS.items():
            if any(kw in title for kw in kws):
                scopes.add(scope)
        return sorted(scopes)

    # ---------- 解析 ----------
    def parse(self, raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """CSG 央企公告 priority=1 (执行约束力, 与 NEA 红头文对齐)."""
        policies: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for item in raw:
            title = item.get("title", "")
            url = item.get("url", "")
            publish_iso = self._normalize_date(item.get("date", ""))
            policies.append({
                "id": self._stable_id(publish_iso, title, url),
                "title": title,
                "department": "南方电网公司",
                "doc_number": item.get("doc_number"),  # 央企文号
                "publish_date": publish_iso,
                "effective_date": publish_iso,
                "category": "policy",
                "scope": self._guess_scope(title),
                "priority": 1,  # 央企执行约束力
                "summary": title[:100],
                "key_points": [],
                "source_url": url,
                "captured_at": now_iso,
                "captured_by": "csg-fetcher-v0.1",
                "tags": [],
                "review_status": "pending",
            })
        return policies


__all__ = ["CsgFetcher"]