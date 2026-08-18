"""
NSP-IM 主抓取器（每日 09:00 调度）

W1-D4 BE 改动 (P0-1 + 健康/去重/原子写入集成):
  - P0-1 修复: 在 basicConfig 之前先 mkdir(parents=True, exist_ok=True),
                保证 logs/fetcher.log 在模块导入期即可创建
  - 把 W1_FETCHERS 改为配置驱动: 通过环境变量 (FETCHER_*_ENABLED) 启停各源
  - 跑完后自动 commit data/ (调用 scripts/git_commit_data.py)
  - 探针健康总览打印 (overall_summary)

W1-D4 集成改动:
  - fetch_with_health 装饰器: 包裹 fetcher.run() 自动写 health.json
  - integrated_fetch: dedup + atomic save + health 一步到位
  - --demo 子命令: 离线生成 5 条 demo policy 写入 data/policies.json

W2-D4 BE 改动（并发调度升级）:
  - 串行 for-loop → asyncio.gather 并发
  - 限流：asyncio.Semaphore（默认并发 3，可通过 FETCHER_CONCURRENCY 覆盖）
  - 失败重试：main 层在 BaseFetcher 内置 3 次指数退避之上，再补 1 次快速重试
    （仅当 BaseFetcher 整轮抛异常时触发；base 层已吃掉瞬时网络抖动，这里只兜
    "整批 3 次都失败" 的极端场景，避免单源永久卡住 main 退出）
  - return_exceptions=True: 一个源抛异常不阻断其他源
  - 保留对外契约: main_async() -> int、CLI --demo / 无参走全流程

W2-D4 CLI 扩展（CLI 升级）:
  - --all               显式跑全部 5 源（与无参等价，但显式更清楚）
  - --only ndrc,nea,...  只跑指定源（FETCHERS 环境变量也保留）
  - --concurrent        强制并发模式（默认）
  - --sequential        串行模式（关闭 gather，逐个 await），用于性能对比
  - --benchmark         仅做 5 源 concurrent vs sequential 性能对比，不写入 data/
"""
import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# 让 src.utils 可被直接 import
_THIS = Path(__file__).resolve()
# src/main_fetcher.py → parents[0]=src, parents[1]=nsp-im
SRC_DIR = _THIS.parent
REPO_ROOT = _THIS.parents[1]
SRC_DIR_STR = str(SRC_DIR)
if SRC_DIR_STR not in sys.path:
    sys.path.insert(0, SRC_DIR_STR)
# utils 在 src/utils/ 下, 不是 src 包内, 需要把 src/ 加入 sys.path
REPO_SRC_STR = str(REPO_ROOT / "src")
if REPO_SRC_STR not in sys.path and REPO_SRC_STR != SRC_DIR_STR:
    sys.path.insert(0, REPO_SRC_STR)

# ---------- P0-1 修复: logging 配置必须在 mkdir 之后才能创建 FileHandler ----------
LOGS_DIR = REPO_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)  # 先建目录
POLICIES_DIR = REPO_ROOT / "data"
POLICIES_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "fetcher.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("nsp-im")

# W1 启用: ndrc 一个, nea 是 W2-D1 新增
from fetchers.ndrc import NdrcFetcher  # noqa: E402
from fetchers.nea import NeaFetcher  # noqa: E402
from fetchers.base import BaseFetcher  # noqa: E402  # W2-D4 run_benchmark 内部 subclass 用

# W2-D2 / W2-D3 接入: csg / sgcc / bjx 全部就位
try:
    from fetchers.csg import CsgFetcher  # noqa: E402
except ImportError:
    CsgFetcher = None  # type: ignore[assignment]
try:
    from fetchers.sgcc import SgccFetcher  # noqa: E402
except ImportError:
    SgccFetcher = None  # type: ignore[assignment]
try:
    from fetchers.bjx import BjxFetcher  # noqa: E402
except ImportError:
    BjxFetcher = None  # type: ignore[assignment]

# W1-D4 集成: utils.{integrate, health, dedup, atomic_write}
from utils.integrate import (  # noqa: E402
    fetch_with_health,
    integrated_fetch,
    run_integration_demo,
)
from utils.health import load_state, overall_summary  # noqa: E402

