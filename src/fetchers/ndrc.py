"""
NSP-IM 发改委政策抓取器 v1.0
源：https://www.ndrc.gov.cn
"""
import hashlib
import re
from datetime import datetime, date
from .base import BaseFetcher

class NdrcFetcher(BaseFetcher):
    # 标题关键词 → 适用范围（与 schema "scope" 一致：grid/water/compute/telecom/pipe/logi/monitor）
    _SCOPE_KEYWORDS = {
        "grid":    ("电网", "电力", "能源", "新能源", "储能"),
        "water":   ("水", "供水", "水利"),
        "compute": ("算", "数据", "数据中心"),
        "telecom": ("通信", "5G", "6G", "网络"),
        "pipe":    ("管网", "管廊", "燃气", "油气"),
        "logi":    ("运输", "物流", "多式联运", "铁路", "公路"),
    }

    def __init__(self):
        super().__init__(
            name="发改委",
            source_url="https://www.ndrc.gov.cn/xxgk/zcfb/tz/index.html"
        )

    async def fetch_raw(self):
        import aiohttp
        from bs4 import BeautifulSoup
        async with aiohttp.ClientSession() as session:
            async with session.get(self.source_url, timeout=self.timeout) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        items = []
        # 发改委列表页结构：li > a（标题） + span（日期）
        # 兼容多种日期格式：YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYYMMDD
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
        return items

    # ---------- 工具函数：日期归一化 ----------
    @staticmethod
    def _normalize_date(raw: str) -> str:
        """把 '2026/08/17' / '2026.08.17' / '2026-08-17' / '20260817' / '2026年08月17日'
        都归一为 ISO 'YYYY-MM-DD'。

        兜底：解析失败时返回今天。这是 W1-D4 BE P0-3 修复：
        schema 要求 `publish_date` 是 `format: date`（ISO YYYY-MM-DD），
        旧代码直接写入 '2026/08/17' 会被 schema 拒绝。
        """
        if not raw or not isinstance(raw, str):
            return date.today().isoformat()
        s = raw.strip()
        # 中文年月日 → 替换为 ASCII 分隔符再解析
        s = s.replace("年", "-").replace("月", "-").replace("日", "")
        # 兼容 ±/无 分隔
        m = re.search(r"(\d{4})[\-/.]?(\d{1,2})[\-/.]?(\d{1,2})", s)
        if m:
            y, mo, d = m.groups()
            try:
                dt = date(int(y), int(mo), int(d))
                return dt.isoformat()
            except ValueError:
                pass
        return date.today().isoformat()

    @staticmethod
    def _stable_id(publish_iso: str, title: str, url: str) -> str:
        """生成跨进程稳定的 id：P-NDRC-YYYYMMDD-HHHH。

        用 sha1(date + '|' + url + '|' + title) 截前 4 位 hex (16 bit) 作为序号。
        为什么不用 hash()：Python hash() 受 PYTHONHASHSEED 控制，每次进程重启会变，
        导致同一政策两次抓取 id 不同 → base.py 去重失效（PM 已实测复现）。
        """
        digest = hashlib.sha1(f"{publish_iso}|{url}|{title}".encode("utf-8")).hexdigest()
        seq = int(digest[:8], 16) % 10000  # 32-bit → 4 位十进制
        date_seg = publish_iso.replace("-", "")
        return f"P-NDRC-{date_seg}-{seq:04d}"

    # ---------- 工具函数：scope 推断 ----------
    @classmethod
    def _guess_scope(cls, title: str) -> list[str]:
        """根据标题关键字推断适用范围，至少包含 monitor（兜底默认）。"""
        scopes = {"monitor"}
        for scope, kws in cls._SCOPE_KEYWORDS.items():
            if any(kw in title for kw in kws):
                scopes.add(scope)
        return sorted(scopes)

    def parse(self, raw):
        policies = []
        now_iso = datetime.utcnow().isoformat() + "Z"
        for item in raw:
            title = item.get("title", "")
            url = item.get("url", "")
            publish_iso = self._normalize_date(item.get("date", ""))
            policies.append({
                "id": self._stable_id(publish_iso, title, url),
                "title": title,
                "department": "国家发改委",
                "doc_number": None,  # 需要详情页解析
                "publish_date": publish_iso,
                "effective_date": publish_iso,
                "category": "policy",
                "scope": self._guess_scope(title),
                "priority": 2,
                "summary": title[:100],
                "key_points": [],
                "source_url": url,
                "captured_at": now_iso,
                "captured_by": "ndrc-fetcher-v1.0",
                "tags": [],
                "review_status": "pending",
            })
        return policies
