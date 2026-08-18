"""
NSP-IM OneSignal 免费层封装
============================

W3-D3 BE 改动:
  - OneSignal REST API v1 客户端 (通知发送 + 设备查看)
  - 免费层限制: 每月 10K 通知, 单次最多 2K 设备, Web Push 走自家 FCM/Mozilla
  - 仅在 ONESIGNAL_APP_ID 配置时启用, 否则视为禁用 (静默跳过)
  - 推送失败不影响 Web Push 主链路 (独立函数, 调用方决定 fallback 策略)
  - 超时 10s (海外服务响应较慢)

OneSignal API 参考: https://documentation.onesignal.com/reference/rest-api-overview

与 webpush.py 的关系:
  - Web Push (VAPID) 是主链路, 浏览器直连推送服务 (FCM/Mozilla Autopush)
  - OneSignal 是 SaaS 通道, 用于:
      a) iOS Safari < 16.4 降级 (Web Push 不可用)
      b) 国内浏览器自动 fallback (OneSignal 有国内 CDN 节点)
      c) 邮件/短信多通道
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx

LOG = logging.getLogger("nspim.push.onesignal")

ONESIGNAL_API_BASE = "https://onesignal.com/api/v1"

# 免费层单次通知最大设备数 (OneSignal 文档: 2,000 for paid, 100 for free trial)
# 保守按 100 处理, 超出时分批
ONESIGNAL_MAX_DEVICES_PER_REQUEST = 100


@dataclass
class OneSignalConfig:
    """OneSignal 配置. 全字段缺失即视为禁用."""

    app_id: str
    rest_api_key: str

    @classmethod
    def from_env(cls) -> Optional["OneSignalConfig"]:
        """从环境变量读取. 缺失返回 None."""
        app_id = os.environ.get("ONESIGNAL_APP_ID", "").strip()
        rest_api_key = os.environ.get("ONESIGNAL_REST_API_KEY", "").strip()
        if not app_id or not rest_api_key:
            return None
        return cls(app_id=app_id, rest_api_key=rest_api_key)


@dataclass
class OneSignalNotification:
    """要发送的通知.

    contents 是各语言版本, key=语言代码 (如 'en', 'zh'), value=文本.
    """

    heading: str                          # 通知标题
    contents: dict[str, str]              # 多语言内容 {"en": "...", "zh": "..."}
    url: Optional[str] = None             # 点击后跳转 URL
    icon: Optional[str] = None
    included_segments: list[str] = field(default_factory=lambda: ["Subscribed Users"])
    send_after: Optional[str] = None      # ISO 8601 时间, 定时发送
    ttl: int = 86400                      # 秒, 默认 24h
    priority: int = 5                     # 10=high, 5=normal, 1=low

    def to_api_body(self, app_id: str) -> dict:
        body = {
            "app_id": app_id,
            "headings": {
                "en": self.heading[:64],
                **{k: v[:64] for k, v in self.contents.items()},
            },
            "contents": {k: v[:200] for k, v in self.contents.items()},
            "included_segments": self.included_segments,
            "ttl": self.ttl,
            "priority": self.priority,
        }
        if self.url:
            body["url"] = self.url
        if self.icon:
            body["chrome_web_icon"] = self.icon
        if self.send_after:
            body["send_after"] = self.send_after
        return body


class OneSignalError(Exception):
    """OneSignal API 调用失败."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def is_configured() -> bool:
    """OneSignal 是否已配置 (APP ID + REST API Key 都存在)."""
    return OneSignalConfig.from_env() is not None


def send_notification(
    notification: OneSignalNotification,
    *,
    timeout: float = 10.0,
) -> dict:
    """发送一条通知 (向所有 Subscribed Users).

    Returns:
        API 返回的 JSON dict (含 id/recipients 等字段)

    Raises:
        OneSignalError: API 返回非 2xx, 或网络错误
    """
    cfg = OneSignalConfig.from_env()
    if cfg is None:
        raise OneSignalError("OneSignal 未配置 (ONESIGNAL_APP_ID 或 ONESIGNAL_REST_API_KEY 缺失)")

    url = f"{ONESIGNAL_API_BASE}/notifications"
    body = notification.to_api_body(cfg.app_id)

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Basic {cfg.rest_api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
    except httpx.HTTPError as e:
        raise OneSignalError(f"OneSignal 网络错误: {e}") from e

    if resp.status_code >= 400:
        # OneSignal 错误格式: {"errors": ["message"]}
        try:
            err_body = resp.json()
            err_msg = err_body.get("errors", [resp.text])[0]
        except Exception:
            err_msg = resp.text
        raise OneSignalError(
            f"OneSignal API 错误 (HTTP {resp.status_code}): {err_msg}",
            status_code=resp.status_code,
        )

    try:
        return resp.json()
    except json.JSONDecodeError:
        return {"raw": resp.text}


def send_to_player_ids(
    player_ids: list[str],
    notification: OneSignalNotification,
    *,
    timeout: float = 10.0,
) -> dict:
    """向指定 OneSignal player_id 列表推送 (定向用户).

    Args:
        player_ids: OneSignal SDK 生成的 player_id 列表 (浏览器 OneSignal.init() 返回)

    Returns:
        API 返回的 JSON dict
    """
    if not player_ids:
        raise OneSignalError("player_ids 为空")

    cfg = OneSignalConfig.from_env()
    if cfg is None:
        raise OneSignalError("OneSignal 未配置")

    # 分批 (免费层上限保护)
    if len(player_ids) > ONESIGNAL_MAX_DEVICES_PER_REQUEST:
        LOG.warning(
            "player_ids=%d 超过单次上限 %d, 仅取前 %d",
            len(player_ids), ONESIGNAL_MAX_DEVICES_PER_REQUEST, ONESIGNAL_MAX_DEVICES_PER_REQUEST,
        )
        player_ids = player_ids[:ONESIGNAL_MAX_DEVICES_PER_REQUEST]

    url = f"{ONESIGNAL_API_BASE}/notifications"
    body = notification.to_api_body(cfg.app_id)
    body["include_player_ids"] = player_ids
    # 去掉 included_segments (定向时互斥)
    body.pop("included_segments", None)

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Basic {cfg.rest_api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
    except httpx.HTTPError as e:
        raise OneSignalError(f"OneSignal 网络错误: {e}") from e

    if resp.status_code >= 400:
        try:
            err_body = resp.json()
            err_msg = err_body.get("errors", [resp.text])[0]
        except Exception:
            err_msg = resp.text
        raise OneSignalError(
            f"OneSignal API 错误 (HTTP {resp.status_code}): {err_msg}",
            status_code=resp.status_code,
        )

    return resp.json()


def get_notification_status(notification_id: str, *, timeout: float = 10.0) -> dict:
    """查询通知送达状态 (debug 用)."""
    cfg = OneSignalConfig.from_env()
    if cfg is None:
        raise OneSignalError("OneSignal 未配置")
    url = f"{ONESIGNAL_API_BASE}/notifications/{notification_id}?app_id={cfg.app_id}"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(
                url,
                headers={"Authorization": f"Basic {cfg.rest_api_key}"},
            )
        if resp.status_code >= 400:
            raise OneSignalError(
                f"查询失败 (HTTP {resp.status_code}): {resp.text}",
                status_code=resp.status_code,
            )
        return resp.json()
    except httpx.HTTPError as e:
        raise OneSignalError(f"网络错误: {e}") from e