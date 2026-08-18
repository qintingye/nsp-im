"""
W1-D4-BE · 单测 (集成工具 integrate.py)
=========================================

覆盖:
  - integrated_fetch 端到端: dedup → atomic save → health record
  - fetch_with_health 装饰器: sync / async 两条路径
  - IntegratedPipeline 上下文管理器
  - run_integration_demo 离线烟测

运行:
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe -m pytest tests/test_d4.py -v
"""
import asyncio
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from utils.integrate import (  # noqa: E402
    fetch_with_health,
    integrated_fetch,
    IntegratedPipeline,
    run_integration_demo,
    DEMO_POLICIES,
)


# ============================================================
# integrated_fetch
# ============================================================
class TestIntegratedFetch:
    """端到端：dedup + atomic save + health record 一次跑通。"""

    def test_basic_merge_and_dedup(self, tmp_path: Path):
        target = tmp_path / "policies.json"
        health = tmp_path / "health.json"

        # 第一次: 写入 3 条
        r1 = integrated_fetch(
            name="t1",
            raw_items=[{"id": "P-A-20260101-0001"}, {"id": "P-B-20260101-0002"}],
            target_path=target,
            health_path=health,
        )
        assert r1["added"] == 2
        assert r1["total"] == 2
        assert r1["duplicates"] == 0
        assert target.exists()

        # 第二次: 再加 2 条 + 1 条与旧重复 (按 id 命中)
        r2 = integrated_fetch(
            name="t1",
            raw_items=[
                {"id": "P-A-20260101-0001"},  # dup-id
                {"id": "P-C-20260101-0003"},  # new
                {"id": "P-D-20260101-0004"},  # new
            ],
            target_path=target,
            health_path=health,
        )
        assert r2["added"] == 2  # only C and D are added
        assert r2["total"] == 4
        assert r2["duplicates"] == 1

        # 校验落盘数据完整
        data = json.loads(target.read_text(encoding="utf-8"))
        assert len(data["policies"]) == 4
        assert "generated_at" in data

        # 校验 health.json 写入了两次 run
        health_data = json.loads(health.read_text(encoding="utf-8"))
        assert health_data["fetchers"]["t1"]["success_count"] == 2

    def test_dirty_inputs_are_tolerated(self, tmp_path: Path):
        target = tmp_path / "policies.json"
        health = tmp_path / "health.json"

        # 混入脏数据：字符串 / None / 非 dict
        r = integrated_fetch(
            name="t1",
            raw_items=[
                {"id": "P-A-20260101-0001"},
                "not a dict",
                None,
                {"id": "P-B-20260101-0002"},
            ],
            target_path=target,
            health_path=health,
        )
        # 脏数据进入 duplicates（按 not-a-dict 原因），unique 仍应有 2 条
        assert r["total"] == 2
        # 即使有脏数据, 也不应抛异常, 也成功写了 health
        health_data = json.loads(health.read_text(encoding="utf-8"))
        assert health_data["fetchers"]["t1"]["success_count"] == 1

    def test_atomic_write_no_partial_file(self, tmp_path: Path):
        """验证 atomic_write: 写入过程中旧文件仍可读。"""
        target = tmp_path / "policies.json"
        health = tmp_path / "health.json"

        # 先写一份
        integrated_fetch(
            name="t",
            raw_items=[{"id": "P-A-20260101-0001"}],
            target_path=target,
            health_path=health,
        )
        old_content = target.read_text(encoding="utf-8")
        # 再写一份更大
        integrated_fetch(
            name="t",
            raw_items=[{"id": "P-A-20260101-0001"}, {"id": "P-B-20260101-0002"}],
            target_path=target,
            health_path=health,
        )
        new_content = target.read_text(encoding="utf-8")
        assert old_content != new_content  # 文件确实变了
        # 目录里不应残留 .tmp 文件
        leftovers = list(target.parent.glob(".policies.json.tmp.*"))
        assert leftovers == []


