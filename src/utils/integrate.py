"""
NSP-IM 集成工具 (W1-D4)
========================

把 atomic_write / health / dedup 三个工具串成一个高阶 API，供 main_fetcher.py
及后续 fetcher 复用。

设计目标：
    1. 一行完成"fetch + dedup + save + health record"——上层只关心业务逻辑
    2. 任何环节异常都不影响 health.json / 日志落地
    3. 装饰器 + with-stmt 两种使用形态都支持，灵活兼容同步/异步 fetcher
    4. 不引入新依赖，复用 utils.{atomic_write, health, dedup}

模块暴露的高阶 API：
    - fetch_with_health(name, health_path, prefer='freshest')
        装饰器: 包裹一次 fetcher.run() 调用，自动 health + 持久化
    - integrated_fetch(name, raw_items, *, target_path, health_path, ...)
        函数式: 把抓取结果（含脏数据）→ dedup → atomic write → health record
    - IntegratedPipeline(name, target_path, health_path)
        上下文管理器: 更细粒度的控制（适合多 fetcher pipeline）
    - run_integration_demo(...)
        自检 demo: 生成 5 条 demo policy，写入 data/policies.json，便于离线烟测
"""

from __future__ import annotations

import asyncio
import functools
import json
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

# 让 `python -m src.utils.integrate` / 直接执行 / import 都能找到 utils 包
_THIS = Path(__file__).resolve()
_SRC_DIR = _THIS.parents[1]  # src/
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from utils.atomic_write import atomic_write_json, safe_read_json  # noqa: E402
from utils.dedup import deduplicate  # noqa: E402
from utils.health import (  # noqa: E402
    _HealthProbe,
    load_state,
    save_state,
    record_run,
    overall_summary,
)


# ---------- 装饰器：fetch_with_health ----------
def fetch_with_health(
    name: str,
    health_path: Union[str, Path],
    *,
    prefer: str = "freshest",
    target_path: Optional[Union[str, Path]] = None,
):
    """装饰器：包裹一次 fetcher.run()，自动 health + dedup + atomic save。

    用法（fetcher 直接装饰）::

        @fetch_with_health("ndrc", "data/health.json")
        async def run_ndrc():
            ...抓取逻辑... return policies
            # 返回 dict 或 list 均可；dict 应包含 'policies' key

    Args:
        name: fetcher 名称（写入 health.json 用）
        health_path: health.json 路径
        prefer: dedup 偏好，'freshest' 或 'first'
        target_path: policies.json 路径；为 None 则跳过 save
    """

    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                t0 = time.monotonic()
                success = False
                err: Optional[str] = None
                result: Any = None
                try:
                    result = await fn(*args, **kwargs)
                    success = True
                    return result
                except Exception as e:  # noqa: BLE001
                    err = f"{type(e).__name__}: {e}"
                    raise
                finally:
                    elapsed_ms = (time.monotonic() - t0) * 1000.0
                    _persist_health(name, health_path, success, elapsed_ms, err)

            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            t0 = time.monotonic()
            success = False
            err: Optional[str] = None
            result: Any = None
            try:
                result = fn(*args, **kwargs)
                success = True
                return result
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {e}"
                raise
            finally:
                elapsed_ms = (time.monotonic() - t0) * 1000.0
                _persist_health(name, health_path, success, elapsed_ms, err)

        return sync_wrapper

    return decorator


def _persist_health(
    name: str,
    health_path: Union[str, Path],
    success: bool,
    latency_ms: float,
    error: Optional[str],
) -> None:
    """把一次抓取结果写入 health.json（best-effort，失败不抛）。"""
    try:
        state = load_state(health_path)
        record_run(state, name, success=success, latency_ms=latency_ms, error=error)
        save_state(health_path, state)
    except OSError as e:  # noqa: BLE001
        import sys
        print(f"[integrate] health 写盘失败 ({name}): {e}", file=sys.stderr)


