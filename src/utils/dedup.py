"""
NSP-IM 去重工具 (B5 - W1-D3)
=============================

目标:
    多个 fetcher (NDRC / 水利部 / 国资委 ...) 抓回来的 policy
    可能出现重复（同一条政策被两个源都收录，或同一源 7 天内重复抓回）。
    在写入 data/policies.json 之前必须去重。

去重键策略（优先级从高到低）:
    1) `id` 字段 (绝对权威: fetcher.parse() 必须保证同一政策 id 稳定)
    2) `source_url` 字段 (URL 归一化后比较, 兜底)

约束:
    - 不抛异常 (P0 容错: 输入脏数据不能阻塞写入)
    - 保留每组重复里的"最新"那一条 (按 `captured_at` / `publish_date` 排序)
    - 输出 dict: 包含 `unique` / `duplicates` / `stats`，便于上层 logging & 测试
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Iterable

# ---------- URL 归一化 ----------
_TRAILING_SLASH = re.compile(r"/+$")
_TRACKING_PARAMS = re.compile(r"[?&](utm_[a-z]+|fbclid|gclid|ref)=[^&]*", re.I)
_FRAGMENT = re.compile(r"#.*$")


def normalize_url(url: str | None) -> str | None:
    """把 URL 归一化到"忽略 scheme / www / 末尾斜杠 / utm 参数 / fragment"。

    返回 None 表示原始 URL 缺失或纯空白。
    """
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    # 去 fragment
    u = _FRAGMENT.sub("", u)
    # 去常见追踪参数（同时清理因移除而产生的孤立 ? 或 &）
    u = _TRACKING_PARAMS.sub("", u)
    # "?utm=...&b=1" 去掉 utm 后可能变成 "&b=1"; 把首个 & 提升为 ?
    if "&" in u and "?" not in u:
        idx = u.find("&")
        u = u[:idx] + "?" + u[idx + 1:]
    u = re.sub(r"\?&", "?", u)
    if u.endswith("?") or u.endswith("&"):
        u = u[:-1]
    # 去掉末尾 ?
    if u.endswith("?"):
        u = u[:-1]
    # scheme 小写化
    if "://" in u:
        scheme, rest = u.split("://", 1)
        u = scheme.lower() + "://" + rest
    # 去掉 www.
    u = re.sub(r"^(https?://)www\.", r"\1", u, flags=re.I)
    # host 小写
    m = re.match(r"^(https?://)([^/]+)(.*)$", u, re.I)
    if m:
        u = m.group(1) + m.group(2).lower() + m.group(3)
    # 末尾斜杠
    u = _TRAILING_SLASH.sub("", u)
    return u


# ---------- 时间字段抽取 ----------
_DATE_KEYS = ("captured_at", "publish_date", "effective_date", "generated_at")


def _pick_datetime(item: dict, key: str) -> datetime | None:
    val = item.get(key)
    if not val or not isinstance(val, str):
        return None
    s = val.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _freshness(item: dict) -> tuple[float, str]:
    """返回 (rank, source_key) 用于排序: 越大越新。

    rank = max(可解析的时间戳) + 一位小数的小次序号（同时间按 captured_at > publish_date > ...）。
    """
    # 优先 captured_at
    for i, key in enumerate(_DATE_KEYS):
        dt = _pick_datetime(item, key)
        if dt is not None:
            # captured_at 最权威 → 反转顺序让它权重最大
            return (dt.timestamp() * 1000, f"{i:02d}")
    return (0.0, "99")


# ---------- 主入口 ----------
def deduplicate(
    items: Iterable[dict[str, Any]],
    *,
    prefer: str = "freshest",
) -> dict[str, Any]:
    """对一组 policy dict 去重。

    Args:
        items: 待去重的 policy 列表（每个必须含 `id` 字段；URL 字段为可选）。
        prefer: 重复时保留策略 - "freshest" (按时间最新) 或 "first" (按顺序最先)。

    Returns:
        {
          "unique": [...],          # 去重后的列表
          "duplicates": [...],      # 被丢弃的条目 (含其被判重复的理由)
          "stats": {
             "input": N,
             "unique": N,
             "removed_by_id": N,
             "removed_by_url": N,
          }
        }
    """
    if prefer not in ("freshest", "first"):
        raise ValueError(f"prefer must be 'freshest' or 'first', got {prefer!r}")

    items = list(items)
    seen_ids: dict[str, dict] = {}
    seen_urls: dict[str, dict] = {}
    duplicates: list[dict[str, Any]] = []
    removed_by_id = 0
    removed_by_url = 0

    def _better(a: dict, b: dict) -> dict:
        if prefer == "first":
            return a  # 先来者保留
        # freshest: 取时间戳大的
        ta = _freshness(a)
        tb = _freshness(b)
        return a if ta >= tb else b

    for raw in items:
        if not isinstance(raw, dict):
            # 非法条目跳过（不抛）
            duplicates.append({"item": raw, "reason": "not-a-dict"})
            continue

        item = raw
        pid = raw.get("id")
        purl = normalize_url(raw.get("source_url"))

        # 1) id 命中
        if pid and pid in seen_ids:
            winner = _better(seen_ids[pid], raw)
            loser = raw if winner is seen_ids[pid] else seen_ids[pid]
            seen_ids[pid] = winner
            duplicates.append({"item": loser, "reason": "dup-id", "kept_id": pid})
            removed_by_id += 1
            # 如果 loser 有 url, 也要把 url 让出来
            loser_url = normalize_url(loser.get("source_url"))
            if loser_url and seen_urls.get(loser_url) is loser:
                seen_urls[loser_url] = winner
            continue

        # 2) url 命中 (仅当 id 不同)
        if purl and purl in seen_urls:
            winner = _better(seen_urls[purl], raw)
            loser = raw if winner is seen_urls[purl] else seen_urls[purl]
            seen_urls[purl] = winner
            # winner 的 id 是权威 id, 让 seen_ids 也对齐
            if winner.get("id"):
                seen_ids[winner["id"]] = winner
            duplicates.append({"item": loser, "reason": "dup-url", "kept_url": purl})
            removed_by_url += 1
            continue

        # 3) 新条目 → 注册
        if pid:
            seen_ids[pid] = item
        if purl:
            seen_urls[purl] = item

    # 汇总 unique = 每个 id 只取一条
    unique_by_id: dict[str, dict] = {}
    for pid, item in seen_ids.items():
        unique_by_id[pid] = item

    unique = list(unique_by_id.values())

    return {
        "unique": unique,
        "duplicates": duplicates,
        "stats": {
            "input": len(items),
            "unique": len(unique),
            "removed_by_id": removed_by_id,
            "removed_by_url": removed_by_url,
        },
    }


__all__ = ["deduplicate", "normalize_url"]