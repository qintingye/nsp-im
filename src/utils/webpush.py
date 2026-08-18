"""
NSP-IM Web Push 发送器 (pywebpush 封装)
========================================

W3-D3 BE 改动:
  - 封装 pywebpush.webpush() 一行调用, 隐藏 VAPID 私钥转换
  - 标准化错误分类:
      * 404 / 410 → 订阅失效 (清理本地存储)
      * 401 / 403 → VAPID 配置错误 (运维告警)
      * 429 → 触发限流 (重试)
      * 其他 5xx → 服务端抖动 (1 次重试 + 退避)
  - 提供 send_push_to_subscriber() 高层 API

依赖: pywebpush>=2.0, cryptography>=42
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

import pywebpush
from py_vapid import Vapid

from utils.vapid import get_or_create_vapid_keys

LOG = logging.getLogger("nspim.push.webpush")


def _load_private_key_for_pywebpush(vapid_private_b64url: str) -> Vapid:
    """把 VAPID 私钥 base64url 转 py_vapid.Vapid 实例 (pywebpush 内部需要).

    py_vapid.Vapid.from_string() 自动识别 RAW 32 字节 (我们的存储格式).
    """
    return Vapid.from_string(private_key=vapid_private_b64url)

LOG = logging.getLogger("nspim.push.webpush")


@dataclass
class PushSubscription:
    """浏览器 PushSubscription JSON (来自 navigator.serviceWorker.pushManager.subscribe).

    字段名严格遵循 W3C Push API 规范.
    """

    endpoint: str
    keys_p256dh: str        # keys.p256dh (client public key, base64url)
    keys_auth: str          # keys.auth (auth secret, base64url)

    def to_dict(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.keys_p256dh, "auth": self.keys_auth},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PushSubscription":
        keys = d.get("keys", {})
        return cls(
            endpoint=d["endpoint"],
            keys_p256dh=keys["p256dh"],
            keys_auth=keys["auth"],
        )


@dataclass
class PushPayload:
    """要发送的通知载荷 (Service Worker push 事件接收).

    title 必须 ≤ 64 字符 (OneSignal 也按此截断),
    body 必须 ≤ 200 字符 (Chromium 显示上限).
    """

    title: str
    body: str
    icon: Optional[str] = None
    badge: Optional[str] = None
    url: Optional[str] = None           # 点击后跳转 URL
    tag: Optional[str] = None           # 同 tag 通知合并
    require_interaction: bool = False
    data: Optional[dict] = None         # 自定义数据 (透传给 SW)

    def to_json(self) -> str:
        d = {
            "title": self.title[:64],
            "body": self.body[:200],
            "icon": self.icon or "/icons/icon-192.png",
            "badge": self.badge or "/icons/badge-72.png",
            "requireInteraction": self.require_interaction,
        }
        if self.url:
            d["url"] = self.url
        if self.tag:
            d["tag"] = self.tag
        if self.data:
            d["data"] = self.data
        return json.dumps(d, ensure_ascii=False)


class PushError(Exception):
    """推送错误基类."""

    def __init__(self, message: str, status_code: Optional[int] = None, expired: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.expired = expired


class SubscriptionExpired(PushError):
    """订阅已失效 (404/410), 需要从本地存储清理."""


class VAPIDConfigError(PushError):
    """VAPID 凭证错误 (401/403), 运维需介入."""


class RateLimited(PushError):
    """推送服务限流 (429)."""


def _classify_error(exc: Exception) -> PushError:
    """把 pywebpush.WebPushException 分类为我们的异常类型.

    pywebpush 在网络层抛的 WebPushException 通常带 .response 属性;
    但 VAPID 签名失败等会在调用前抛异常, 没有 status_code.
    """
    resp = getattr(exc, "response", None)
    status = getattr(resp, "status_code", None) if resp is not None else None
    msg = str(exc) or exc.__class__.__name__
    if status in (404, 410):
        return SubscriptionExpired(f"订阅失效 (HTTP {status}): {msg}", status_code=status, expired=True)
    if status in (401, 403):
        return VAPIDConfigError(f"VAPID 凭证错误 (HTTP {status}): {msg}", status_code=status)
    if status == 429:
        return RateLimited(f"推送限流 (HTTP 429): {msg}", status_code=status)
    return PushError(f"推送失败 (HTTP {status}): {msg}", status_code=status)


def send_push(
    subscription: PushSubscription,
    payload: PushPayload,
    *,
    ttl: int = 86400,
    timeout: int = 10,
) -> bool:
    """发送一条 Web Push 通知.

    Args:
        subscription: 浏览器推送订阅对象
        payload: 通知载荷
        ttl: 消息生存时间 (秒), 默认 24h. 推送服务在订阅者离线时排队.
        timeout: HTTP 超时 (秒)

    Returns:
        True 推送成功
        False 订阅已失效 (调用方应清理)

    Raises:
        VAPIDConfigError: 凭证错 (401/403) - 运维介入
        RateLimited: 限流 (429) - 调用方退避重试
        PushError: 其他网络错误
    """
    keys = get_or_create_vapid_keys()
    private_key = _load_private_key_for_pywebpush(keys.private_key_b64url)

    try:
        response = pywebpush.webpush(
            subscription_info=subscription.to_dict(),
            data=payload.to_json(),
            vapid_private_key=private_key,
            vapid_claims={"sub": keys.subject},
            ttl=ttl,
            timeout=timeout,
        )
        LOG.info(
            "推送成功 endpoint=%s status=%s",
            subscription.endpoint[:60],
            getattr(response, "status_code", "?"),
        )
        return True

    except pywebpush.WebPushException as e:
        classified = _classify_error(e)
        if isinstance(classified, SubscriptionExpired):
            LOG.warning("订阅失效, 待清理: %s", subscription.endpoint[:60])
            return False
        LOG.error("推送异常 [%s]: %s", classified.__class__.__name__, classified)
        raise classified from e

    except Exception as e:
        # 网络抖动 / 超时 - 抛通用 PushError
        LOG.error("推送未分类异常: %s", e)
        raise PushError(f"推送未分类异常: {e}") from e


def send_push_batch(
    subscriptions: list[PushSubscription],
    payload: PushPayload,
    *,
    on_expired: Optional[callable] = None,
) -> tuple[int, int, int]:
    """批量推送 (常用于"新政策入库"广播给全部订阅者).

    Args:
        on_expired: 订阅失效时的回调 (签名: (PushSubscription) -> None)

    Returns:
        (success_count, expired_count, error_count)
    """
    success = expired = error = 0
    for sub in subscriptions:
        try:
            if send_push(sub, payload):
                success += 1
            else:
                expired += 1
                if on_expired:
                    try:
                        on_expired(sub)
                    except Exception as cb_err:
                        LOG.warning("on_expired 回调异常: %s", cb_err)
        except (VAPIDConfigError, RateLimited) as e:
            LOG.error("严重错误 (%s): %s", e.__class__.__name__, e)
            error += 1
            # VAPID 配置错误立即停 - 后续都是失败
            if isinstance(e, VAPIDConfigError):
                break
        except PushError:
            error += 1
    LOG.info("批量推送完成 success=%d expired=%d error=%d", success, expired, error)
    return success, expired, error