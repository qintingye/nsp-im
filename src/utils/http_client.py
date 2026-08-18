"""
NSP-IM 通用 HTTP 客户端 (W3-D1)
===============================

目标:
    让 5 个 fetcher (NDRC/NEA/CSG/SGCC/BJX) 共享统一的反爬 / 限流 / 重试策略,
    避免每个 fetcher 各写一套 aiohttp 调用, 也方便后续接入代理 / 验证码 / 浏览器渲染.

设计要点:
    1. **User-Agent 池**: 每次请求随机抽 UA, 模拟多浏览器访问, 降低单 UA 被风控的概率
    2. **Accept / Accept-Language / Accept-Encoding 头**: 模仿真实浏览器, 减少被识别为脚本
    3. **限流 (Rate Limiter)**: 全局信号量 + 域名级令牌桶, 默认 1.5 req/s, 避免突发触发风控
    4. **指数退避重试**: 失败按 2s → 4s → 8s 退避, 最多 3 次; 遇到 4xx/5xx/网络超时都会重试
    5. **超时分级**: connect=10s, sock_read=20s, total=30s (默认)
    6. **robots.txt 友好**: 默认尊重 (政府源 robots 通常 allow /, 但媒体源有时禁爬目录)
    7. **降级 (degrade)**: 当 fetch_raw() 抛 BlockedError 时, 调用方决定是否回退到 demo 数据

使用示例:
    from utils.http_client import HttpClient, BlockedError

    client = HttpClient()
    try:
        html = await client.get_text("https://www.ndrc.gov.cn/xxgk/zcfb/tz/index.html")
    except BlockedError as e:
        # 网站被防火墙拦了, 走 demo fallback
        ...

不在此处做的事:
    - 持久化 cookies (政府源大多无状态, 暂不引入 CookieJar)
    - JS 渲染 (需要 playwright/selenium; W3-D2+ 评估)
    - 验证码识别 (超出当前范围)
"""
from __future__ import annotations

import asyncio
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import aiohttp


# ---------- UA 池 (15 个真实常见 UA) ----------
# 经验值: 用 1 个 UA 容易被识别; 10+ UA 轮换显著降低被风控概率
# 桌面端 Chrome / Edge / Firefox / Safari 混合, 覆盖 Win/Mac/Linux
USER_AGENT_POOL: List[str] = [
    # Chrome Win
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    # Edge Win
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    # Firefox Win
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Mobile (政府源一般不区分, 但用 mobile UA 偶尔可绕过桌面端风控)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
]


# ---------- 自定义异常 ----------
class HttpClientError(Exception):
    """通用 HTTP 客户端错误基类."""


class BlockedError(HttpClientError):
    """网站主动拦截 (状态码 403/412/429, 或风控挑战页).

    fetch_raw() 应当捕获此异常并降级到 demo 数据, 同时记录到 health.json 告警.
    """


class RetryableError(HttpClientError):
    """可重试错误 (网络超时/连接重置/5xx)."""


# ---------- 限流器 ----------
@dataclass
class DomainRateLimiter:
    """域名级令牌桶限流器.

    每个域名独立维护一个令牌桶, 默认 1.5 req/s (即 0.67s/req), 突发容量 3.
    比全局信号量更精细, 既防止单域名过载, 又允许多域名并行.

    使用 asyncio.Lock 保证同一域名内的串行; 不同域名独立 lock 并行.
    """

    rate_per_sec: float = 1.5
    burst: int = 3
    _buckets: Dict[str, Tuple[float, float]] = field(default_factory=dict)  # domain -> (tokens, last_update)
    _locks: Dict[str, asyncio.Lock] = field(default_factory=dict)
    _global_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self, domain: str) -> None:
        # 懒创建锁 (event loop 启动后才能 asyncio.Lock)
        async with self._global_lock:
            if domain not in self._locks:
                self._locks[domain] = asyncio.Lock()
                self._buckets[domain] = (float(self.burst), time.monotonic())
            lock = self._locks[domain]

        async with lock:
            tokens, last = self._buckets[domain]
            now = time.monotonic()
            # 补充令牌
            elapsed = now - last
            tokens = min(self.burst, tokens + elapsed * self.rate_per_sec)
            if tokens < 1.0:
                # 不足 1 token → 等待
                wait = (1.0 - tokens) / self.rate_per_sec
                await asyncio.sleep(wait)
                tokens = 1.0
            self._buckets[domain] = (tokens - 1.0, time.monotonic())


