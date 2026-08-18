"""
NSP-IM Fetcher 健壮基类 v1.0 (W3-D1)

封装公共能力:
  - 真实浏览器 User-Agent + 多 header (防 403 / 反爬)
  - 1-2s 限流延迟 (避免触发站点限流)
  - 激进重试 (sgcc 15s 超时 → 拆 3 次 5s 试)
  - SSL 兼容 (Windows + Py3.11 aiohttp 偶尔 SSL EOF)
  - demo fallback: 真抓失败/超时/0 条 → 调用同源 demo 数据

使用:
  from fetchers.robust import RobustFetcher, robust_get_html, ROBOT_UA

  class MyFetcher(RobustFetcher):
      async def fetch_raw(self):
          html = await robust_get_html(self.session, self.source_url, timeout=5)
          ...
"""
from __future__ import annotations

import asyncio
import random
import ssl
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import aiohttp

# ---- 真实浏览器 header 集 ---------------------------------------------------
# 真实 UA (Chrome 120 on Windows), 减少被识别为 bot
ROBOT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 默认 headers: 多站点共用, 防止简单 UA-only 校验触发 403
DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": ROBOT_UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# SSL: Windows + Py3.11 aiohttp 经常 SSL EOF; 关验证可显著提速 + 减少异常
DEFAULT_SSL_CTX = ssl.create_default_context()
DEFAULT_SSL_CTX.check_hostname = False
DEFAULT_SSL_CTX.verify_mode = ssl.CERT_NONE

# ---- 重试 / 限流参数 ---------------------------------------------------------
# 默认每个请求 sleep_delay + jitter, 防并发雪崩
DEFAULT_MIN_DELAY = 1.0
DEFAULT_MAX_DELAY = 2.0
DEFAULT_MAX_RETRIES = 3
# sgcc 历史超时 15s; 拆 3 次 5s, 让一次 504 后还有 2 次机会
DEFAULT_PER_ATTEMPT_TIMEOUT = 5.0


def _jittered_sleep(min_s: float = DEFAULT_MIN_DELAY, max_s: float = DEFAULT_MAX_DELAY) -> float:
    """随机延迟, 防多个 fetcher 同步请求被限流。"""
    return random.uniform(min_s, max_s)


async def robust_get_html(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout: float = DEFAULT_PER_ATTEMPT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    min_delay: float = DEFAULT_MIN_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    headers: Optional[Dict[str, str]] = None,
    ssl_ctx=DEFAULT_SSL_CTX,
) -> Optional[str]:
    """带重试 + 限流 + headers 的 GET.

    Returns:
        HTML 文本; 全部重试失败返回 None (caller 决定 fallback).
    """
    last_err: Optional[BaseException] = None
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    for attempt in range(1, max_retries + 1):
        try:
            # 1-2s 随机延迟, 防被限流 (第一次也抖一下, 防止冷启动并发同瞬间)
            if attempt > 1 or True:
                await asyncio.sleep(_jittered_sleep(min_delay, max_delay))
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with session.get(
                url,
                headers=hdrs,
                timeout=client_timeout,
                ssl=ssl_ctx,
                allow_redirects=True,
            ) as resp:
                if resp.status in (403, 429):
                    # 反爬触发; 等更久再试
                    last_err = aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                    )
                    backoff = min(2 ** attempt, 8)
                    await asyncio.sleep(backoff)
                    continue
                # 2xx
                html = await resp.text(errors="replace")
                return html
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            last_err = e
            if attempt < max_retries:
                backoff = min(2 ** attempt, 8)
                await asyncio.sleep(backoff)
                continue
            break
    return None


class RobustFetcher:
    """Mixin: 为真抓 fetcher 提供统一 header + SSL + 限流 session.

    子类只需:
      1. 在 __init__ 调用 super().__init__(name=..., source_url=..., max_retries=3)
      2. 实现 fetch_raw(); 在内部用 self.robust_get(...) 替代裸 session.get
      3. 失败 fallback 时调用 self.demo_fallback() (需提供 _DEMO_DATA 属性)
    """

    # 默认 demo 缓存: 子类覆盖
    _DEMO_DATA: List[Dict[str, Any]] = []

    def __init__(
        self,
        *,
        name: str,
        source_url: str,
        max_retries: int = DEFAULT_MAX_RETRIES,
        per_attempt_timeout: float = DEFAULT_PER_ATTEMPT_TIMEOUT,
        min_delay: float = DEFAULT_MIN_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ):
        self.name = name
        self.source_url = source_url
        self.max_retries = max_retries
        self.per_attempt_timeout = per_attempt_timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.per_attempt_timeout * self.max_retries)
            self._session = aiohttp.ClientSession(
                headers=dict(DEFAULT_HEADERS),
                timeout=timeout,
                connector=aiohttp.TCPConnector(ssl=DEFAULT_SSL_CTX, limit=10),
            )
        return self._session

    async def robust_get(
        self,
        url: Optional[str] = None,
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> Optional[str]:
        """带 header + 重试 + 限流 的 GET, 返回 HTML 文本或 None."""
        sess = await self._ensure_session()
        return await robust_get_html(
            sess,
            url or self.source_url,
            timeout=timeout if timeout is not None else self.per_attempt_timeout,
            max_retries=max_retries if max_retries is not None else self.max_retries,
            min_delay=self.min_delay,
            max_delay=self.max_delay,
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def demo_fallback(self) -> List[Dict[str, Any]]:
        """真抓失败兜底: 返回同源 demo 数据 (子类覆写 _DEMO_DATA)."""
        return [dict(item) for item in self._DEMO_DATA]


__all__ = [
    "RobustFetcher",
    "robust_get_html",
    "ROBOT_UA",
    "DEFAULT_HEADERS",
    "DEFAULT_SSL_CTX",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_PER_ATTEMPT_TIMEOUT",
]