W1_FETCHERS_ENV_KEY = "FETCHERS"  # 逗号分隔, 例: "ndrc,nea,csg"; 空/未设置 = 全部启用
FETCHER_CONCURRENCY_ENV_KEY = "FETCHER_CONCURRENCY"  # 并发上限, 默认 3
FETCHER_RETRY_ENV_KEY = "FETCHER_RETRY"  # main 层额外重试次数, 默认 1 (0 = 关)

# alias -> fetcher class 的注册表 (W2-D4 把分散 if-elif 改成统一注册)
FETCHER_REGISTRY: dict = {
    "ndrc": (NdrcFetcher, "发改委"),
    "nea": (NeaFetcher, "能源局"),
    "csg": (CsgFetcher, "南网"),
    "sgcc": (SgccFetcher, "国网"),
    "bjx": (BjxFetcher, "北极星"),
}


def _parse_int_env(key: str, default: int, *, min_val: int = 1, max_val: int = 64) -> int:
    """读取 int 类环境变量, 非法值兜底回 default, 越界 clamp 到 [min, max]。"""
    raw = os.environ.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        v = int(raw.strip())
    except ValueError:
        logger.warning(f"⚠️ 环境变量 {key}={raw!r} 非整数, 退回默认值 {default}")
        return default
    if v < min_val:
        logger.warning(f"⚠️ 环境变量 {key}={v} 小于下限 {min_val}, clamp 到 {min_val}")
        return min_val
    if v > max_val:
        logger.warning(f"⚠️ 环境变量 {key}={v} 大于上限 {max_val}, clamp 到 {max_val}")
        return max_val
    return v


def _build_fetchers() -> list:
    """按环境变量 (FETCHERS=ndrc,nea) 决定启用哪些 fetcher。

    W2-D4 改造: 5 源全部可注册; FETCHERS 为空或未设置时 = 启用全部已注册源。
    """
    raw = os.environ.get(W1_FETCHERS_ENV_KEY, "").strip()
    if raw:
        keys = [s.strip() for s in raw.split(",") if s.strip()]
    else:
        keys = list(FETCHER_REGISTRY.keys())

    fetchers = []
    for key in keys:
        entry = FETCHER_REGISTRY.get(key)
        if entry is None:
            logger.warning(f"⏭ Fetcher '{key}' 未注册, 已忽略")
            continue
        cls, alias = entry
        if cls is None:
            logger.warning(f"⏭ Fetcher '{key}' (别名 {alias}) 模块未导入, 已忽略")
            continue
        try:
            fetchers.append(cls())
        except Exception as e:  # noqa: BLE001
            logger.warning(f"⏭ Fetcher '{key}' (别名 {alias}) 实例化失败: {e}")
    return fetchers


def _commit_data_now() -> bool:
    """抓取跑完后调用一次 git_commit_data 自动提交 data/。

    用法: main_fetcher 末尾调用即可, 失败不阻塞抓取主流程。
    """
    try:
        # scripts/git_commit_data.py 是项目脚本; 直接调用其 main()
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from git_commit_data import main as git_commit_main  # type: ignore
        import argparse
        rc = git_commit_main(argparse.Namespace(
            commit_msg=f"auto: W1-D4 数据更新 {datetime.now().strftime('%Y-%m-%d')}",
            auto=True,
            dry_run=False,
            allow_dirty=False,
            repo=REPO_ROOT,
        ))
        return rc == 0
    except Exception as e:
        logger.warning(f"⚠️ 自动 git commit 失败 (不影响本次抓取): {e}")
        return False


# W1-D4: 把 fetcher.run() 用 fetch_with_health 装饰，让 health 自动落盘
# 这里用 lambda 包装是为了不动 fetchers/* 代码也可享受 health 装饰器
async def _run_one_fetcher(fetcher) -> dict:
    """运行单个 fetcher。内部已由 BaseFetcher.run() 集成 _HealthProbe，
    这里额外用 fetch_with_health 包裹一层，用于 main 流程的统一 health 报告。

    注意：这里返回 dict (可能为 None); 若抛异常则交给上层 gather(return_exceptions=True)。
    """
    hpath = str(POLICIES_DIR / "health.json")

    @fetch_with_health(fetcher.name, hpath)
    async def _inner():
        return await fetcher.run(health_path=hpath)

    return await _inner()


# ---------- W2-D4: 并发调度 + 限流 + 失败重试 ----------

