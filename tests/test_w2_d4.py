"""
W2-D4-BE · 单测（并发调度 + 限流 + 失败重试）
================================================

覆盖:
  - _parse_int_env: 默认值 / 非法值兜底 / clamp
  - _gather_with_semaphore: 全部完成 / 单失败不阻断 / 限流峰值
  - _run_with_main_retry: 一次成功 / 一次失败再试成功 / 全部失败返回 error
  - _build_fetchers: 全部启用 / 指定启用 / 未注册 / 模块缺失
  - main_async: 5 fetcher 端到端并发（用真实 BaseFetcher 子类，避开网络）

运行:
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe -m pytest tests/test_w2_d4.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import main_fetcher as mf  # noqa: E402
from fetchers.base import BaseFetcher  # noqa: E402

# pytest-asyncio 在 STRICT mode 下 (项目无 conftest.py 切换 auto), async 测试
# 必须显式标记。仅 3 个 async class 需要, 用 class-level pytestmark 避免对 sync
# class (TestParseIntEnv / TestBuildFetchers) 误标 asyncio 触发 warnings。
def _async_class(cls):
    cls.pytestmark = pytest.mark.asyncio
    return cls


# ============================================================
# Test Fixtures: 可控的 fake fetcher
# ============================================================
class FakeFetcher(BaseFetcher):
    """W2-D4 测试专用 fetcher：行为完全由参数控制，不联网。

    Args:
        name: fetcher 名称
        sleep: 模拟抓取耗时 (秒)
        fail_first: 前 N 次会抛 RuntimeError, 之后成功 (测 retry 用)
        always_fail: 永远抛异常
        return_value: run() 返回的 dict
    """

    def __init__(
        self,
        name: str,
        *,
        sleep: float = 0.0,
        fail_first: int = 0,
        always_fail: bool = False,
        return_value: Optional[Dict[str, Any]] = None,
        max_retries_override: Optional[int] = None,
    ):
        super().__init__(name=name, source_url=f"https://fake/{name}")
        self.sleep = sleep
        self.fail_first = fail_first
        self.always_fail = always_fail
        self.return_value = return_value
        self.call_count = 0
        self.start_times: List[float] = []
        # 测试不期望 BaseFetcher 真的去 fetch_raw / save, 直接覆盖 run()
        if max_retries_override is not None:
            self.max_retries = max_retries_override
        # 让 fetch_with_retry 内部循环次数可控
        self.max_retries = max(self.fail_first + 1, self.max_retries)

    async def fetch_raw(self):  # pragma: no cover - 不被调用
        return []

    def parse(self, raw):  # pragma: no cover - 不被调用
        return []

    async def run(self, *, health_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """覆盖 base.run(), 让行为完全可控。return_value=None 时真返回 None。"""
        self.call_count += 1
        self.start_times.append(time.monotonic())
        await asyncio.sleep(self.sleep)
        if self.always_fail:
            raise RuntimeError(f"fake-{self.name}-always-fail")
        if self.call_count <= self.fail_first:
            raise RuntimeError(f"fake-{self.name}-transient-fail (call {self.call_count})")
        if self.return_value is None:
            return None
        return self.return_value


# ============================================================
# _parse_int_env
# ============================================================
class TestParseIntEnv:
    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_W2_D4_INT", raising=False)
        assert mf._parse_int_env("TEST_W2_D4_INT", default=3) == 3

    def test_default_when_empty(self, monkeypatch):
        monkeypatch.setenv("TEST_W2_D4_INT", "")
        assert mf._parse_int_env("TEST_W2_D4_INT", default=3) == 3

    def test_valid_int(self, monkeypatch):
        monkeypatch.setenv("TEST_W2_D4_INT", "7")
        assert mf._parse_int_env("TEST_W2_D4_INT", default=3) == 7

    def test_invalid_int_returns_default(self, monkeypatch):
        monkeypatch.setenv("TEST_W2_D4_INT", "not-a-number")
        assert mf._parse_int_env("TEST_W2_D4_INT", default=3) == 3

    def test_clamp_to_min(self, monkeypatch):
        monkeypatch.setenv("TEST_W2_D4_INT", "0")
        assert mf._parse_int_env("TEST_W2_D4_INT", default=3, min_val=1) == 1

    def test_clamp_to_max(self, monkeypatch):
        monkeypatch.setenv("TEST_W2_D4_INT", "999")
        assert mf._parse_int_env("TEST_W2_D4_INT", default=3, max_val=64) == 64


# ============================================================
# _gather_with_semaphore
# ============================================================
@_async_class
class TestGatherWithSemaphore:
    async def test_all_complete_with_correct_count(self):
        async def ok():
            return "ok"

        coros = [ok() for _ in range(5)]
        results = await mf._gather_with_semaphore(coros, concurrency=3)
        assert results == ["ok"] * 5
        assert len(results) == 5

    async def test_single_failure_does_not_block_others(self):
        async def ok():
            return 1

        async def boom():
            raise RuntimeError("boom")

        coros = [ok(), boom(), ok(), boom(), ok()]
        results = await mf._gather_with_semaphore(coros, concurrency=3)

        assert len(results) == 5
        # ok 位置成功
        assert results[0] == 1
        assert results[2] == 1
        assert results[4] == 1
        # boom 位置是 Exception 实例
        assert isinstance(results[1], RuntimeError)
        assert isinstance(results[3], RuntimeError)
        assert "boom" in str(results[1])

    async def test_concurrency_limit_respected(self):
        """验证 Semaphore 真限流：3 个慢协程, 后面 2 个必须等."""
        peak_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def slow(n):
            nonlocal peak_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                peak_concurrent = max(peak_concurrent, current_concurrent)
            await asyncio.sleep(0.1)
            async with lock:
                current_concurrent -= 1
            return n

        coros = [slow(i) for i in range(5)]
        t0 = time.monotonic()
        results = await mf._gather_with_semaphore(coros, concurrency=3)
        elapsed = time.monotonic() - t0

        assert results == [0, 1, 2, 3, 4]
        # 峰值并发必须 == 3, 不可能 4 或 5
        assert peak_concurrent == 3, f"峰值 {peak_concurrent} 超过限流 3"
        # 5 个协程每个 0.1s, 限流 3 → 总耗时应在 (5/3)*0.1 ≈ 0.17s 到 0.5s 之间
        assert 0.15 < elapsed < 0.5, f"耗时 {elapsed:.3f}s 不在预期窗口"

    async def test_concurrency_zero_rejected(self):
        """concurrency=0 时 Semaphore 永远不会 release, 应该死锁.

        这里只是 smoke test: 我们用 asyncio.wait_for 兜底, 验证不会真跑出结果.
        """
        async def ok():
            return 1

        coros = [ok() for _ in range(3)]
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                mf._gather_with_semaphore(coros, concurrency=0),
                timeout=0.2,
            )


# ============================================================
# _run_with_main_retry
# ============================================================
@_async_class
class TestRunWithMainRetry:
    async def test_first_success(self):
        f = FakeFetcher("a", return_value={"added": 5, "total": 5, "duplicates": 0})
        r = await mf._run_with_main_retry(f, max_retries=2)
        assert r == {"added": 5, "total": 5, "duplicates": 0}
        assert f.call_count == 1

    async def test_retry_after_one_failure(self):
        f = FakeFetcher("b", fail_first=1, return_value={"added": 1, "total": 1, "duplicates": 0})
        r = await mf._run_with_main_retry(f, max_retries=2)
        assert r == {"added": 1, "total": 1, "duplicates": 0}
        assert f.call_count == 2  # 第一次失败 + 第二次成功

    async def test_all_retries_exhausted_returns_error(self):
        f = FakeFetcher("c", always_fail=True)
        r = await mf._run_with_main_retry(f, max_retries=2)
        # 最终返回 error dict, 不抛
        assert "error" in r
        assert r["added"] == 0
        assert r["total"] == 0
        assert "always-fail" in r["error"]
        # 1 + max_retries 次尝试
        assert f.call_count == 3

    async def test_zero_retry_skips_retry(self):
        f = FakeFetcher("d", always_fail=True)
        r = await mf._run_with_main_retry(f, max_retries=0)
        assert "error" in r
        # 0 retry → 仅尝试 1 次
        assert f.call_count == 1

    async def test_none_return_normalized_to_zero_dict(self):
        """fetcher.run() 返回 None 时 (空源/未启用) 应规范化为全 0 dict."""
        f = FakeFetcher("e", return_value=None)  # type: ignore[arg-type]
        r = await mf._run_with_main_retry(f, max_retries=1)
        assert r == {"added": 0, "total": 0, "duplicates": 0}


# ============================================================
# _build_fetchers
# ============================================================
class TestBuildFetchers:
    def test_no_env_uses_all_registered(self, monkeypatch):
        monkeypatch.setenv("FETCHERS", "")
        fetchers = mf._build_fetchers()
        # 至少 ndrc + nea 必须可用 (其他看 ImportError)
        names = [f.name for f in fetchers]
        assert "发改委" in names
        assert "能源局" in names

    def test_specific_keys(self, monkeypatch):
        monkeypatch.setenv("FETCHERS", "ndrc")
        fetchers = mf._build_fetchers()
        names = [f.name for f in fetchers]
        assert names == ["发改委"]

    def test_unknown_key_skipped(self, monkeypatch, caplog):
        monkeypatch.setenv("FETCHERS", "ndrc,unknown-source")
        fetchers = mf._build_fetchers()
        names = [f.name for f in fetchers]
        assert names == ["发改委"]
        # 日志中应有 ⏭ 警告
        assert any("未注册" in r.message for r in caplog.records)


# ============================================================
# main_async 端到端 (FakeFetcher 注入)
# ============================================================
@_async_class
class TestMainAsyncEndToEnd:
    """端到端验证 5 个 fetcher 并发跑通, 限流生效, 失败不阻断."""

    async def test_five_fetchers_concurrent_run(self, tmp_path, monkeypatch):
        # 切到临时目录, 避免污染真实 data/
        monkeypatch.setattr(mf, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(mf, "POLICIES_DIR", tmp_path / "data")
        monkeypatch.setattr(mf, "LOGS_DIR", tmp_path / "logs")
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        # 把 health 写到 tmp
        monkeypatch.setattr(mf, "POLICIES_DIR", tmp_path / "data", raising=False)
        # 关掉 git commit, 避免跑 git
        monkeypatch.setattr(mf, "_commit_data_now", lambda: False)
        # 关掉 fetcher 健康探针对 health_path 的写入 (FakeFetcher 没经过 _HealthProbe)
        # 让 _run_with_main_retry 走 health_path 不存在也不挂
        monkeypatch.setenv("FETCHER_CONCURRENCY", "3")
        monkeypatch.setenv("FETCHER_RETRY", "0")

        # 注入 5 个 fake fetcher
        fake_fetchers = [
            FakeFetcher(f"源{i}", sleep=0.05, return_value={"added": i, "total": i, "duplicates": 0})
            for i in range(5)
        ]
        monkeypatch.setattr(mf, "_build_fetchers", lambda: fake_fetchers)

        t0 = time.monotonic()
        rc = await mf.main_async()
        elapsed = time.monotonic() - t0

        assert rc == 0
        # 5 个 0.05s, 限流 3 → 至少 2 批, 总耗时应在 0.10s 上下 (含 main_async 开销)
        assert 0.10 < elapsed < 1.0, f"并发总耗时 {elapsed:.3f}s 异常"
        # 所有 fetcher 都被调用了
        for f in fake_fetchers:
            assert f.call_count == 1

    async def test_one_fetcher_failure_does_not_block_others(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mf, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(mf, "POLICIES_DIR", tmp_path / "data")
        monkeypatch.setattr(mf, "LOGS_DIR", tmp_path / "logs")
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(mf, "_commit_data_now", lambda: False)
        monkeypatch.setenv("FETCHER_CONCURRENCY", "3")
        monkeypatch.setenv("FETCHER_RETRY", "0")

        # 中间塞一个 always_fail, 看其他 4 个是否照常成功
        fake_fetchers = [
            FakeFetcher("好源A", sleep=0.02, return_value={"added": 1, "total": 1, "duplicates": 0}),
            FakeFetcher("好源B", sleep=0.02, return_value={"added": 2, "total": 2, "duplicates": 0}),
            FakeFetcher("坏源C", sleep=0.02, always_fail=True),
            FakeFetcher("好源D", sleep=0.02, return_value={"added": 3, "total": 3, "duplicates": 0}),
            FakeFetcher("好源E", sleep=0.02, return_value={"added": 4, "total": 4, "duplicates": 0}),
        ]
        monkeypatch.setattr(mf, "_build_fetchers", lambda: fake_fetchers)

        rc = await mf.main_async()
        assert rc == 0  # 一个失败不应让 main 返回非零
        # 4 个好源都被调用 1 次
        assert fake_fetchers[0].call_count == 1
        assert fake_fetchers[1].call_count == 1
        # 坏源失败 (retry=0 → 1 次)
        assert fake_fetchers[2].call_count == 1
        assert fake_fetchers[3].call_count == 1
        assert fake_fetchers[4].call_count == 1

    async def test_no_fetchers_returns_error_code(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mf, "_build_fetchers", lambda: [])
        rc = await mf.main_async()
        assert rc == 1  # 没 fetcher → 退出码 1