# ============================================================
# fetch_with_health
# ============================================================
class TestFetchWithHealthDecorator:
    """装饰器路径: sync + async。"""

    def test_sync_decorator_records_success(self, tmp_path: Path):
        health = tmp_path / "h.json"

        @fetch_with_health("sync-fetcher", health)
        def my_fn():
            return {"ok": True}

        result = my_fn()
        assert result == {"ok": True}
        data = json.loads(health.read_text(encoding="utf-8"))
        assert data["fetchers"]["sync-fetcher"]["success_count"] == 1
        assert data["fetchers"]["sync-fetcher"]["last_status"] == "success"

    def test_sync_decorator_records_failure(self, tmp_path: Path):
        health = tmp_path / "h.json"

        @fetch_with_health("sync-fetcher", health)
        def my_fn():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            my_fn()
        data = json.loads(health.read_text(encoding="utf-8"))
        assert data["fetchers"]["sync-fetcher"]["fail_count"] == 1
        assert "RuntimeError" in data["fetchers"]["sync-fetcher"]["last_error"]

    def test_async_decorator_records_success(self, tmp_path: Path):
        health = tmp_path / "h.json"

        @fetch_with_health("async-fetcher", health)
        async def my_async():
            await asyncio.sleep(0.01)
            return [1, 2, 3]

        result = asyncio.run(my_async())
        assert result == [1, 2, 3]
        data = json.loads(health.read_text(encoding="utf-8"))
        assert data["fetchers"]["async-fetcher"]["success_count"] == 1
        assert data["fetchers"]["async-fetcher"]["last_latency_ms"] is not None

    def test_async_decorator_records_failure(self, tmp_path: Path):
        health = tmp_path / "h.json"

        @fetch_with_health("async-fetcher", health)
        async def my_async():
            raise ValueError("nope")

        with pytest.raises(ValueError, match="nope"):
            asyncio.run(my_async())
        data = json.loads(health.read_text(encoding="utf-8"))
        assert data["fetchers"]["async-fetcher"]["fail_count"] == 1


# ============================================================
# IntegratedPipeline
# ============================================================
class TestIntegratedPipeline:
    def test_with_block_records_success(self, tmp_path: Path):
        health = tmp_path / "h.json"
        with IntegratedPipeline("pipe", health) as p:
            p.set_result([{"id": "1"}])
        data = json.loads(health.read_text(encoding="utf-8"))
        assert data["fetchers"]["pipe"]["success_count"] == 1

    def test_with_block_records_failure_via_set_error(self, tmp_path: Path):
        health = tmp_path / "h.json"
        with IntegratedPipeline("pipe", health) as p:
            p.set_error("simulated fail")
        data = json.loads(health.read_text(encoding="utf-8"))
        assert data["fetchers"]["pipe"]["fail_count"] == 1
        assert data["fetchers"]["pipe"]["last_error"] == "simulated fail"

    def test_with_block_records_failure_via_exception(self, tmp_path: Path):
        health = tmp_path / "h.json"
        with pytest.raises(RuntimeError):
            with IntegratedPipeline("pipe", health):
                raise RuntimeError("ctx boom")
        data = json.loads(health.read_text(encoding="utf-8"))
        assert data["fetchers"]["pipe"]["fail_count"] == 1


# ============================================================
# run_integration_demo
# ============================================================
class TestRunIntegrationDemo:
    def test_demo_offline_no_network(self, tmp_path: Path):
        """即使断网, demo 也能跑通。"""
        target = tmp_path / "p.json"
        health = tmp_path / "h.json"
        captured = []
        res = run_integration_demo(
            target_path=target,
            health_path=health,
            log=lambda m: captured.append(m),
        )
        # 6 输入 (5 demo + 1 dup) → 5 unique → 全部为新增
        assert res["added"] == len(DEMO_POLICIES)
        assert res["total"] == len(DEMO_POLICIES)
        assert res["duplicates"] == 1
        # 校验所有 demo policy 都已写入
        data = json.loads(target.read_text(encoding="utf-8"))
        ids = {p["id"] for p in data["policies"]}
        for d in DEMO_POLICIES:
            assert d["id"] in ids
        # health 至少记录了 integrate-demo 一次成功
        h = json.loads(health.read_text(encoding="utf-8"))
        assert "integrate-demo" in h["fetchers"]
        assert h["fetchers"]["integrate-demo"]["success_count"] == 1