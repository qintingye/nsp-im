"""
NSP-IM 订阅存储 (W3-D3 BE)
==========================

设计目标:
    持久化浏览器 PushSubscription, 用于"政策入库时广播给全部订阅者".
    - 原子读写 (复用 utils.atomic_write)
    - 自动清理失效订阅 (410/404 标记后, 异步清理)
    - 简单去重 (endpoint 作为主键)
    - 线程安全 (threading.Lock, 单进程 server 足够; 多进程用 fcntl)

数据格式 (data/.subscriptions.json):
    {
      "version": "1.0",
      "subscriptions": [
        {
          "endpoint": "https://fcm.googleapis.com/fcm/send/...",
          "keys": {"p256dh": "...", "auth": "..."},
          "ua": "Mozilla/5.0 ...",        # 创建时的 UA, 用于排查
          "created_at": "2026-08-18T10:00:00Z",
          "last_seen_at": "2026-08-18T10:00:00Z",
          "status": "active",             # active | expired
          "fail_count": 0                 # 连续失败次数 (≥3 → 主动清理)
        }
      ]
    }

注意: 文件路径锚定仓库根, 与 utils/vapid.py 一致.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

# 路径锚定: src/api/subscriptions.py → parents[0]=src/api, parents[1]=src, parents[2]=nsp-im
_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[2]
DEFAULT_SUBSCRIPTIONS_FILE = REPO_ROOT / "data" / ".subscriptions.json"

# 让 utils.* 可以直接被 import (与 src/fetchers/base.py 一致)
import sys
SRC_DIR = str(REPO_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from utils.atomic_write import atomic_write_json, safe_read_json  # noqa: E402

LOG = logging.getLogger("nspim.push.subscriptions")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SubscriptionStore:
    """Push 订阅存储 (单进程线程安全).

    用法:
        store = SubscriptionStore()
        store.add({"endpoint": "...", "keys": {...}}, ua="Mozilla/5.0...")
        for sub in store.list_active():
            ...
        store.mark_expired(endpoint)
        store.cleanup_expired()
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or DEFAULT_SUBSCRIPTIONS_FILE
        self._lock = threading.Lock()

    # ---------------- 读取 ----------------

    def _read(self) -> dict:
        data = safe_read_json(self.path, default=None)
        if not isinstance(data, dict) or "subscriptions" not in data:
            return {"version": "1.0", "subscriptions": []}
        # 兜底: 缺字段时补默认
        for sub in data.get("subscriptions", []):
            sub.setdefault("status", "active")
            sub.setdefault("fail_count", 0)
            sub.setdefault("created_at", _utc_now_iso())
            sub.setdefault("last_seen_at", sub["created_at"])
        return data

    def list_active(self) -> list[dict]:
        """返回所有 status=active 的订阅 (深拷贝, 调用方修改不影响存储)."""
        with self._lock:
            data = self._read()
        return [dict(s) for s in data["subscriptions"] if s.get("status") == "active"]

    def list_all(self) -> list[dict]:
        with self._lock:
            data = self._read()
        return [dict(s) for s in data["subscriptions"]]

    def count_active(self) -> int:
        with self._lock:
            data = self._read()
        return sum(1 for s in data["subscriptions"] if s.get("status") == "active")

    def has_endpoint(self, endpoint: str) -> bool:
        with self._lock:
            data = self._read()
        return any(s["endpoint"] == endpoint for s in data["subscriptions"])

    # ---------------- 写入 ----------------

    def _write(self, data: dict) -> None:
        atomic_write_json(self.path, data, ensure_ascii=False, indent=2)

    def add(self, subscription: dict, *, ua: str = "") -> dict:
        """添加或更新订阅 (endpoint 已存在则更新 keys/ua/last_seen_at).

        Returns: 最终落盘的订阅 dict
        """
        if "endpoint" not in subscription:
            raise ValueError("subscription 缺少 endpoint 字段")
        if "keys" not in subscription or "p256dh" not in subscription["keys"] or "auth" not in subscription["keys"]:
            raise ValueError("subscription.keys 必须包含 p256dh + auth")

        endpoint = subscription["endpoint"]
        now = _utc_now_iso()

        with self._lock:
            data = self._read()
            existing = None
            for s in data["subscriptions"]:
                if s["endpoint"] == endpoint:
                    existing = s
                    break

            if existing is None:
                record = {
                    "endpoint": endpoint,
                    "keys": {
                        "p256dh": subscription["keys"]["p256dh"],
                        "auth": subscription["keys"]["auth"],
                    },
                    "ua": ua[:512] if ua else "",
                    "created_at": now,
                    "last_seen_at": now,
                    "status": "active",
                    "fail_count": 0,
                }
                data["subscriptions"].append(record)
                LOG.info("新订阅已添加 endpoint=%s", endpoint[:60])
            else:
                existing["keys"] = {
                    "p256dh": subscription["keys"]["p256dh"],
                    "auth": subscription["keys"]["auth"],
                }
                if ua:
                    existing["ua"] = ua[:512]
                existing["last_seen_at"] = now
                existing["status"] = "active"
                existing["fail_count"] = 0
                record = existing
                LOG.info("订阅已刷新 endpoint=%s", endpoint[:60])

            self._write(data)
        return dict(record)

    def remove(self, endpoint: str) -> bool:
        """物理删除 (与 mark_expired 区别: 不留痕, 用于主动退订)."""
        with self._lock:
            data = self._read()
            before = len(data["subscriptions"])
            data["subscriptions"] = [s for s in data["subscriptions"] if s["endpoint"] != endpoint]
            if len(data["subscriptions"]) == before:
                return False
            self._write(data)
            LOG.info("订阅已删除 endpoint=%s", endpoint[:60])
            return True

    def mark_expired(self, endpoint: str) -> None:
        """标记失效 (404/410), 不立刻删除 (保留 24h 排查窗口)."""
        with self._lock:
            data = self._read()
            for s in data["subscriptions"]:
                if s["endpoint"] == endpoint:
                    if s.get("status") != "expired":
                        s["status"] = "expired"
                        s["expired_at"] = _utc_now_iso()
                        self._write(data)
                        LOG.info("订阅已标记失效 endpoint=%s", endpoint[:60])
                    return

    def increment_fail(self, endpoint: str, *, threshold: int = 3) -> bool:
        """累加 fail_count, 达到阈值自动标记失效. 返回 True=已失效."""
        with self._lock:
            data = self._read()
            for s in data["subscriptions"]:
                if s["endpoint"] == endpoint:
                    s["fail_count"] = int(s.get("fail_count", 0)) + 1
                    s["last_seen_at"] = _utc_now_iso()
                    if s["fail_count"] >= threshold and s.get("status") != "expired":
                        s["status"] = "expired"
                        s["expired_at"] = _utc_now_iso()
                        self._write(data)
                        LOG.warning(
                            "订阅连续失败 %d 次, 标记失效 endpoint=%s",
                            s["fail_count"], endpoint[:60],
                        )
                        return True
                    self._write(data)
                    return False
        return False

    def cleanup_expired(self) -> int:
        """清理所有 expired 记录, 返回清理数."""
        with self._lock:
            data = self._read()
            before = len(data["subscriptions"])
            data["subscriptions"] = [s for s in data["subscriptions"] if s.get("status") == "active"]
            removed = before - len(data["subscriptions"])
            if removed > 0:
                self._write(data)
                LOG.info("清理失效订阅 %d 条", removed)
            return removed


# 便捷全局实例 (单进程场景, 避免每个请求都新建)
_global: Optional[SubscriptionStore] = None
_global_lock = threading.Lock()


def get_default_store() -> SubscriptionStore:
    global _global
    with _global_lock:
        if _global is None:
            _global = SubscriptionStore()
        return _global


__all__ = ["SubscriptionStore", "get_default_store", "DEFAULT_SUBSCRIPTIONS_FILE"]