async def _gather_with_semaphore(
    coros: list,
    *,
    concurrency: int = 3,
) -> list:
    """asyncio.gather + Semaphore 限流。

    Args:
        coros: 协程列表 (每个对应一个 fetcher.run())
        concurrency: 同一时刻最多并发几个

    Returns:
        list, 长度 == len(coros); 失败源对应位置是 Exception 实例 (return_exceptions=True)。

    行为契约:
        1. 单源失败不阻断其他源
        2. 全部 coros 一定会被 await（即便中途有异常）
        3. 限制峰值并发数，避免 5 源同时打外部被 ban
    """
    sem = asyncio.Semaphore(concurrency)

    async def _limited(coro_obj):
        async with sem:
            return await coro_obj

    return await asyncio.gather(*[_limited(c) for c in coros], return_exceptions=True)


async def _run_with_main_retry(
    fetcher,
    *,
    max_retries: int = 1,
) -> dict:
    """main 层给单个 fetcher 加一层快速 retry。

    与 base 层 fetch_with_retry 的区别:
        - base 层: 抓 raw 阶段内部 3 次指数退避 (2^n 秒)
        - main 层: 整轮 run() 失败的兜底, 默认再试 1 次 (轻量, 不退避)
        - 设计目的: base 层已吃掉瞬时网络抖动; main 层兜"整批 3 次都失败" 的极端场景

    Args:
        fetcher: BaseFetcher 实例
        max_retries: main 层额外重试次数, 0 表示关

    Returns:
        dict (fetcher.run() 的返回); 失败时返回 {"added": 0, "total": 0, "duplicates": 0, "error": str(e)}
    """
    last_err: Optional[BaseException] = None
    for attempt in range(max_retries + 1):
        try:
            r = await _run_one_fetcher(fetcher)
            if attempt > 0:
                logger.info(f"♻️ {fetcher.name} main-层 retry 成功 (第 {attempt + 1} 次)")
            return r if r is not None else {"added": 0, "total": 0, "duplicates": 0}
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < max_retries:
                logger.warning(f"⚠️ {fetcher.name} main-层 retry 第 {attempt + 1}/{max_retries} 次: {e}")
                # main 层 retry 不做指数退避（base 层已退避过），只做短 sleep 即可
                await asyncio.sleep(0.5)
            else:
                logger.error(f"❌ {fetcher.name} main-层重试 {max_retries} 次仍失败: {e}")
                return {"added": 0, "total": 0, "duplicates": 0, "error": str(e)}
    # 不可达, 仅补全类型
    return {"added": 0, "total": 0, "duplicates": 0, "error": str(last_err) if last_err else "unknown"}


async def _run_sequential(
    fetchers: list,
    *,
    max_retries: int = 1,
) -> list:
    """W2-D4 性能对比用：串行执行所有 fetcher (一个一个 await)。

    与 _gather_with_semaphore 的差异:
        - 本函数不并发: 等待前一个完成才开始下一个
        - 用于 `--benchmark` 与 `_gather_with_semaphore` 速度对比
        - 失败仍然不阻断后续源 (单源异常捕获后继续)

    Returns:
        list, 长度 == len(fetchers); 失败源对应位置是 Exception 实例。
    """
    results = []
    for f in fetchers:
        try:
            r = await _run_with_main_retry(f, max_retries=max_retries)
            results.append(r)
        except Exception as e:  # noqa: BLE001
            results.append(e)
    return results


