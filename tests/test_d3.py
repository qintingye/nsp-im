"""
W1-D3-BE · 单测 (B5 + B6 + 复用 B4)
=====================================

覆盖:
  - atomic_write  (smoke: 确保 B4 既有实现仍能跑通)
  - health        (record_run / evaluate / stale 判定 / 持久化往返)
  - dedup         (按 id 去重 / 按 url 去重 / freshness 优先)

运行:
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe -m pytest tests/test_d3.py -v
"""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from utils.atomic_write import atomic_write_json, safe_read_json  # noqa: E402
from utils.health import (  # noqa: E402
    FetcherHealth,
    evaluate,
    load_state,
    overall_summary,
    record_run,
    save_state,
    _HealthProbe,
    STALE_HOURS,
)
from utils.dedup import deduplicate, normalize_url  # noqa: E402


# ============================================================
# Atomic write smoke
# ============================================================
class TestAtomicWrite:
    """B4 smoke: 确保 Day1 已落地的原子写入仍可被消费。"""

    def test_atomic_write(self, tmp_path: Path):
        target = tmp_path / "p.json"
        atomic_write_json(target, {"v": 1}, ensure_ascii=False)
        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}

        # 二次覆盖
        atomic_write_json(target, {"v": 2, "中文": "绿电"})
        text = target.read_text(encoding="utf-8")
        assert "绿电" in text
        assert json.loads(text)["v"] == 2


# ============================================================
# Health
# ============================================================
class TestHealth:
    """B6 健康探针。"""

    def _now(self) -> datetime:
        return datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)

    def test_record_run_success_and_fail(self, tmp_path: Path):
        state: dict = {}
        now = self._now()

        record_run(state, "ndrc", success=True, latency_ms=1200, now=now)
        record_run(state, "ndrc", success=True, latency_ms=800, now=now)
        record_run(state, "ndrc", success=False, latency_ms=9999, error="timeout", now=now)

        h = state["ndrc"]
        assert h.success_count == 2
        assert h.fail_count == 1
        assert h.last_status == "fail"
        assert h.last_error == "timeout"
        assert h.avg_latency_ms == pytest.approx(1000.0)
        assert h.is_alerting() is True  # fail_ratio 1/3 < 0.5 但 last_status=fail

    def test_stale_detection(self):
        now = self._now()
        h = FetcherHealth(name="ndrc", last_run_at=(now - timedelta(hours=STALE_HOURS + 1)).isoformat())
        assert h.is_stale(now) is True

        h2 = FetcherHealth(name="ndrc", last_run_at=(now - timedelta(hours=1)).isoformat())
        assert h2.is_stale(now) is False

    def test_evaluate_and_overall(self):
        now = self._now()
        h = FetcherHealth(
            name="mwr",
            success_count=10,
            fail_count=0,
            last_run_at=now.isoformat(),
            last_status="success",
            last_latency_ms=200.0,
            total_latency_ms=2000.0,
        )
        rep = evaluate(h, now)
        assert rep["status"] == "success"
        assert rep["alerting"] is False
        assert rep["stale"] is False
        assert rep["avg_latency_ms"] == 200.0

        overall = overall_summary({"mwr": h}, now)
        assert overall["healthy"] is True
        assert overall["alerting_count"] == 0

    def test_persistence_roundtrip(self, tmp_path: Path):
        path = tmp_path / "health.json"
        state: dict = {}
        now = self._now()
        record_run(state, "ndrc", success=True, latency_ms=1500, now=now)
        record_run(state, "mwr", success=False, latency_ms=9999, error="boom", now=now)
        save_state(path, state)

        # 重新加载
        loaded = load_state(path)
        assert "ndrc" in loaded and "mwr" in loaded
        assert loaded["ndrc"].success_count == 1
        assert loaded["mwr"].last_error == "boom"

        # safe_read_json 容错
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert safe_read_json(bad, default={}) == {}

    def test_health_probe_context_manager(self, tmp_path: Path):
        """_HealthProbe: 模拟一次 fetcher 调用，自动写 health。"""
        path = tmp_path / "h.json"
        with _HealthProbe("ndrc", path) as probe:
            # 模拟一段耗时操作
            import time
            time.sleep(0.05)  # 50ms，确保 monotonic 时钟可分辨
        assert probe.elapsed_ms is not None
        assert probe.elapsed_ms >= 10  # 至少 10ms (Windows monotonic 起步较粗)
        loaded = load_state(path)
        assert "ndrc" in loaded
        assert loaded["ndrc"].success_count == 1

        # 异常路径
        with pytest.raises(RuntimeError):
            with _HealthProbe("ndrc", path):
                raise RuntimeError("simulated fail")
        loaded2 = load_state(path)
        assert loaded2["ndrc"].fail_count == 1
        assert loaded2["ndrc"].last_status == "fail"


