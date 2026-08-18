"""
W3-D1 端到端真抓稳定化测试: scripts/_w3d1_real_fetch.py 跑完后,
验证 logs/w3d1_summary.json + data/policies.json + data/health.json 三件套.

验收标准 (W3-D1 任务书: User-Agent + 限流 + 反爬 + 重试 + 真实抓 5 源):
  1. 5 源 (发改委 / 能源局 / 南网 / 国网 / 北极星) 都出现在 summary.sources
  2. errors == 0 (5 源全部跑通, sgcc 走 demo fallback 不算错误)
  3. 至少 4/5 源是真实抓取 (fallback 字段为 False), sgcc 可走 fallback
  4. policies.json 通过 jsonschema 校验 + 总条目数 >= 60
  5. health.json 中 5 源均存在, last_status 至少 4 个 success + sgcc 可 fallback 标记
  6. summary 时间戳 <= 当前时间

注: 本测试不重复运行真抓 (会消耗 60s+ 且依赖网络); 只验证已有产物.
    若需要回归, 单独跑: .venv-d5/Scripts/python.exe scripts/_w3d1_real_fetch.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

REPO_DATA_DIR = ROOT / "data"
LOGS_DIR = ROOT / "logs"
SCHEMA_PATH = ROOT / "src" / "schemas" / "policies.schema.json"
SUMMARY_PATH = LOGS_DIR / "w3d1_summary.json"
POLICIES_PATH = REPO_DATA_DIR / "policies.json"
HEALTH_PATH = REPO_DATA_DIR / "health.json"

EXPECTED_SOURCES = ["发改委", "能源局", "南网", "国网", "北极星"]


def _load_json(path: Path) -> dict:
    assert path.exists(), f"缺少文件: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


class TestW3D1SummaryArtifacts:
    """logs/w3d1_summary.json: W3-D1 真抓驱动产物."""

    def test_summary_exists_and_is_recent(self):
        s = _load_json(SUMMARY_PATH)
        ts = s.get("timestamp", "")
        assert ts, "summary.timestamp 不能为空"
        # 解析 ISO 8601
        assert ts.endswith("Z"), f"timestamp 应以 Z 结尾 (UTC): {ts}"
        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta_min = (now - ts_dt).total_seconds() / 60
        # 允许 7 天 (跨多次重试); 一般 < 30min
        assert delta_min < 7 * 24 * 60, (
            f"summary 时间戳太旧: {ts} (距今 {delta_min:.1f} 分钟)"
        )

    def test_summary_has_all_5_sources(self):
        s = _load_json(SUMMARY_PATH)
        names = {x["name"] for x in s.get("sources", [])}
        for src in EXPECTED_SOURCES:
            assert src in names, f"summary 缺少源: {src} (现有: {names})"

    def test_summary_zero_errors(self):
        """W3-D1 硬指标: errors == 0."""
        s = _load_json(SUMMARY_PATH)
        totals = s["totals"]
        assert totals["errors"] == 0, (
            f"应 0 错误, 实际 {totals['errors']}; 各源错误: "
            + ", ".join(
                f"{x['name']}={x['error']}" for x in s["sources"] if x["error"]
            )
        )

    def test_summary_at_least_4_real_fetches(self):
        """至少 4/5 源真实抓取 (sgcc 可走 fallback)."""
        s = _load_json(SUMMARY_PATH)
        real_count = sum(1 for x in s["sources"] if not x["fallback"])
        assert real_count >= 4, (
            f"至少 4 源真实抓取, 实际 {real_count}; "
            f"fallback 详情: {[(x['name'], x['fallback']) for x in s['sources']]}"
        )

    def test_summary_raw_counts_meaningful(self):
        """每个源 raw >= 1 (真抓或 fallback 都至少 1 条)."""
        s = _load_json(SUMMARY_PATH)
        for x in s["sources"]:
            assert x["raw"] >= 1, f"{x['name']} raw 条数为 0"


class TestW3D1PoliciesIntegrity:
    """data/policies.json: 真抓后落盘必须仍合规."""

    def test_policies_passes_schema(self):
        """落盘 policies.json 必须通过 jsonschema 校验."""
        policies = _load_json(POLICIES_PATH)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=policies, schema=schema)

    def test_policies_count_at_least_60(self):
        """W2 已落库 61 条, W3-D1 真抓后不应回退 (允许少量新增)."""
        policies = _load_json(POLICIES_PATH)
        assert len(policies["policies"]) >= 60, (
            f"policies.json 总数 < 60: {len(policies['policies'])}"
        )

    def test_policies_id_unique(self):
        policies = _load_json(POLICIES_PATH)
        ids = [p["id"] for p in policies["policies"]]
        assert len(ids) == len(set(ids)), (
            f"id 不唯一: 重复 = "
            + ", ".join(
                i for i in ids if ids.count(i) > 1
            )
        )

    def test_policies_5_departments_present(self):
        """5 源落盘后, 应有 5 个部门: 国家发改委 / 国家能源局 / 南方电网公司 / 国家电网公司 / 北极星电力."""
        policies = _load_json(POLICIES_PATH)
        depts = {p.get("department") for p in policies["policies"]}
        required = {
            "国家发改委",
            "国家能源局",
            "南方电网公司",
            "国家电网公司",
            "北极星电力",
        }
        missing = required - depts
        assert not missing, (
            f"policies.json 缺部门: {missing}; 实际: {sorted(depts)}"
        )


class TestW3D1HealthCoverage:
    """data/health.json: 5 源都在健康表中."""

    def test_health_has_5_sources(self):
        h = _load_json(HEALTH_PATH)
        fetchers = h.get("fetchers", {})
        for src in EXPECTED_SOURCES:
            assert src in fetchers, (
                f"health.fetchers 缺少源: {src} (现有: {sorted(fetchers)})"
            )

    def test_health_at_least_4_sources_success(self):
        """至少 4/5 源 last_status == success."""
        h = _load_json(HEALTH_PATH)
        fetchers = h.get("fetchers", {})
        success_count = sum(
            1
            for src in EXPECTED_SOURCES
            if fetchers.get(src, {}).get("last_status") == "success"
        )
        assert success_count >= 4, (
            f"至少 4 源 success, 实际 {success_count}; "
            + ", ".join(
                f"{src}={fetchers.get(src, {}).get('last_status')}"
                for src in EXPECTED_SOURCES
            )
        )


if __name__ == "__main__":
    # 允许直接 python -m tests.test_w3d1_real_fetch 跑 (旧 CI 兼容)
    print("W3-D1 端到端真抓稳定化测试 (直接运行模式)")
    print(f"  summary: {SUMMARY_PATH}")
    print(f"  policies: {POLICIES_PATH}")
    print(f"  health: {HEALTH_PATH}")
    s = _load_json(SUMMARY_PATH)
    print(
        f"\n  sources: {[(x['name'], x['raw'], x['parsed'], 'fallback' if x['fallback'] else 'real') for x in s['sources']]}"
    )
    print(f"  totals: {s['totals']}")
    policies = _load_json(POLICIES_PATH)
    print(f"  policies.json: total={len(policies['policies'])}")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=policies, schema=schema)
    print("  ✅ schema validate OK")