async def run_benchmark(
    *,
    concurrency: int = 5,
    max_retries: int = 0,
    per_source_sleep: float = 0.3,
) -> dict:
    """W2-D4 性能对比: 5 源串行 vs 并发耗时。

    用本地 BenchFetcher (5 个各睡 per_source_sleep 秒) 跑两轮:
        - sequential: 一个一个跑, 总耗时 ≈ 5 × per_source_sleep
        - concurrent (Semaphore=concurrency): 总耗时 ≈ per_source_sleep + 排队开销

    返回 dict 含两轮耗时 + speedup 倍数, 供 CLI 输出与单测断言。

    设计: BenchFetcher 在这里本地定义 (不依赖 tests 包), 避免 tests/ 非 package 时 ImportError.
    """

    class BenchFetcher(BaseFetcher):
        def __init__(self, name: str, sleep: float):
            super().__init__(name=name, source_url=f"https://bench/{name}")
            self.sleep = sleep
            self.call_count = 0

        async def fetch_raw(self):  # pragma: no cover
            return []

        def parse(self, raw):  # pragma: no cover
            return []

        async def run(self, *, health_path=None):
            self.call_count += 1
            await asyncio.sleep(self.sleep)
            return {"added": 1, "total": 1, "duplicates": 0}

    fetchers = [
        BenchFetcher(f"bench_{i}", sleep=per_source_sleep)
        for i in range(5)
    ]

    # Sequential
    t0 = time.monotonic()
    seq_results = await _run_sequential(fetchers, max_retries=max_retries)
    seq_elapsed = time.monotonic() - t0

    # Concurrent (新一组 fetcher, 避免 call_count 污染)
    fetchers2 = [
        BenchFetcher(f"bench_{i}", sleep=per_source_sleep)
        for i in range(5)
    ]
    t0 = time.monotonic()
    coros = [_run_with_main_retry(f, max_retries=max_retries) for f in fetchers2]
    conc_results = await _gather_with_semaphore(coros, concurrency=concurrency)
    conc_elapsed = time.monotonic() - t0

    speedup = (seq_elapsed / conc_elapsed) if conc_elapsed > 0 else 1.0
    return {
        "sequential_s": seq_elapsed,
        "concurrent_s": conc_elapsed,
        "speedup": speedup,
        "concurrency": concurrency,
        "n_sources": len(fetchers),
        "per_source_sleep": per_source_sleep,
        "sequential_ok_count": sum(1 for r in seq_results if isinstance(r, dict) and not r.get("error")),
        "concurrent_ok_count": sum(1 for r in conc_results if isinstance(r, dict) and not r.get("error")),
    }


async def main_async(*, sequential: bool = False) -> int:
    logger.info(f"=== NSP-IM 抓取启动 {datetime.now().isoformat()} ===")
    fetchers = _build_fetchers()
    if not fetchers:
        logger.error("❌ 未配置任何 fetcher (检查环境变量 FETCHERS)")
        return 1

    concurrency = _parse_int_env(FETCHER_CONCURRENCY_ENV_KEY, default=3)
    retry = _parse_int_env(FETCHER_RETRY_ENV_KEY, default=1, min_val=0, max_val=5)
    mode_label = "串行" if sequential else "并发"
    logger.info(
        f"=== {mode_label}模式: {len(fetchers)} 个 fetcher, "
        f"并发上限 {concurrency}, main-层 retry {retry} 次 ==="
    )

    # 1. W2-D4: 并发抓取 (W1 串行 for-loop 替换为 gather + Semaphore 限流)
    # CLI --sequential 强制串行 (用于性能对比)
    if sequential:
        gathered = await _run_sequential(fetchers, max_retries=retry)
    else:
        coros = [_run_with_main_retry(f, max_retries=retry) for f in fetchers]
        gathered = await _gather_with_semaphore(coros, concurrency=concurrency)

    # 把结果对齐回 fetcher.name; gather 抛异常的位置是 Exception 实例
    results = []
    for fetcher, item in zip(fetchers, gathered):
        if isinstance(item, BaseException):
            logger.error(f"❌ {fetcher.name} gather 异常: {item}")
            results.append((
                fetcher.name,
                {"added": 0, "total": 0, "duplicates": 0, "error": f"{type(item).__name__}: {item}"},
            ))
        elif isinstance(item, dict):
            results.append((fetcher.name, item))
        else:
            # 防御: _run_with_main_retry 应该永远返回 dict; 非 dict 视为异常
            logger.error(f"❌ {fetcher.name} 返回非 dict 类型: {type(item).__name__}")
            results.append((fetcher.name, {"added": 0, "total": 0, "duplicates": 0, "error": f"unexpected return type {type(item).__name__}"}))

    # 2. 总结
    logger.info("=== 抓取结果 ===")
    total_added = 0
    for name, r in results:
        err = r.get("error") if isinstance(r, dict) else None
        added = r.get("added", 0) if isinstance(r, dict) else 0
        total = r.get("total", 0) if isinstance(r, dict) else 0
        status = "❌" if err else ("✅" if added > 0 else "⏭")
        msg = f"{status} {name}: +{added} (total {total})"
        if err:
            msg += f" — 错误: {err}"
        logger.info(msg)
        if not err:
            total_added += added

    # 3. health 探针总览
    try:
        state = load_state(POLICIES_DIR / "health.json")
        summary = overall_summary(state)
        logger.info(
            f"=== Health: {summary['fetcher_count']} fetcher, "
            f"{summary['alerting_count']} alerting, "
            f"{summary['stale_count']} stale ==="
        )
        if not summary["healthy"]:
            logger.warning(f"⚠️ 健康检查失败, 详情: {summary['fetchers']}")
    except Exception as e:
        logger.warning(f"⚠️ health 汇总失败: {e}")

    # 4. 自动 commit
    if total_added > 0:
        if _commit_data_now():
            logger.info("=== data/ 已自动 commit ===")
        else:
            logger.warning("=== 自动 commit 失败, 请人工检查 data/ ===")
    else:
        logger.info("=== 本次无新增政策, 跳过 git commit ===")

    logger.info(f"=== 总计 +{total_added} 新政策，程序退出 ===")
    return 0


