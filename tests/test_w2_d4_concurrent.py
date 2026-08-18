"""
W2-D4-BE · 并发抓取专项测试
============================

与 test_w2_d4.py 互补, 专注 W2-D4 三个核心验收点:
  1. 并发执行: 多个 fetcher 真正并行 (而非伪并发 / 串行)
  2. 限流 (Semaphore): 严格不超过设定并发上限
  3. 失败重试: 单源失败自动重试, 重试耗尽仍不阻断其他源

额外覆盖 W2-D4 CLI 升级:
  4. --all / --only / --sequential CLI 行为
  5. run_benchmark() speedup >= 2x

运行:
    .venv-d5/Scripts/python.exe -m pytest tests/test_w2_d4_concurrent.py -v
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import main_fetcher as mf  # noqa: E402
from fetchers.base import BaseFetcher  # noqa: E402


def _async_class(cls):
    cls.pytestmark = pytest.mark.asyncio
    return cls


# ============================================================
# FakeFetcher: 可控的并发测试夹具
# ============================================================
class ConcurrentFakeFetcher(BaseFetcher):
    """W2-D4 并发测试专用 fetcher。

    与 test_w2_d4.py 中的 FakeFetcher 区别:
      - 同时记录 start_time + end_time, 用于精确验证"真并行"
      - overlap_time(): 与其它 fetcher 的执行时间窗口重叠率
    """

    def __init__(
        self,
        name: str,
        *,
        sleep: float = 0.0,
        fail_first: int = 0,
        always_fail: bool = False,
        return_value: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name=name, source_url=f"https://fake/{name}")
        self.sleep = sleep
        self.fail_first = fail_first
        self.always_fail = always_fail
        self.return_value = return_value
        self.call_count = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.attempts_log: List[str] = []  # 每次调用记录 [start_iso, fail/success]

    async def fetch_raw(self):  # pragma: no cover
        return []

    def parse(self, raw):  # pragma: no cover
        return []

    async def run(self, *, health_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        self.call_count += 1
        self.start_time = time.monotonic()
        await asyncio.sleep(self.sleep)
        self.end_time = time.monotonic()
        self.attempts_log.append(f"{self.start_time:.4f}-{self.end_time:.4f}")

        if self.always_fail:
            raise RuntimeError(f"fake-{self.name}-always-fail")
        if self.call_count <= self.fail_first:
            raise RuntimeError(f"fake-{self.name}-transient (call {self.call_count})")
        return self.return_value if self.return_value is not None else {"added": 0, "total": 0, "duplicates": 0}


# ============================================================
# 1. 并发执行 (真正并行, 而非串行)
# ============================================================
@_async_class
class TestConcurrentExecution:
    async def test_five_sources_run_in_parallel(self):
        """5 个 fetcher 各睡 0.2s, 并发跑 → 总耗时应远小于 1.0s (5×0.2=1.0s).

        若串行执行总耗时 ≈ 1.0s, 并发执行应 < 0.6s (含调度开销).
        """
        fetchers = [
            ConcurrentFakeFetcher(f"src{i}", sleep=0.2,
                                  return_value={"added": i + 1, "total": i + 1, "duplicates": 0})
            for i in range(5)
        ]

        t0 = time.monotonic()
        coros = [mf._run_with_main_retry(f, max_retries=0) for f in fetchers]
        results = await mf._gather_with_semaphore(coros, concurrency=5)
        elapsed = time.monotonic() - t0

        # 全部成功
        assert len(results) == 5
        assert all(isinstance(r, dict) and not r.get("error") for r in results)
        # 总耗时 < 串行理论值 1.0s 的 70% (留 30% 调度开销)
        assert elapsed < 0.7, f"5 源各 0.2s 并发耗时 {elapsed:.3f}s, 接近串行"

        # 验证时间窗口重叠: 至少 3 个 fetcher 同时在跑
        events = sorted([(f.start_time, f.end_time, f.name) for f in fetchers])
        # 取第一个 end - 第一个 start 应该 < 0.4s (即有重叠)
        first_start = events[0][0]
        first_end = events[0][1]
        overlapping = sum(
            1 for s, e, _ in events
            if s < first_end + 0.05  # +0.05 容差
            and e > first_start
        )
        assert overlapping >= 3, f"并发度仅 {overlapping}, 应 >= 3"

    async def test_concurrent_results_order_preserved(self):
        """gather 的结果顺序必须与传入 coro 顺序一致 (即使完成时间不同)."""
        fetchers = [
            ConcurrentFakeFetcher(f"src{i}", sleep=0.01 * (5 - i),  # 越后面的 sleep 越短
                                  return_value={"added": i, "total": i, "duplicates": 0})
            for i in range(5)
        ]
        coros = [mf._run_with_main_retry(f, max_retries=0) for f in fetchers]
        results = await mf._gather_with_semaphore(coros, concurrency=5)

        # 顺序应保持: src0, src1, src2, src3, src4
        assert [r["added"] for r in results] == [0, 1, 2, 3, 4]


# ============================================================
# 2. 限流 (Semaphore 严格不超上限)
# ============================================================
@_async_class
class TestSemaphoreRateLimit:
    async def test_concurrency_2_with_5_sources(self):
        """concurrency=2 + 5 sources: 峰值并发必须 == 2."""
        peak = 0
        current = 0
        lock = asyncio.Lock()

        async def slow(n):
            nonlocal peak, current
            async with lock:
                current += 1
                peak = max(peak, current)
            await asyncio.sleep(0.05)
            async with lock:
                current -= 1
            return n

        coros = [slow(i) for i in range(5)]
        results = await mf._gather_with_semaphore(coros, concurrency=2)

        assert results == [0, 1, 2, 3, 4]
        assert peak == 2, f"concurrency=2 时峰值并发 {peak}, 超过限流"

    async def test_concurrency_1_is_sequential(self):
        """concurrency=1 时, 5 个源必须一个一个跑 (退化为串行)."""
        order: List[int] = []
        start_times: List[float] = []

        async def task(n):
            start_times.append(time.monotonic())
            order.append(n)
            await asyncio.sleep(0.05)
            return n

        coros = [task(i) for i in range(5)]
        t0 = time.monotonic()
        results = await mf._gather_with_semaphore(coros, concurrency=1)
        elapsed = time.monotonic() - t0

        # 顺序必须保持 (concurrency=1 等价串行)
        assert results == [0, 1, 2, 3, 4]
        assert order == [0, 1, 2, 3, 4]
        # 串行 5×0.05=0.25s, 但因为 asyncio 调度开销可能稍长
        assert elapsed >= 0.20, f"concurrency=1 耗时 {elapsed:.3f}s, 不像串行"
        # 起始时间必须递增 (前一个完成才开始下一个)
        for i in range(1, 5):
            assert start_times[i] > start_times[i - 1], "concurrency=1 应严格串行启动"

    async def test_concurrency_higher_than_sources_is_noop(self):
        """concurrency=10 但只有 3 个 source: 限流不应阻塞, 全部并发."""
        fetchers = [
            ConcurrentFakeFetcher(f"src{i}", sleep=0.05,
                                  return_value={"added": 1, "total": 1, "duplicates": 0})
            for i in range(3)
        ]
        coros = [mf._run_with_main_retry(f, max_retries=0) for f in fetchers]
        t0 = time.monotonic()
        results = await mf._gather_with_semaphore(coros, concurrency=10)
        elapsed = time.monotonic() - t0

        assert len(results) == 3
        # 全部并发 → 约 0.05s, 不该被限流拖到 0.10s+
        assert elapsed < 0.15, f"3 源 concurrency=10 应 < 0.15s, 实测 {elapsed:.3f}s"


# ============================================================
# 3. 失败重试 (单源失败不阻断其他源)
# ============================================================
@_async_class
class TestRetryBehavior:
    async def test_transient_failure_recovers_on_retry(self):
        """fail_first=1 → 第 1 次失败, 第 2 次成功 (测 main 层 retry)."""
        f = ConcurrentFakeFetcher("transient", fail_first=1,
                                  return_value={"added": 3, "total": 3, "duplicates": 0})
        r = await mf._run_with_main_retry(f, max_retries=2)

        assert r == {"added": 3, "total": 3, "duplicates": 0}
        assert f.call_count == 2, f"应尝试 2 次, 实测 {f.call_count}"
        assert len(f.attempts_log) == 2

    async def test_exhausted_retries_returns_error_not_raises(self):
        """max_retries=2 + always_fail → 跑 3 次后返回 error dict, 不抛异常."""
        f = ConcurrentFakeFetcher("always_fail", always_fail=True)
        r = await mf._run_with_main_retry(f, max_retries=2)

        assert isinstance(r, dict)
        assert "error" in r
        assert r["added"] == 0
        assert r["total"] == 0
        assert "always-fail" in r["error"]
        assert f.call_count == 3

    async def test_one_fetcher_failure_does_not_block_others_in_gather(self):
        """5 个 fetcher 中 1 个 always_fail, 其它 4 个必须照常成功."""
        fetchers = [
            ConcurrentFakeFetcher("good_a", sleep=0.05,
                                  return_value={"added": 1, "total": 1, "duplicates": 0}),
            ConcurrentFakeFetcher("bad_b", sleep=0.05, always_fail=True),
            ConcurrentFakeFetcher("good_c", sleep=0.05,
                                  return_value={"added": 2, "total": 2, "duplicates": 0}),
            ConcurrentFakeFetcher("good_d", sleep=0.05,
                                  return_value={"added": 3, "total": 3, "duplicates": 0}),
            ConcurrentFakeFetcher("good_e", sleep=0.05,
                                  return_value={"added": 4, "total": 4, "duplicates": 0}),
        ]
        coros = [mf._run_with_main_retry(f, max_retries=0) for f in fetchers]
        results = await mf._gather_with_semaphore(coros, concurrency=5)

        assert len(results) == 5
        # 4 个好源成功
        good_results = [r for r in results if isinstance(r, dict) and not r.get("error")]
        assert len(good_results) == 4
        # 1 个坏源返回 error dict (而非异常, 因为 _run_with_main_retry 已吞)
        bad_results = [r for r in results if isinstance(r, dict) and r.get("error")]
        assert len(bad_results) == 1
        assert "always-fail" in bad_results[0]["error"]

        # 验证 4 个好源都跑过 (没被坏源拖累)
        assert fetchers[0].call_count == 1
        assert fetchers[2].call_count == 1
        assert fetchers[3].call_count == 1
        assert fetchers[4].call_count == 1


# ============================================================
# 4. run_benchmark() 性能对比
# ============================================================
@_async_class
class TestBenchmark:
    async def test_benchmark_speedup_at_least_2x(self):
        """run_benchmark 默认 5 源 × 0.3s sleep, 并发应至少 2x 加速."""
        result = await mf.run_benchmark(concurrency=5, max_retries=0, per_source_sleep=0.2)

        assert result["n_sources"] == 5
        assert result["sequential_ok_count"] == 5
        assert result["concurrent_ok_count"] == 5

        # 串行理论值: 5 × 0.2 = 1.0s
        assert result["sequential_s"] >= 0.9, f"串行耗时 {result['sequential_s']:.3f}s, 偏短"
        # 并发理论值: 1×0.2 = 0.2s (5 源全并发)
        assert result["concurrent_s"] < 0.6, f"并发耗时 {result['concurrent_s']:.3f}s, 像串行"
        # 加速比 >= 2x
        assert result["speedup"] >= 2.0, f"加速比 {result['speedup']:.2f}x 不达标"


# ============================================================
# 5. CLI 升级 (--all / --only / --sequential)
# ============================================================
class TestCLI:
    def test_help_includes_new_flags(self):
        """main_fetcher --help 必须列出 --all / --only / --sequential / --benchmark."""
        py = ROOT / ".venv-d5" / "Scripts" / "python.exe"
        r = subprocess.run(
            [str(py), "-m", "src.main_fetcher", "--help"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30,
        )
        out = r.stdout + r.stderr
        assert "--all" in out
        assert "--only" in out
        assert "--concurrent" in out
        assert "--sequential" in out
        assert "--benchmark" in out

    def test_only_env_var_overrides(self, monkeypatch):
        """--only ndrc 应把环境变量 FETCHERS 设为 ndrc."""
        # main() 里 os.environ 赋值, 这里测环境变量赋值后 _build_fetchers 的行为
        monkeypatch.setenv("FETCHERS", "")
        monkeypatch.setenv("FETCHERS", "ndrc")  # 模拟 --only 已生效
        fetchers = mf._build_fetchers()
        names = [f.name for f in fetchers]
        assert "发改委" in names
        # 其他源应被排除
        assert len(names) == 1, f"--only ndrc 应只启 1 源, 实测 {names}"

    def test_demo_still_works(self):
        """W1-D4 的 --demo 子命令在 CLI 升级后仍可用 (回归)."""
        py = ROOT / ".venv-d5" / "Scripts" / "python.exe"
        r = subprocess.run(
            [str(py), "-m", "src.main_fetcher", "--demo"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30,
        )
        assert r.returncode == 0, f"--demo 退出码 {r.returncode}: {r.stderr}"
        assert "demo" in r.stdout.lower() or "demo" in r.stderr.lower() or "✅" in r.stdout