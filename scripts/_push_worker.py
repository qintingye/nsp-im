#!/usr/bin/env python
"""
NSP-IM Push Worker (W3-D3 BE)
==============================

监听 data/policies.json 变化, 把"新政策入库"事件广播给所有 Push 订阅者.

设计取舍:
    - 轮询 (默认 60s) 而非 inotify: 跨平台 (Windows + Linux), 无需 watchdog 依赖
    - 持久化"上次推送过的 policy id 集合"到 data/.push_seen.json (原子写入)
    - 单次推送: title=政策标题, body=部门+文号+发布日期, url=source_url (若有), tag=policy id
    - 失效订阅 (404/410): 标记 expired, 不立即物理删除 (保留排查窗口)
    - 失败率 > 50% 或 VAPID 配置错误: 走兜底 OneSignal (若配置), 否则记日志退出非零

两种运行模式:
    1. 默认: 守护进程 (loop forever, 60s 间隔)
    2. --once: 跑一次就退出 (CI / GitHub Actions 兜底)

Usage:
    # 守护进程
    python scripts/_push_worker.py

    # CI 模式 (每日 9:30 跑, 在 main_fetcher 之后)
    python scripts/_push_worker.py --once
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 路径锚定: scripts/_push_worker.py → parents[0]=scripts, parents[1]=nsp-im
_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.webpush import (  # noqa: E402
    PushSubscription,
    PushPayload,
    SubscriptionExpired,
    VAPIDConfigError,
    send_push,
)
from utils.atomic_write import atomic_write_json, safe_read_json  # noqa: E402
from api.subscriptions import SubscriptionStore  # noqa: E402

LOG = logging.getLogger("nspim.push.worker")

POLICIES_FILE = REPO_ROOT / "data" / "policies.json"
SEEN_FILE = REPO_ROOT / "data" / ".push_seen.json"
SUBSCRIPTIONS_FILE = REPO_ROOT / "data" / ".subscriptions.json"

# 单次循环最多推送多少条新政策 (防误操作"一次性灌入 100 条"刷屏)
MAX_BROADCAST_PER_TICK = 20
# 失败比例超过此阈值 → 走 OneSignal 兜底
FAIL_RATIO_FALLBACK = 0.5


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_seen_ids() -> set[str]:
    """读取上次推送过的 policy id 集合."""
    data = safe_read_json(SEEN_FILE, default={"ids": []})
    return set(data.get("ids", []) or [])


def save_seen_ids(ids: set[str, Any]) -> None:  # noqa: F821
    """落盘 seen ids (按时间倒序排列, 最多保留 500 个)."""
    ordered = sorted(ids, reverse=True)
    payload = {
        "version": "1.0",
        "updated_at": _utc_now_iso(),
        "ids": ordered[:500],
    }
    atomic_write_json(SEEN_FILE, payload, ensure_ascii=False, indent=2)


def load_policies() -> list[dict]:
    data = safe_read_json(POLICIES_FILE, default={"policies": []})
    return list(data.get("policies", []) or [])


def diff_new_policies(policies: list[dict], seen: set[str]) -> list[dict]:
    """返回未推送过的新政策 (按 publish_date 升序, 最新的最后)."""
    new_pols = [p for p in policies if p.get("id") and p["id"] not in seen]
    new_pols.sort(key=lambda p: p.get("publish_date", "") or "")
    return new_pols[-MAX_BROADCAST_PER_TICK:]


def make_payload(policy: dict) -> PushPayload:
    title = (policy.get("title") or "新政策入库")[:64]
    dept = policy.get("department", "—")
    doc_no = policy.get("doc_number") or ""
    pub = policy.get("publish_date", "")
    parts = [dept]
    if doc_no:
        parts.append(doc_no)
    if pub:
        parts.append(pub)
    body = " · ".join(parts)[:200]

    return PushPayload(
        title=title,
        body=body,
        url=policy.get("source_url"),
        tag=f"policy-{policy.get('id', 'unknown')}",
        require_interaction=False,
        data={"policy_id": policy.get("id"), "doc_number": policy.get("doc_number")},
    )


def broadcast_one(
    store: SubscriptionStore,
    payload: PushPayload,
) -> tuple[int, int, int, bool]:
    """广播单条政策. Returns (success, expired, error, fallback_triggered).

    fallback_triggered=True 表示 VAPID 配置错误 (调用方应尝试 OneSignal).
    """
    subs = store.list_active()
    if not subs:
        LOG.info("无活跃订阅, 跳过推送")
        return 0, 0, 0, False

    success = expired = error = 0
    fallback = False
    for record in subs:
        endpoint = record.get("endpoint", "")
        try:
            sub = PushSubscription.from_dict(record)
            if send_push(sub, payload):
                success += 1
            else:
                expired += 1
                store.mark_expired(endpoint)
        except SubscriptionExpired:
            expired += 1
            store.mark_expired(endpoint)
        except VAPIDConfigError as e:
            LOG.error("VAPID 配置错误, 停止 Web Push 链路: %s", e)
            error += 1
            fallback = True
            return success, expired, error, True
        except Exception as e:  # noqa: BLE001
            LOG.warning("推送失败 endpoint=%s: %s", endpoint[:60], e)
            store.increment_fail(endpoint)
            error += 1

    LOG.info("推送完成 success=%d expired=%d error=%d", success, expired, error)

    # 失败率高 → 触发 OneSignal 兜底 (若已配置)
    total = success + expired + error
    if total > 0 and (error + expired) / total >= FAIL_RATIO_FALLBACK:
        fallback = True

    return success, expired, error, fallback


def try_onesignal_fallback(policies: list[dict]) -> bool:
    """Web Push 链路故障时, 尝试 OneSignal 兜底. Returns 是否调用成功."""
    try:
        from utils.onesignal import is_configured, OneSignalNotification, send_notification, OneSignalError
    except ImportError as e:
        LOG.warning("OneSignal 模块导入失败: %s", e)
        return False
    if not is_configured():
        LOG.info("OneSignal 未配置, 无兜底")
        return False

    if not policies:
        return True

    p = policies[-1]  # 最新一条
    try:
        note = OneSignalNotification(
            heading=(p.get("title") or "新政策入库")[:64],
            contents={
                "zh": f"{p.get('department', '')} {p.get('doc_number') or ''} {p.get('publish_date', '')}".strip()[:200],
            },
            url=p.get("source_url"),
        )
        result = send_notification(note)
        LOG.info("OneSignal 兜底发送成功: %s", result.get("id") or result.get("recipients"))
        return True
    except OneSignalError as e:
        LOG.error("OneSignal 兜底失败: %s", e)
        return False


def run_once(*, onesignal_fallback: bool) -> int:
    """单次跑, Returns 0=OK / 1=有失败但非致命 / 2=VAPID 配置错误."""
    if not POLICIES_FILE.exists():
        LOG.warning("policies.json 不存在 @ %s, 跳过", POLICIES_FILE)
        return 0

    policies = load_policies()
    seen = load_seen_ids()
    new_pols = diff_new_policies(policies, seen)
    if not new_pols:
        LOG.info("无新政策需要推送 (total=%d, seen=%d)", len(policies), len(seen))
        return 0

    LOG.info("发现 %d 条新政策, 准备推送...", len(new_pols))

    store = SubscriptionStore(path=SUBSCRIPTIONS_FILE)
    if store.count_active() == 0:
        LOG.info("无活跃订阅, 只更新 seen_ids 不推送")
        seen.update(p["id"] for p in new_pols if p.get("id"))
        save_seen_ids(seen)
        return 0

    fatal_vapid = False
    for p in new_pols:
        payload = make_payload(p)
        success, expired, error, fallback = broadcast_one(store, payload)
        if fallback and onesignal_fallback:
            LOG.warning("Web Push 失败率高, 触发 OneSignal 兜底...")
            try_onesignal_fallback([p])
            if error > 0 and expired > success:
                # VAPID 错 — 不更新 seen (下次重试)
                if all(s.get("status") == "expired" for s in store.list_active()):
                    fatal_vapid = True

    # 更新 seen_ids (即使 VAPID 错也更新, 因为再重试还是同一个错)
    seen.update(p["id"] for p in new_pols if p.get("id"))
    save_seen_ids(seen)

    if fatal_vapid:
        return 2
    return 0


def run_loop(interval: float, *, onesignal_fallback: bool) -> int:
    LOG.info("进入守护模式, 轮询间隔 %.1fs", interval)
    last_mtime: Optional[float] = None
    while True:
        try:
            if POLICIES_FILE.exists():
                mtime = POLICIES_FILE.stat().st_mtime
                if last_mtime is None or mtime > last_mtime:
                    last_mtime = mtime
                    LOG.info("policies.json 变化 (mtime=%.0f), 触发推送...", mtime)
                    code = run_once(onesignal_fallback=onesignal_fallback)
                    if code == 2:
                        LOG.error("VAPID 配置错误, 退避后重试 (code=2)")
                else:
                    LOG.debug("policies.json 未变化 (mtime=%.0f)", mtime)
        except Exception as e:  # noqa: BLE001
            LOG.exception("循环异常: %s", e)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            LOG.info("收到 Ctrl-C, 退出")
            return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="NSP-IM Push Worker (policies.json → Web Push)")
    parser.add_argument(
        "--once",
        action="store_true",
        help="跑一次就退出 (CI 模式, GitHub Actions 用)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("PUSH_WORKER_INTERVAL", "60")),
        help="轮询间隔秒数 (仅守护模式生效, 默认 60s)",
    )
    parser.add_argument(
        "--no-onesignal-fallback",
        action="store_true",
        help="关闭 OneSignal 兜底 (默认: Web Push 失败率高时自动 fallback)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    onesignal_fallback = not args.no_onesignal_fallback

    if args.once:
        return run_once(onesignal_fallback=onesignal_fallback)
    return run_loop(args.interval, onesignal_fallback=onesignal_fallback)


if __name__ == "__main__":
    sys.exit(main())