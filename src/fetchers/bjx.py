"""
NSP-IM 北极星电力 (BJX) 政策/资讯抓取器 v0.1
源: https://www.bjx.com.cn/

W2-D3:
  因反爬 + 需 JS 渲染, fetch_raw() 直接返回手写 demo (与 nea.py 同套路);
  真抓版将复用 aiohttp + BeautifulSoup + JS 渲染 (playwright 或 selenium).
  BJX 是行业头部媒体, 内容覆盖电力/储能/新能源/光伏/碳市场等, 6 网全场景广,
  是 NSP-IM 项目 5 网协同最具代表性的"行业实操信号"源.

设计要点 (与 ndrc.py / nea.py 同构):
  - 继承 BaseFetcher, 自动获得 fetch_with_retry / save() / health 探针
  - 标题 → scope 智能推断 (行业媒体关键词丰富, 覆盖 6 网全类型)
  - 稳定 id: P-BJX-YYYYMMDD-NNNN (基于 sha1(date|url|title))
  - 因 BJX 是"行业资讯"性质, priority 多数为 2 (媒体视角低于红头文)
  - doc_number 多数为空 (BJX 文章多为资讯/解读, 无文号)
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, date
from typing import Any, Dict, List

from .base import BaseFetcher


# BJX 行业媒体 demo 数据 (W2-D3 离线; 真抓落库后会被覆盖)
# 覆盖 5 网全类型: grid / water / compute / telecom / pipe / logi + monitor 兜底
_BJX_DEMO_RAW: List[Dict[str, Any]] = [
    {
        # 电网 (grid) — 新型电力系统 / 储能 / 调度
        "title": "《新型电力系统建设加速, 储能装机规模将破 8000 万千瓦》",
        "url": "https://www.bjx.com.cn/news/2024-0418/news_20240418_2001.html",
        "date": "2024-04-18",
        "doc_number": None,
    },
    {
        # 算 (compute) — 数据中心 / 算电协同
        "title": "《数据中心算电协同新范式: 内蒙古枢纽节点绿电直供观察》",
        "url": "https://www.bjx.com.cn/news/2024-0510/news_20240510_2002.html",
        "date": "2024-05-10",
        "doc_number": None,
    },
    {
        # 水 (water) — 水电 / 抽水蓄能
        "title": "《抽水蓄能装机突破 5000 万千瓦, 新型电力系统压舱石地位强化》",
        "url": "https://www.bjx.com.cn/news/2024-0528/news_20240528_2003.html",
        "date": "2024-05-28",
        "doc_number": None,
    },
    {
        # 通 (telecom) — 5G+电力 / 虚拟电厂通信
        "title": "《虚拟电厂 5G 通信切片落地, 毫秒级调度响应成为可能》",
        "url": "https://www.bjx.com.cn/news/2024-0620/news_20240620_2004.html",
        "date": "2024-06-20",
        "doc_number": None,
    },
    {
        # 物 (logi) — 物流 / 充换电
        "title": "《重卡换电干线网络加速布局, 物流绿电走廊落地三城》",
        "url": "https://www.bjx.com.cn/news/2024-0715/news_20240715_2005.html",
        "date": "2024-07-15",
        "doc_number": None,
    },
    {
        # 管 (pipe) — 油气管道 (与能源局/发改委同领域, BJX 偶有解读)
        "title": "《西气东输四线投产, 油气长输管道与新能源融合调度观察》",
        "url": "https://www.bjx.com.cn/news/2024-0810/news_20240810_2006.html",
        "date": "2024-08-10",
        "doc_number": None,
    },
    {
        # 储 (BESS) 兜底 grid — 储能 PCS / 容量电价
        "title": "《储能容量电价机制落地, 独立储能商业模式破局》",
        "url": "https://www.bjx.com.cn/news/2024-0828/news_20240828_2007.html",
        "date": "2024-08-28",
        "doc_number": None,
    },
    {
        # 兜底 (monitor) — 碳市场 / 行业数据, 不命中 5 网
        "title": "《全国碳市场扩容: 钢铁/铝/水泥三大行业纳入倒计时》",
        "url": "https://www.bjx.com.cn/news/2024-0912/news_20240912_2008.html",
        "date": "2024-09-12",
        "doc_number": None,
    },
]


class BjxFetcher(BaseFetcher):
    """北极星电力 (BJX) fetcher.

    行业头部媒体, 资讯 + 解读 + 评论, 与发改委/能源局红头文互补:
      - 政府源 (NDRC/NEA): 红头文 / 监管通知, 法律约束力强
      - BJX (媒体): 行业动态 / 市场观察 / 案例解读, 实操信号丰富

    设计要点:
      - 继承 BaseFetcher, 自动获得 fetch_with_retry / save() / health 探针
      - 标题 → scope 智能推断 (覆盖 6 网全类型, monitor 兜底)
      - 稳定 id: P-BJX-YYYYMMDD-NNNN (基于 sha1(date|url|title))
      - BJX 文章无文号 (doc_number=None), priority 默认 2 (媒体视角)
    """

    # 标题关键词 → 适用范围 (能/水/算/通/管/物/monitor)
    # BJX 媒体关键词比 NEA 更杂 (含市场/案例/解读), 但仍按"主题域"对齐 5 网
    _SCOPE_KEYWORDS = {
        "grid": (
            "电力", "电网", "储能", "新能源", "光伏", "风电",
            "消纳", "调度", "电力市场", "电改", "虚拟电厂",
            "BESS", "PCS", "容量电价", "新型电力系统",
        ),
        "water": ("水电", "抽水蓄能", "水利", "供水"),
        "compute": ("算", "数据", "数据中心", "算电协同", "算力枢纽", "PUE"),
        "telecom": ("通信", "5G", "6G", "网络", "通信切片"),
        "pipe": ("管道", "管网", "燃气", "油气", "长输", "西气东输"),
        "logi": ("运输", "物流", "多式联运", "铁路", "公路", "换电", "重卡", "干线"),
    }

    def __init__(self):
        super().__init__(
            name="北极星",
            source_url="https://www.bjx.com.cn/",
        )

    # ---------- 抓取 (W2-D3 demo 数据; 真抓留待后续) ----------
    async def fetch_raw(self) -> List[Dict[str, Any]]:
        """返回 BJX 原始条目列表.

        W2-D3 阶段: 返回手写 demo (8 条覆盖 5 网 + monitor 兜底);
        真实抓取版本会调 aiohttp + bs4 + JS 渲染, 解析 bjx.com.cn 列表结构.
        """
        # 真实抓取版 (留作参考, 当前 demo 模式直接返回):
        # import aiohttp
        # from bs4 import BeautifulSoup
        # async with aiohttp.ClientSession() as session:
        #     async with session.get(self.source_url, timeout=self.timeout) as resp:
        #         html = await resp.text()
        # soup = BeautifulSoup(html, "html.parser")
        # items = []
        # for li in soup.select("ul.news-list li")[:20]:
        #     a = li.find("a")
        #     if not a:
        #         continue
        #     items.append({
        #         "title": a.get_text(strip=True),
        #         "url": a.get("href", ""),
        #         "date": li.find("span.time").get_text(strip=True) if li.find("span.time") else "",
        #     })
        # return items
        return [dict(item) for item in _BJX_DEMO_RAW]

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
        """P-BJX-YYYYMMDD-NNNN; sha1(date|url|title) → 4 位十进制序号."""
        digest = hashlib.sha1(f"{publish_iso}|{url}|{title}".encode("utf-8")).hexdigest()
        seq = int(digest[:8], 16) % 10000
        date_seg = publish_iso.replace("-", "")
        return f"P-BJX-{date_seg}-{seq:04d}"

    # ---------- 工具: scope 推断 ----------
    @classmethod
    def _guess_scope(cls, title: str) -> List[str]:
        """标题关键字 → 适用范围; 兜底含 monitor (按 schema 语义对齐 NDRC/NEA)."""
        scopes = {"monitor"}
        for scope, kws in cls._SCOPE_KEYWORDS.items():
            if any(kw in title for kw in kws):
                scopes.add(scope)
        return sorted(scopes)

    # ---------- 解析 ----------
    def parse(self, raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """BJX 文章无文号 (doc_number=None); priority=2 (媒体视角低于红头文)."""
        policies: List[Dict[str, Any]] = []
        now_iso = datetime.utcnow().isoformat() + "Z"
        for item in raw:
            title = item.get("title", "")
            url = item.get("url", "")
            publish_iso = self._normalize_date(item.get("date", ""))
            policies.append({
                "id": self._stable_id(publish_iso, title, url),
                "title": title,
                "department": "北极星电力",  # 媒体署名, 区别于政府源
                "doc_number": item.get("doc_number"),  # 媒体文章多为 None
                "publish_date": publish_iso,
                "effective_date": publish_iso,
                "category": "monitor",  # 媒体源多为"动态/解读", 归 monitor 类
                "scope": self._guess_scope(title),
                "priority": 2,  # 媒体视角低于 NEA 红头文 (priority=1)
                "summary": title[:100],
                "key_points": [],
                "source_url": url,
                "captured_at": now_iso,
                "captured_by": "bjx-fetcher-v0.1",
                "tags": [],
                "review_status": "pending",
            })
        return policies


__all__ = ["BjxFetcher"]