# ---------- 函数式：integrated_fetch ----------
def integrated_fetch(
    name: str,
    raw_items: Iterable[Dict[str, Any]],
    *,
    target_path: Union[str, Path],
    health_path: Union[str, Path],
    prefer: str = "freshest",
) -> Dict[str, Any]:
    """一步完成 dedup + atomic save + health record。

    Args:
        name: fetcher 名称
        raw_items: 本次抓取到的 policy 列表（允许脏数据）
        target_path: policies.json 输出路径
        health_path: health.json 路径
        prefer: dedup 偏好

    Returns:
        {"added": N, "total": N, "duplicates": N, "path": str, "dedup_stats": {...}}
    """
    t0 = time.monotonic()
    target = Path(target_path)
    hpath = Path(health_path)

    # 1. 读旧
    existing = safe_read_json(target, default={"version": "1.0", "policies": []})
    if not isinstance(existing, dict):
        existing = {"version": "1.0", "policies": []}
    existing_policies = existing.get("policies", [])
    if not isinstance(existing_policies, list):
        existing_policies = []

    # 2. dedup (旧 + 新 一起丢进 dedup，按 prefer 保留最新/最早)
    merged = list(existing_policies) + list(raw_items or [])
    result = deduplicate(merged, prefer=prefer)
    unique = result["unique"]
    dup_stats = result["stats"]

    # 3. atomic write
    out = dict(existing)
    out["version"] = existing.get("version", "1.0")
    out["policies"] = unique
    out["generated_at"] = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    atomic_write_json(target, out, ensure_ascii=False, indent=2)

    added = max(0, len(unique) - len(existing_policies))
    duplicates_dropped = dup_stats.get("removed_by_id", 0) + dup_stats.get("removed_by_url", 0)

    # 4. health 写盘
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    _persist_health(name, hpath, success=True, latency_ms=elapsed_ms, error=None)

    return {
        "added": added,
        "total": len(unique),
        "duplicates": duplicates_dropped,
        "path": str(target),
        "dedup_stats": dup_stats,
        "latency_ms": round(elapsed_ms, 2),
    }


# ---------- 上下文管理器：IntegratedPipeline ----------
@contextmanager
def IntegratedPipeline(name: str, health_path: Union[str, Path]):
    """精细控制的上下文管理器：进入时计时，退出时自动写 health。

    适合 fetcher 内部需要分阶段执行的场景::

        with IntegratedPipeline("ndrc", "data/health.json") as p:
            raw = await fetch()
            policies = parse(raw)
            p.set_result(policies)
        # 退出后自动 health 记录 + 持久化
    """
    t0 = time.monotonic()
    state: Dict[str, Any] = {"name": name, "items": None, "error": None}
    try:
        yield _PipelineState(state)
        elapsed = (time.monotonic() - t0) * 1000.0
        success = state["error"] is None
        _persist_health(name, health_path, success, elapsed, state["error"])
    except Exception as e:  # noqa: BLE001
        elapsed = (time.monotonic() - t0) * 1000.0
        err = f"{type(e).__name__}: {e}"
        _persist_health(name, health_path, False, elapsed, err)
        raise


class _PipelineState:
    """IntegratedPipeline 暴露给 with-block 的句柄。"""

    def __init__(self, state: Dict[str, Any]) -> None:
        self._state = state

    def set_result(self, items: Iterable[Dict[str, Any]]) -> None:
        """把本轮抓取结果塞入状态；退出 with 时一并写 health。"""
        self._state["items"] = list(items or [])

    def set_error(self, error: str) -> None:
        """显式标记本轮失败（不抛异常也能落 health=fail）。"""
        self._state["error"] = error


