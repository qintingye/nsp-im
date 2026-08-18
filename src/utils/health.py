"""
NSP-IM 健康探针 (B6 - W1-D3)
=============================

目标:
    监测 fetcher 的运行状态 (success/fail/latency/last_run)，
    供 daily-fetch CI 与本地调试判断"今天这次抓取是否健康"。

设计原则:
    1. 无外部依赖: 纯 Python 字典 + JSON, 不依赖 Redis/Prometheus 等
    2. 持久化轻量: 状态文件落在 data/health.json, 原子写入 (复用 atomic_write)
    3. 探针判定可解释: 给定一份"历史 + 这次"的数据, 能回答:
       - 这次是否成功?
       - 响应时间是否健康 (<threshold)?
       - 最近 24h 失败率是否过高 (>50%)?
       - 该 fetcher 是否"已经静默" (超过 48h 没运行)?
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from utils.atomic_write import atomic_write_json, safe_read_json


# ---------- 阈值常量（可被环境变量覆盖，简单起见写死） ----------
LATENCY_WARN_MS = 5_000          # 单次响应超过 5s 视为"慢"
LATENCY_FAIL_MS = 30_000         # 单次响应超过 30s 视为"失败"
FAIL_RATIO_ALERT = 0.5           # 最近窗口内失败率 > 50% 报警
STALE_HOURS = 48                 # 超过 48h 没跑视为"静默"


@dataclass
class FetcherHealth:
    """单个 fetcher 的健康状态。"""
    name: str
    success_count: int = 0
    fail_count: int = 0
    last_run_at: Optional[str] = None        # ISO 8601 UTC
    last_status: str = "unknown"             # success | fail | unknown
    last_latency_ms: Optional[float] = None
    last_error: Optional[str] = None
    total_latency_ms: float = 0.0

    @property
    def total_count(self) -> int:
        return self.success_count + self.fail_count

    @property
    def fail_ratio(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.fail_count / self.total_count

    @property
    def avg_latency_ms(self) -> Optional[float]:
        if self.success_count == 0:
            return None
        return self.total_latency_ms / self.success_count

    def is_alerting(self) -> bool:
        """是否处于报警态。"""
        if self.fail_ratio > FAIL_RATIO_ALERT and self.total_count >= 2:
            return True
        if self.last_status == "fail":
            return True
        if self.last_latency_ms and self.last_latency_ms > LATENCY_FAIL_MS:
            return True
        return False

    def is_stale(self, now: Optional[datetime] = None) -> bool:
        """是否超过 STALE_HOURS 没运行。"""
        if not self.last_run_at:
            return True
        now = now or datetime.now(timezone.utc)
        try:
            last = datetime.fromisoformat(self.last_run_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now - last).total_seconds() > STALE_HOURS * 3600


def record_run(
    state: dict[str, FetcherHealth],
    name: str,
    *,
    success: bool,
    latency_ms: float,
    error: Optional[str] = None,
    now: Optional[datetime] = None,
) -> FetcherHealth:
    """记录一次抓取结果到内存中的 health state。

    返回更新后的 FetcherHealth（调用方负责持久化）。
    """
    now = now or datetime.now(timezone.utc)
    h = state.get(name) or FetcherHealth(name=name)
    h.last_run_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    h.last_status = "success" if success else "fail"
    h.last_latency_ms = round(latency_ms, 2)
    h.last_error = error if not success else None
    if success:
        h.success_count += 1
        h.total_latency_ms += latency_ms
    else:
        h.fail_count += 1
    state[name] = h
    return h


def evaluate(h: FetcherHealth, now: Optional[datetime] = None) -> dict:
    """把一个 fetcher 的当前状态汇总为一份可读的探针报告。"""
    now = now or datetime.now(timezone.utc)
    return {
        "name": h.name,
        "status": h.last_status,
        "alerting": h.is_alerting(),
        "stale": h.is_stale(now),
        "fail_ratio": round(h.fail_ratio, 3),
        "avg_latency_ms": round(h.avg_latency_ms, 2) if h.avg_latency_ms is not None else None,
        "last_run_at": h.last_run_at,
        "last_error": h.last_error,
    }


def overall_summary(state: dict[str, FetcherHealth], now: Optional[datetime] = None) -> dict:
    """聚合所有 fetcher 的健康度，给 CI/上游一个总览。"""
    now = now or datetime.now(timezone.utc)
    evals = [evaluate(h, now) for h in state.values()]
    return {
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "fetcher_count": len(evals),
        "alerting_count": sum(1 for e in evals if e["alerting"]),
        "stale_count": sum(1 for e in evals if e["stale"]),
        "healthy": all(not e["alerting"] and not e["stale"] for e in evals) if evals else True,
        "fetchers": evals,
    }


# ---------- 持久化 ----------
def load_state(path: str | Path) -> dict[str, FetcherHealth]:
    """从磁盘加载历史 health state；文件不存在/损坏则返回空 state。"""
    raw = safe_read_json(path, default={"fetchers": {}})
    items = raw.get("fetchers", {}) if isinstance(raw, dict) else {}
    out: dict[str, FetcherHealth] = {}
    for name, blob in items.items():
        if not isinstance(blob, dict):
            continue
        try:
            out[name] = FetcherHealth(
                name=name,
                success_count=int(blob.get("success_count", 0)),
                fail_count=int(blob.get("fail_count", 0)),
                last_run_at=blob.get("last_run_at"),
                last_status=blob.get("last_status", "unknown"),
                last_latency_ms=blob.get("last_latency_ms"),
                last_error=blob.get("last_error"),
                total_latency_ms=float(blob.get("total_latency_ms", 0.0)),
            )
        except (TypeError, ValueError):
            # 损坏的单条记录直接跳过，不阻塞其他 fetcher
            continue
    return out


def save_state(path: str | Path, state: dict[str, FetcherHealth]) -> Path:
    """把 state 原子写入磁盘。"""
    payload = {
        "version": "1.0",
        "fetchers": {name: asdict(h) for name, h in state.items()},
    }
    return atomic_write_json(path, payload, ensure_ascii=False, indent=2)


# ---------- 探针包装器 ----------
def timed_run(name: str, state_path: str | Path):
    """上下文管理器/装饰器: 包裹一次 fetcher 调用，自动 record & 持久化 health。

    用法 (装饰器):
        @timed_run("ndrc", "data/health.json")
        async def run_ndrc():
            ...

    用法 (with):
        with timed_run("ndrc", "data/health.json") as probe:
            ...抓取逻辑...
        # probe.elapsed_ms 自动记录 + 写盘
    """
    # 实现见 HealthProbe 类（更易测试）
    return _HealthProbe(name, state_path)


class _HealthProbe:
    """简易计时探针。

    设计成同时支持装饰器和 with 两种用法，避免给 fetcher 加复杂样板。
    """
    def __init__(self, name: str, state_path: str | Path):
        self.name = name
        self.state_path = Path(state_path)
        self.elapsed_ms: Optional[float] = None
        self._t0: float = 0.0
        self._state: dict[str, FetcherHealth] = {}

    def __enter__(self) -> "_HealthProbe":
        self._state = load_state(self.state_path)
        self._t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.elapsed_ms = (time.monotonic() - self._t0) * 1000.0
        success = exc_type is None
        err = None if success else f"{exc_type.__name__}: {exc}"
        record_run(
            self._state,
            self.name,
            success=success,
            latency_ms=self.elapsed_ms,
            error=err,
        )
        # 持久化失败不能阻塞主流程
        try:
            save_state(self.state_path, self._state)
        except OSError:
            pass


__all__ = [
    "FetcherHealth",
    "record_run",
    "evaluate",
    "overall_summary",
    "load_state",
    "save_state",
    "timed_run",
    "_HealthProbe",
    "LATENCY_WARN_MS",
    "LATENCY_FAIL_MS",
    "FAIL_RATIO_ALERT",
    "STALE_HOURS",
]