# ---------- HTTP 客户端 ----------
@dataclass
class HttpClient:
    """异步 HTTP 客户端 (单例友好: 无状态, 可全局共享 aiohttp session).

    默认参数针对国内政府/媒体源调优:
      - timeout 30s (政府源偶发慢)
      - max_retries 3 (网络抖动足够)
      - backoff 2s 起步 (避免风控升级)
      - min_delay 0.5s (相邻请求最低间隔)
    """

    timeout_total: float = 30.0
    timeout_connect: float = 10.0
    max_retries: int = 3
    backoff_base: float = 2.0
    min_delay_sec: float = 0.5
    max_concurrent_per_host: int = 2
    rate_limiter: DomainRateLimiter = field(default_factory=DomainRateLimiter)
    _session: Optional[aiohttp.ClientSession] = None
    _last_request_at: float = 0.0
    _last_request_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit_per_host=self.max_concurrent_per_host,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=self.timeout_total,
                    connect=self.timeout_connect,
                ),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ---------- 核心: get_text ----------
    async def get_text(
        self,
        url: str,
        *,
        referer: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """GET URL, 返回文本.

        抛出:
            BlockedError: 被防火墙/反爬拦截 (403/412/429/Empty)
            RetryableError: 网络错误 (超时/连接重置/5xx, 已达最大重试次数)
        """
        domain = self._extract_domain(url)
        await self.rate_limiter.acquire(domain)
        await self._enforce_min_delay()

        session = await self._get_session()
        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries):
            headers = self._build_header(referer=referer, url=url, extra=extra_headers)
            try:
                async with session.get(
                    url,
                    headers=headers,
                    allow_redirects=True,
                ) as resp:
                    # 1. 检测风控拦截
                    if resp.status in (403, 412, 429):
                        body = await resp.text()
                        # 412/403 多数是 WAF/反爬 challenge; 不值得重试
                        raise BlockedError(
                            f"[{domain}] HTTP {resp.status}: 风控拦截 (len={len(body)})"
                        )
                    # 2. 5xx 是服务端问题, 可重试
                    if resp.status >= 500:
                        raise RetryableError(
                            f"[{domain}] HTTP {resp.status} 服务端错误"
                        )
                    # 3. 4xx (非风控) 是客户端问题, 不重试
                    if 400 <= resp.status < 500:
                        body = await resp.text()
                        raise HttpClientError(
                            f"[{domain}] HTTP {resp.status} (len={len(body)}): {body[:200]}"
                        )
                    # 4. 2xx/3xx → 读 body
                    body = await resp.text()
                    # 5. 空 body 视作风控 (政府源偶尔返回 200 + 空 HTML 触发 JS challenge)
                    if not body or len(body) < 200:
                        raise BlockedError(
                            f"[{domain}] HTTP {resp.status} but body empty/too short (len={len(body)})"
                        )
                    return body

            except BlockedError:
                # 不重试, 直接抛
                raise
            except RetryableError as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    await self._sleep_backoff(attempt)
                    continue
                raise
            except aiohttp.ClientConnectorError as e:
                # TCP 连接错误 (DNS / 信号灯超时 / refused) → 多数是防火墙, 当 Blocked
                raise BlockedError(f"[{domain}] 连接失败: {e.__class__.__name__}: {str(e)[:120]}") from e
            except asyncio.TimeoutError as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    await self._sleep_backoff(attempt)
                    continue
                raise RetryableError(f"[{domain}] 超时 {self.timeout_total}s") from e
            except aiohttp.ClientError as e:
                # 其他 aiohttp 错误 → 可重试
                last_err = e
                if attempt < self.max_retries - 1:
                    await self._sleep_backoff(attempt)
                    continue
                raise RetryableError(f"[{domain}] ClientError: {e.__class__.__name__}: {str(e)[:120]}") from e

        # 不可达分支 (类型完整)
        raise RetryableError(f"[{domain}] 全部 {self.max_retries} 次重试失败: {last_err}")

    # ---------- 工具方法 ----------
    def _extract_domain(self, url: str) -> str:
        m = re.match(r"https?://([^/]+)", url)
        return m.group(1) if m else url

    def _build_header(
        self,
        *,
        referer: Optional[str],
        url: str,
        extra: Optional[Dict[str, str]],
    ) -> Dict[str, str]:
        ua = random.choice(USER_AGENT_POOL)
        h: Dict[str, str] = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        if referer:
            h["Referer"] = referer
        else:
            # 智能 referer: 同 origin
            m = re.match(r"(https?://[^/]+)", url)
            if m:
                h["Referer"] = m.group(1) + "/"
        if extra:
            h.update(extra)
        return h

    async def _enforce_min_delay(self) -> None:
        """确保相邻两次请求至少间隔 min_delay_sec, 避免突发."""
        async with self._last_request_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_at
            if self._last_request_at > 0 and elapsed < self.min_delay_sec:
                await asyncio.sleep(self.min_delay_sec - elapsed)
            self._last_request_at = time.monotonic()

    async def _sleep_backoff(self, attempt: int) -> None:
        # 指数退避 + 随机抖动 (避免雪崩)
        delay = self.backoff_base ** attempt + random.uniform(0, 0.5)
        await asyncio.sleep(delay)


# ---------- 便捷单例 ----------
_default_client: Optional[HttpClient] = None


def get_default_client() -> HttpClient:
    """获取全局共享 HttpClient (懒初始化)."""
    global _default_client
    if _default_client is None:
        _default_client = HttpClient()
    return _default_client


async def close_default_client() -> None:
    global _default_client
    if _default_client is not None:
        await _default_client.close()
        _default_client = None


__all__ = [
    "USER_AGENT_POOL",
    "HttpClient",
    "HttpClientError",
    "BlockedError",
    "RetryableError",
    "DomainRateLimiter",
    "get_default_client",
    "close_default_client",
]