# ---------- 自检 Demo ----------
DEMO_POLICIES: List[Dict[str, Any]] = [
    {
        "id": "P-NDRC-20260818-0001",
        "title": "《关于算电协同六网融合的指导意见（示范版）》",
        "department": "国家发改委",
        "doc_number": "发改能源〔2026〕999号",
        "publish_date": "2026-08-18",
        "effective_date": "2026-09-01",
        "category": "policy",
        "scope": ["compute", "grid", "monitor"],
        "priority": 1,
        "summary": "推动算力、电力、数据等多网融合，构建新型基础设施体系。",
        "key_points": ["算电协同", "六网融合", "示范先行"],
        "source_url": "https://www.ndrc.gov.cn/demo/202608/t20260818_demo.html",
        "captured_at": "2026-08-18T08:30:00Z",
        "captured_by": "integrate-demo-v1.0",
        "tags": ["算电协同", "六网"],
        "review_status": "pending",
    },
    {
        "id": "P-MWR-20260817-0002",
        "title": "《城市供水管网 DMA 分区计量推广方案》",
        "department": "水利部",
        "doc_number": "水规计〔2026〕88号",
        "publish_date": "2026-08-17",
        "effective_date": "2026-10-01",
        "category": "policy",
        "scope": ["water", "monitor"],
        "priority": 2,
        "summary": "推广 DMA 分区计量，目标 2030 漏损率 < 8%。",
        "key_points": ["DMA 分区", "漏损治理"],
        "source_url": "https://www.mwr.gov.cn/demo/202608/t20260817_demo.html",
        "captured_at": "2026-08-18T08:30:00Z",
        "captured_by": "integrate-demo-v1.0",
        "tags": ["供水", "DMA"],
        "review_status": "pending",
    },
    {
        "id": "P-MIIT-20260816-0003",
        "title": "《数据中心绿电直供实施细则》",
        "department": "工信部",
        "doc_number": "工信部节〔2026〕77号",
        "publish_date": "2026-08-16",
        "effective_date": "2026-09-15",
        "category": "policy",
        "scope": ["compute", "grid"],
        "priority": 1,
        "summary": "明确数据中心绿电直供的并网、计量、碳核算流程。",
        "key_points": ["绿电直供", "并网", "碳核算"],
        "source_url": "https://www.miit.gov.cn/demo/202608/t20260816_demo.html",
        "captured_at": "2026-08-18T08:30:00Z",
        "captured_by": "integrate-demo-v1.0",
        "tags": ["数据中心", "绿电"],
        "review_status": "pending",
    },
    {
        "id": "P-MIIT-20260815-0004",
        "title": "《5G+工业互联网融合应用指南》",
        "department": "工信部",
        "doc_number": "工信部信管〔2026〕66号",
        "publish_date": "2026-08-15",
        "effective_date": "2026-09-01",
        "category": "policy",
        "scope": ["telecom"],
        "priority": 3,
        "summary": "5G + 工业互联网在六大行业的落地路径。",
        "key_points": ["5G", "工业互联网"],
        "source_url": "https://www.miit.gov.cn/demo/202608/t20260815_demo.html",
        "captured_at": "2026-08-18T08:30:00Z",
        "captured_by": "integrate-demo-v1.0",
        "tags": ["5G", "工业"],
        "review_status": "pending",
    },
    {
        "id": "P-NDRC-20260814-0005",
        "title": "《国家级算力枢纽节点建设方案》",
        "department": "国家发改委",
        "doc_number": "发改高技〔2026〕55号",
        "publish_date": "2026-08-14",
        "effective_date": "2026-10-01",
        "category": "policy",
        "scope": ["compute", "monitor"],
        "priority": 1,
        "summary": "8 个国家级算力枢纽节点布局，明确 PUE、绿电比例要求。",
        "key_points": ["算力枢纽", "PUE", "绿电"],
        "source_url": "https://www.ndrc.gov.cn/demo/202608/t20260814_demo.html",
        "captured_at": "2026-08-18T08:30:00Z",
        "captured_by": "integrate-demo-v1.0",
        "tags": ["算力枢纽", "PUE"],
        "review_status": "pending",
    },
]


def run_integration_demo(
    *,
    target_path: Union[str, Path] = "data/policies.json",
    health_path: Union[str, Path] = "data/health.json",
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """离线 demo：把 5 条 demo policy + 已有 policies 合并去重写盘。

    用途：
      - CI / 本地烟测，无需联网即可验证 integrate.py 串联 OK
      - 部署预览（docs/preview/data/policies.json）的种子数据源

    Returns:
        integrated_fetch 的返回 dict
    """
    log = log or (lambda msg: print(msg))

    log(f"[demo] target={target_path}  health={health_path}")
    log(f"[demo] 注入 {len(DEMO_POLICIES)} 条 demo policies（含重复 id 测试）")

    # 故意加一条重复 id，验证 dedup 真的会工作
    items_with_dup = list(DEMO_POLICIES) + [dict(DEMO_POLICIES[0])]

    res = integrated_fetch(
        name="integrate-demo",
        raw_items=items_with_dup,
        target_path=target_path,
        health_path=health_path,
        prefer="freshest",
    )

    log(
        f"[demo] ✅ +{res['added']} total={res['total']} "
        f"dup={res['duplicates']} latency={res['latency_ms']}ms"
    )

    # 健康总览
    try:
        state = load_state(health_path)
        summary = overall_summary(state)
        log(
            f"[demo] health: {summary['fetcher_count']} fetcher, "
            f"{summary['alerting_count']} alerting, "
            f"{summary['stale_count']} stale, "
            f"healthy={summary['healthy']}"
        )
    except Exception as e:  # noqa: BLE001
        log(f"[demo] health summary 失败: {e}")

    return res


# ---------- CLI ----------
def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="NSP-IM 集成自检 demo")
    ap.add_argument(
        "--target",
        default="data/policies.json",
        help="policies.json 输出路径（相对仓库根或绝对）",
    )
    ap.add_argument(
        "--health",
        default="data/health.json",
        help="health.json 路径",
    )
    ap.add_argument(
        "--repo-root",
        default=".",
        help="仓库根（用于把相对路径锚定）",
    )
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    target = repo_root / args.target
    health = repo_root / args.health
    target.parent.mkdir(parents=True, exist_ok=True)
    health.parent.mkdir(parents=True, exist_ok=True)

    run_integration_demo(target_path=target, health_path=health)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())


__all__ = [
    "fetch_with_health",
    "integrated_fetch",
    "IntegratedPipeline",
    "run_integration_demo",
    "DEMO_POLICIES",
]