def run_demo(log=logger.info) -> int:
    """W1-D4: --demo 子命令入口。离线生成 5 条 demo policy 写盘。"""
    target = POLICIES_DIR / "policies.json"
    health = POLICIES_DIR / "health.json"
    log(f"=== NSP-IM demo 模式启动 {datetime.now().isoformat()} ===")
    res = run_integration_demo(target_path=target, health_path=health, log=log)
    log(f"=== demo 完成 ✅ +{res['added']} total={res['total']} dup={res['duplicates']} ===")
    return 0


def main() -> int:
    """CLI 入口。

    支持子命令 / 模式:
        --demo                离线生成 demo policy 数据（无需联网）
        --all                 显式跑全部 5 源（与 FETCHERS= 空等价；默认行为）
        --only ndrc,nea,...   只跑指定源 (覆盖 FETCHERS 环境变量)
        --concurrent          并发模式（默认）
        --sequential          串行模式（关闭 gather，逐个 await），用于性能对比
        --benchmark           仅做 concurrent vs sequential 性能对比，不写 data/

    无参数 = 跑全部源, 并发模式 (与 --all --concurrent 等价).
    """
    ap = argparse.ArgumentParser(prog="nsp-im.main_fetcher", description="NSP-IM 主抓取器")
    ap.add_argument("--demo", action="store_true", help="离线生成 demo policy 数据（无需联网）")
    ap.add_argument("--all", dest="all_sources", action="store_true",
                    help="显式跑全部 5 源 (与无参等价, 但更显式)")
    ap.add_argument("--only", type=str, default=None, metavar="NAMES",
                    help="只跑指定源, 逗号分隔 (如 --only ndrc,nea; 覆盖 FETCHERS 环境变量)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--concurrent", dest="concurrent", action="store_true",
                      help="并发模式 (默认)")
    mode.add_argument("--sequential", dest="sequential", action="store_true",
                      help="串行模式 (逐个 await), 用于性能对比")
    ap.add_argument("--benchmark", action="store_true",
                    help="仅做 concurrent vs sequential 性能对比 (FakeFetcher, 不写 data/)")
    args = ap.parse_args()

    # 1. --demo 优先: 离线模式
    if args.demo:
        return run_demo()

    # 2. --benchmark: 跑 5 源 fake 数据, 输出 concurrent vs sequential 耗时
    if args.benchmark:
        result = asyncio.run(run_benchmark(concurrency=5, max_retries=0, per_source_sleep=0.3))
        print()
        print("=" * 60)
        print("📊 W2-D4 性能对比 (5 源 × 0.3s sleep)")
        print("=" * 60)
        print(f"⏱  串行模式: {result['sequential_s']:.2f}s ({result['sequential_ok_count']}/5 OK)")
        print(f"⏱  并发模式: {result['concurrent_s']:.2f}s ({result['concurrent_ok_count']}/5 OK)")
        print(f"🚀 加速比:   {result['speedup']:.2f}x")
        print("=" * 60)
        # speedup 写入日志便于 CI grep
        logger.info(f"📊 W2-D4 性能: 串行 {result['sequential_s']:.2f}s vs 并发 {result['concurrent_s']:.2f}s = {result['speedup']:.2f}x")
        return 0

    # 3. --only 覆盖 FETCHERS 环境变量
    if args.only:
        keys = ",".join(k.strip() for k in args.only.split(",") if k.strip())
        os.environ[W1_FETCHERS_ENV_KEY] = keys
        logger.info(f"--only {keys} → 覆盖 FETCHERS 环境变量")

    # 4. 模式: --sequential 走串行路径
    sequential = bool(args.sequential)
    if args.all_sources:
        logger.info(f"--all: 跑全部 {len(FETCHER_REGISTRY)} 个已注册源")

    return asyncio.run(main_async(sequential=sequential))


if __name__ == "__main__":
    sys.exit(main())