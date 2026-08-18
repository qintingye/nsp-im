"""
NSP-IM 发改委政策抓取器 v2.0 (W3-D1 真抓版)
源：https://www.ndrc.gov.cn

W3-D1 升级:
  - 真抓版: 列表页 aiohttp + BeautifulSoup 解析 (NDRC 反爬温和, 单 UA + 1.5 req/s 即可)
  - 列表页结构: ul > li (每个 li 含 <a title=...> + 日期文本 形如 2026/08/17)
  - 详情页解析: doc_number (如 "发改能源〔2026〕1055号"), publish_date
  - 复用 utils.http_client 的 UA 池 / 限流 / 重试 / 风控检测
  - 与 W1-D4 兼容: 保留 _normalize_date / _stable_id / _guess_scope 工具方法
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


log = logging.getLogger("fetcher.ndrc")


# 发改委列表页结构 (实测):
#   <ul>
#     <li><a href="./202608/t20260817_1407041.html">关于印发《XXX》的通知(发改能源〔2026〕1055号)</a>
#         相关解读
#         <span>2026/08/17</span>     # 日期在 li 文本末尾 (部分 li)
#     </li>
#   </ul>
# 详情页:
#   <h1>关于印发《XXX》的通知(发改能源〔2026〕1055号)</h1>
#   <div class="..."> 发布时间: 2026/08/17  来源: 能源局 ... </div>
_NDRC_LIST_URL = "https://www.ndrc.gov.cn/xxgk/zcfb/tz/index.html"


# doc_number 提取正则: "发改能源〔2026〕1055号", "发改办环资〔2026〕520号", "发改民营〔2026〕10号"
# 兼容括号内数字 / 中文括号
_DOCNO_RE = re.compile(
    r"发改[\u4e00-\u9fa5]+[〔(]\d{4}[〕)]\d+号"
)


class NdrcFetcher(BaseFetcher):
    """国家发改委 (NDRC) fetcher v2.0.

    W3-D1 真抓版流程:
      1) GET 列表页 → 解析 ul > li > a (标题+URL) + 日期文本
      2) 对每条政策 GET 详情页 → 提取 doc_number + 校验发布日期
      3) parse() 输出 schema 合规 dict 列表

    反爬策略 (utils.http_client 默认):
      - 随机 UA (14 个真实 Chrome/Edge/Safari/Firefox/Mobile 池)
      - 1.5 req/s 域令牌桶限流
      - 403/412/429 视为 BlockedError → 降级 demo
      - 超时 / 5xx 指数退避 3 次
    """

    _SCOPE_KEYWORDS = {
        "grid": ("电网", "电力", "能源", "新能源", "储能", "光伏", "风电", "消纳", "调度"),
        "water": ("水", "供水", "水利"),
        "compute": ("算", "数据", "数据中心"),
        "telecom": ("通信", "5G", "6G", "网络"),
        "pipe": ("管网", "管廊", "燃气", "油气", "西气东输"),
        "logi": ("运输", "物流", "多式联运", "铁路", "公路"),
    }

    def __init__(self, client: Optional[HttpClient] = None):
        super().__init__(
            name="发改委",
            source_url=_NDRC_LIST_URL,
        )
        self.client = client or get_default_client()

    # ---------- 抓取 ----------
    async def fetch_raw(self) -> List[Dict[str, Any]]:
        """真抓列表页 → 解析 ul > li > a + 日期 + 跳详情页提 doc_number."""
        html = await self.client.get_text(
            _NDRC_LIST_URL,
            referer="https://www.ndrc.gov.cn/",
        )
        items = self._parse_list_html(html)
        if not items:
            return []

        # 详情页: 补全 doc_number / publish_date (列表页日期可能不全)
        enriched: List[Dict[str, Any]] = []
        for it in items[:20]:  # 列表 20 条上限 (避免突发 50 req)
            try:
                detail = await self._fetch_detail(it["url"])
                if detail:
                    it.update(detail)
            except BlockedError:
                # 详情页被风控 → 列表页数据保留, doc_number 留空
                it.setdefault("doc_number", None)
            enriched.append(it)
        return enriched

    def _parse_list_html(self, html: str) -> List[Dict[str, Any]]:
        """解析发改委列表页 (ul > li > a + 日期).

        策略: 遍历所有 ul, 累计 "政策类 li" (含 通知/意见/办法/规划/方案/制度/印发/部署/推进),
        一旦达到 5 条即视为找到了列表区, 停止扫描, 避免误抓导航条.
        """
        soup = BeautifulSoup(html, "html.parser")
        items: List[Dict[str, Any]] = []
        seen_keys: set = set()  # 去重 (title+href)
        POLICY_KEYWORDS = ("通知", "意见", "办法", "规划", "方案", "制度", "印发", "部署", "推进", "实施方案")
        for ul in soup.find_all("ul"):
            lis = ul.find_all("li")
            if len(lis) < 5:
                continue  # 过滤导航条 ul
            for li in lis:
                a = li.find("a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if not title or len(title) < 6:
                    continue
                # 过滤"答记者问" / "一图读懂" 类解读文章 (不在通知正文列表)
                if "答记者问" in title or "一图读懂" in title:
                    continue
                if not any(kw in title for kw in POLICY_KEYWORDS):
                    continue
                key = f"{title}|{href}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                # 拼接完整 URL
                full_url = self._normalize_url(href)
                # 日期
                date_text = self._extract_date_from_li(li)
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
        if href.startswith("./"):
            # 形如 ./202608/t20260817_1407041.html
            return "https://www.ndrc.gov.cn/xxgk/zcfb/tz/" + href[2:]
        if href.startswith("../"):
            # 形如 ../../jd/jd/202608/t... — 跨目录, 用 root 拼
            return "https://www.ndrc.gov.cn/" + href.replace("../", "")
        if href.startswith("/"):
            return "https://www.ndrc.gov.cn" + href
        # 默认相对列表页
        return "https://www.ndrc.gov.cn/xxgk/zcfb/tz/" + href.lstrip("./")

    @staticmethod
    def _extract_date_from_li(li) -> str:
        """从 li 元素提日期 (优先 span, 其次 li 末尾文本)."""
        # 优先 span 内的日期
        for span in li.find_all("span"):
            txt = span.get_text(strip=True)
            if re.match(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", txt):
                return txt
        # 兜底: li 末尾的日期
        text = li.get_text(" ", strip=True)
        m = re.search(r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", text)
        if m:
            return m.group(1)
        return ""

    async def _fetch_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """抓详情页提 doc_number / publish_date (软失败, 不抛).

        抛出:
            BlockedError: 已被 BlockedError 传递, 调用方处理降级
            其他异常 → 包装成 None 返回 (不阻断列表数据)
        """
        from utils.http_client import HttpClientError
        try:
            html = await self.client.get_text(
                url,
                referer=_NDRC_LIST_URL,
            )
        except BlockedError:
            # 详情页被风控 → 列表数据保留, doc_number 留空
            raise  # 让 fetch_raw() 的外层 except 统一处理
        except HttpClientError as e:
            # 404 / 其他客户端错误 → 软失败, 返回 None
            log.debug("NDRC 详情页失败 %s: %s", url, e)
            return None
        # doc_number
        m = _DOCNO_RE.search(html)
        doc_number = m.group(0) if m else None
        # publish_date: 详情页有 "发布时间：2026/08/17" / "2026-08-17"
        m = re.search(r"发布时间[：:]\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", html)
        if not m:
            m = re.search(r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", html)
        date_text = m.group(1) if m else ""
        return {"doc_number": doc_number, "detail_date": date_text}

    # ---------- 工具: 日期归一化 (W1-D4 P0-3 兼容) ----------
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
        return f"P-NDRC-{date_seg}-{seq:04d}"

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
            # 日期: 优先详情页, 兜底列表页
            date_src = item.get("detail_date") or item.get("date") or ""
            publish_iso = self._normalize_date(date_src)
            policies.append({
                "id": self._stable_id(publish_iso, title, url),
                "title": title,
                "department": "国家发改委",
                "doc_number": item.get("doc_number"),  # 详情页提
                "publish_date": publish_iso,
                "effective_date": publish_iso,
                "category": "policy",
                "scope": self._guess_scope(title),
                "priority": 2,
                "summary": title[:100],
                "key_points": [],
                "source_url": url,
                "captured_at": now_iso,
                "captured_by": "ndrc-fetcher-v2.0",  # W3-D1 升级标记
                "tags": [],
                "review_status": "pending",
            })
        return policies


__all__ = ["NdrcFetcher"]