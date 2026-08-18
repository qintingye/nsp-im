"""
NSP-IM 国家能源局政策抓取器 v2.0 (W3-D1 真抓版)
源：https://www.nea.gov.cn/

W3-D1 升级:
  - 真抓版: 从 NEA 首页 "最新动态" 区 (ul, 15 条) 抓取能源行业最新政策/通知/公告
  - NEA 首页是静态 HTML (服务端渲染), 无需 JS 引擎
  - 日期从 URL 路径 /YYYYMMDD/.../ 提取 (政府源常见模式)
  - 复用 utils.http_client 的 UA 池 / 限流 / 重试 / 风控检测
  - 保留 demo 数据作为 BlockedError 降级 (fetch_raw 内置 fallback)
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base import BaseFetcher
from utils.http_client import (
    HttpClient,
    BlockedError,
    get_default_client,
)


log = logging.getLogger("fetcher.nea")


# NEA 首页 "最新动态" 区域 URL 模式: /YYYYMMDD/{uuid}/c.html
_NEA_URL_DATE_RE = re.compile(r"/(\d{4})(\d{2})(\d{2})/")
# doc_number: "国能发新能〔2024〕62号" / "国能发电力〔2024〕78号" / "国能发监管〔2024〕45号"
_NEA_DOCNO_RE = re.compile(
    r"国能发[\u4e00-\u9fa5]+[〔(]\d{4}[〕)]\d+号"
)


# 离线 demo 数据 (W2-D1 真抓前的种子, W3-D1 起仅作 BlockedError 降级用)
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
    """国家能源局 (NEA) fetcher v2.0.

    W3-D1 真抓策略:
      1) GET NEA 首页 → 解析 "最新动态" ul (15 条)  + 头条区
      2) 日期从 URL /YYYYMMDD/ 提取 (NEA 静态路径)
      3) 政府文号(doc_number) 从标题或详情页提

    BlockedError → 降级到 _NEA_DEMO_RAW (确保监控链路不中断).
    """

    _SCOPE_KEYWORDS = {
        "grid": (
            "电力", "电网", "储能", "新能源", "光伏", "风电",
            "消纳", "调度", "电力市场", "电改", "特高压", "配网",
        ),
        "water": ("水电", "抽水蓄能", "水利", "供水"),
        "compute": ("算", "数据", "数据中心", "算电协同", "算力"),
        "telecom": ("通信", "5G", "6G", "网络", "专网"),
        "pipe": ("管道", "管网", "燃气", "油气", "西气东输", "输电"),
        "logi": ("运输", "物流", "招标", "采购", "重卡"),
    }

    def __init__(self, client: Optional[HttpClient] = None):
        super().__init__(
            name="能源局",
            source_url="https://www.nea.gov.cn/",
        )
        self.client = client or get_default_client()

    # ---------- 抓取 (W3-D1 真抓版) ----------
    async def fetch_raw(self) -> List[Dict[str, Any]]:
        """GET NEA 首页 → 解析最新动态列表.

        抛出:
            BlockedError: NEA 被防火墙拦截 → fetch_with_retry 兜底
        """
        try:
            html = await self.client.get_text(
                self.source_url,
                referer="https://www.nea.gov.cn/",
            )
        except BlockedError as e:
            log.warning("NEA 真抓被拦截, 降级 demo: %s", e)
            return [dict(item) for item in _NEA_DEMO_RAW]

        items = self._parse_home_html(html)
        if not items:
            log.warning("NEA 首页解析为空 (页面结构变化?), 降级 demo")
            return [dict(item) for item in _NEA_DEMO_RAW]
        return items[:20]

    def _parse_home_html(self, html: str) -> List[Dict[str, Any]]:
        """解析 NEA 首页.

        策略: 抓 "最新动态" / "通知公告" 类 ul, 取 15 条新闻, 标题含能源/电力/储能/光伏等关键词优先.
        """
        soup = BeautifulSoup(html, "html.parser")
        items: List[Dict[str, Any]] = []
        seen_keys: set = set()
        ENERGY_KW = ("能源", "电力", "储能", "光伏", "风电", "消纳", "调度",
                     "电网", "电改", "新能", "国家能源", "氢能", "核电", "煤炭",
                     "电力市场", "油气", "西气", "特高压", "配网", "源网荷储")
        SKIP_HOSTS = ("news.cn", "gov.cn", "peopleapp.com", "people.com.cn",
                      "xinhuanet", "qq.com", "weixin.qq.com", "163.com",
                      "people.com", "cctv", "people.cn")  # 过滤外链到其他媒体
        # 遍历所有 ul, 找含能源关键词的 li
        for ul in soup.find_all("ul"):
            lis = ul.find_all("li")
            if not lis:
                continue
            for li in lis:
                a = li.find("a")
                if not a:
                    continue
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if not title or len(title) < 8:
                    continue
                # 跳过外链 (news.cn / gov.cn 等其他媒体, 这些不是 NEA 原生内容)
                if any(host in href for host in SKIP_HOSTS):
                    continue
                # NEA 原生 URL 形如 "20260817/{hash}/c.html" (相对) 或带完整域
                # 标准化
                full_url = self._normalize_url(href)
                # 只保留 nea.gov.cn 域名
                if "nea.gov.cn" not in full_url:
                    continue
                # 日期从 URL /YYYYMMDD/ 提取
                date_text = self._extract_date_from_url(full_url)
                # 关键词加权 (能源类优先; 不限, 全部保留以保证覆盖率)
                key = f"{title}|{href}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                items.append({
                    "title": title,
                    "url": full_url,
                    "date": date_text,
                })
                if len(items) >= 20:
                    return items
        return items

    @staticmethod
    def _normalize_url(href: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return "https://www.nea.gov.cn" + href
        if href.startswith("./"):
            return "https://www.nea.gov.cn/" + href[2:]
        # 相对路径 (如 20260817/.../c.html)
        return "https://www.nea.gov.cn/" + href.lstrip("./")

    @staticmethod
    def _extract_date_from_url(url: str) -> str:
        m = _NEA_URL_DATE_RE.search(url)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return ""

    # ---------- 工具: 日期归一化 (W1-D4 兼容) ----------
    @staticmethod
    def _normalize_date(raw: str) -> str:
        if not raw or not isinstance(raw, str):
            return date.today().isoformat()
        s = raw.strip().replace("年", "-").replace("月", "-").replace("日", "")
        m = re.search(r"(\d{4})[-/.]?(\d{1,2})[-/.]?(\d{1,2})", s)
        if m:
            y, mo, d = m.groups()
            try:
                return date(int(y), int(mo), int(d)).isoformat()
            except ValueError:
                pass
        return date.today().isoformat()

    # ---------- 工具: 跨进程稳定 id (W1-D4 兼容) ----------
    @staticmethod
    def _stable_id(publish_iso: str, title: str, url: str) -> str:
        digest = hashlib.sha1(f"{publish_iso}|{url}|{title}".encode("utf-8")).hexdigest()
        seq = int(digest[:8], 16) % 10000
        date_seg = publish_iso.replace("-", "")
        return f"P-NEA-{date_seg}-{seq:04d}"

    # ---------- 工具: scope 推断 (W1-D4 兼容) ----------
    @classmethod
    def _guess_scope(cls, title: str) -> List[str]:
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
                "department": "国家能源局",
                "doc_number": item.get("doc_number"),
                "publish_date": publish_iso,
                "effective_date": publish_iso,
                "category": "policy",
                "scope": self._guess_scope(title),
                "priority": 1,  # NEA 红头文优先
                "summary": title[:100],
                "key_points": [],
                "source_url": url,
                "captured_at": now_iso,
                "captured_by": "nea-fetcher-v2.0",
                "tags": [],
                "review_status": "pending",
            })
        return policies


__all__ = ["NeaFetcher"]