# ============================================================
# Dedup
# ============================================================
class TestDedup:
    """B5 去重。"""

    def test_normalize_url_strips_tracking(self):
        assert normalize_url("HTTPS://WWW.Example.com/path/?") == "https://example.com/path"
        assert normalize_url("https://example.com/a?utm_source=x&b=1") == "https://example.com/a?b=1"
        assert normalize_url("https://example.com/a#frag") == "https://example.com/a"
        assert normalize_url("") is None
        assert normalize_url(None) is None

    def test_dedup_by_id(self):
        items = [
            {"id": "P-1", "title": "政策一", "captured_at": "2026-08-19T08:00:00Z"},
            {"id": "P-1", "title": "政策一(更新)", "captured_at": "2026-08-19T09:00:00Z"},  # 更新版
            {"id": "P-2", "title": "政策二"},
        ]
        result = deduplicate(items, prefer="freshest")
        assert result["stats"]["input"] == 3
        assert result["stats"]["unique"] == 2
        assert result["stats"]["removed_by_id"] == 1
        # freshest 策略：保留 captured_at 较新的
        kept = next(p for p in result["unique"] if p["id"] == "P-1")
        assert kept["title"] == "政策一(更新)"

    def test_dedup_by_url_when_id_differs(self):
        items = [
            {"id": "P-1", "source_url": "https://www.ndrc.gov.cn/a.html"},
            {"id": "P-2", "source_url": "HTTPS://www.ndrc.gov.cn/a.html?utm_source=x"},
        ]
        result = deduplicate(items)
        assert result["stats"]["unique"] == 1
        assert result["stats"]["removed_by_url"] == 1
        assert result["stats"]["removed_by_id"] == 0

    def test_dedup_keeps_all_when_no_dup(self):
        items = [
            {"id": "P-1", "source_url": "https://a.com/1"},
            {"id": "P-2", "source_url": "https://a.com/2"},
            {"id": "P-3"},  # 无 url
        ]
        result = deduplicate(items)
        assert result["stats"]["unique"] == 3
        assert result["duplicates"] == []

    def test_dedup_tolerates_dirty_inputs(self):
        items = [
            {"id": "P-1"},
            "not a dict",          # 脏数据
            None,                  # 脏数据
            {"id": "P-1", "title": "dup"},
        ]
        result = deduplicate(items)
        # unique: P-1 一条；duplicates 包含脏数据 + dup-id
        assert result["stats"]["unique"] == 1
        assert any(d.get("reason") == "not-a-dict" for d in result["duplicates"])

    def test_dedup_prefer_first(self):
        items = [
            {"id": "P-1", "captured_at": "2026-08-19T09:00:00Z"},
            {"id": "P-1", "captured_at": "2026-08-19T08:00:00Z"},
        ]
        result = deduplicate(items, prefer="first")
        kept = result["unique"][0]
        assert kept["captured_at"] == "2026-08-19T09:00:00Z"  # 第一次出现的