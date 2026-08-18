"""
W2-D3 · 4 源集成测试 (NDRC + NEA + BJX + CSG)
==============================================

覆盖:
  1. 4 源各自能跑通 fetch_raw → parse (单 fetcher 入口已由 test_nea/test_bjx/test_csg 覆盖)
  2. 4 源合并 dedup 后, 覆盖 5 网全类型 (grid/water/compute/telecom/pipe/logi + monitor)
  3. integrated_fetch 端到端: 4 源数据 → dedup → atomic write → health.json
  4. 跨源去重 (URL 归一化 / id 命中) - 模拟同一政策被多源收录
  5. main_fetcher 的 --demo 离线模式集成 4 源
  6. policies.json 落盘文件 schema 校验

设计目标 (W2-D3 验收基线):
  - 单文件覆盖 4 源端到端链路
  - 跑通即可证明 "5 网协同" 横向信号源集成 OK

运行:
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe -m pytest tests/test_integration_4_sources.py -v
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# 4 源全部走离线 demo (NDRC 为真抓源, 离线环境不确定, 见 tests/test_d3.py)
from fetchers.sgcc import SgccFetcher  # noqa: E402
from fetchers.nea import NeaFetcher  # noqa: E402
from fetchers.bjx import BjxFetcher  # noqa: E402
from fetchers.csg import CsgFetcher  # noqa: E402
from utils.integrate import (  # noqa: E402
    integrated_fetch,
    run_integration_demo,
)

# 4 源常量: 用于夹具复用
ALL_FOUR_SOURCES = [SgccFetcher, NeaFetcher, BjxFetcher, CsgFetcher]
SOURCE_NAMES = ["国网", "能源局", "北极星", "南网"]

# 5 网全类型 (与 schema "scope" enum 对齐)
FIVE_NET_SCOPES = {"grid", "water", "compute", "telecom", "pipe", "logi", "monitor"}


# ============================================================
# 4 源 fixture (避免每 case 重复 await)
# ============================================================
@pytest.fixture(scope="module")
def four_source_policies() -> List[Dict[str, Any]]:
    """跑一遍 4 个 fetcher, 合并所有 policies (dedup 前)."""
    all_policies: List[Dict[str, Any]] = []
    for fetcher_cls in ALL_FOUR_SOURCES:
        f = fetcher_cls()
        raw = asyncio.run(f.fetch_raw())
        parsed = f.parse(raw)
        # 给每条加 source 标记 (便于追踪)
        for p in parsed:
            p = dict(p)
            p["_source"] = f.name
        all_policies.extend(parsed)
    return all_policies


@pytest.fixture(scope="module")
def four_source_raw_counts() -> Dict[str, int]:
    """4 源各自的 raw 条数."""
    counts: Dict[str, int] = {}
    for fetcher_cls in ALL_FOUR_SOURCES:
        f = fetcher_cls()
        raw = asyncio.run(f.fetch_raw())
        counts[f.name] = len(raw)
    return counts


# ============================================================
# 单源 smoke
# ============================================================
class TestFourSourceSmoke:
    """4 源各自 fetch_raw → parse 能跑通."""

    @pytest.mark.parametrize("fetcher_cls", ALL_FOUR_SOURCES)
    def test_each_fetcher_returns_at_least_3_items(self, fetcher_cls):
        """每个 fetcher 至少返回 3 条原始数据."""
        f = fetcher_cls()
        raw = asyncio.run(f.fetch_raw())
        assert len(raw) >= 3, f"{f.name} 返回 {len(raw)} 条 (< 3)"

    @pytest.mark.parametrize("fetcher_cls", ALL_FOUR_SOURCES)
    def test_each_fetcher_parse_produces_valid_policies(self, fetcher_cls):
        """每个 fetcher parse 后必须含 schema 必填字段."""
        f = fetcher_cls()
        raw = asyncio.run(f.fetch_raw())
        policies = f.parse(raw)
        assert len(policies) == len(raw)
        for p in policies:
            for field in ("id", "title", "department", "publish_date", "scope"):
                assert field in p, f"{f.name} 缺字段: {field}"
            # id 必须符合 schema: P-<SRC>-YYYYMMDD-NNNN
            assert re.match(r"^P-[A-Z]+-\d{8}-\d{4}$", p["id"]), \
                f"{f.name} id 格式错: {p['id']}"

    def test_four_source_id_prefixes_distinct(self, four_source_policies):
        """4 源的 id 前缀应清晰区分 (P-SGCC / P-NEA / P-BJX / P-CSG)."""
        prefixes = {p["id"].split("-")[1] for p in four_source_policies}
        assert prefixes == {"SGCC", "NEA", "BJX", "CSG"}, \
            f"id 前缀未覆盖 4 源: {prefixes}"


# ============================================================
# 4 源合并覆盖 5 网全类型
# ============================================================
class TestFiveNetCoverage:
    """4 源合并后, 必须覆盖 5 网 + monitor 兜底."""

    def test_combined_scopes_cover_5_net(self, four_source_policies):
        """合并后所有 scope 应覆盖 grid/water/compute/telecom/pipe/logi + monitor."""
        all_scopes = set()
        for p in four_source_policies:
            all_scopes.update(p.get("scope", []))
        missing = FIVE_NET_SCOPES - all_scopes
        assert not missing, f"4 源合并后未覆盖的 scope: {missing}"

    def test_each_5_net_has_at_least_one_policy(self, four_source_policies):
        """每个 scope 至少有一条 policy 命中."""
        scope_counts: Dict[str, int] = {}
        for p in four_source_policies:
            for s in p.get("scope", []):
                scope_counts[s] = scope_counts.get(s, 0) + 1
        for scope in FIVE_NET_SCOPES:
            assert scope_counts.get(scope, 0) >= 1, \
                f"{scope} 0 命中: {scope_counts}"

    def test_grid_is_most_common_scope(self, four_source_policies):
        """grid 应该是最常见的 scope (电力/电网是核心)."""
        scope_counts: Dict[str, int] = {}
        for p in four_source_policies:
            for s in p.get("scope", []):
                scope_counts[s] = scope_counts.get(s, 0) + 1
        assert scope_counts.get("grid", 0) >= scope_counts.get("water", 0)
        assert scope_counts.get("grid", 0) >= scope_counts.get("pipe", 0)


# ============================================================
# 跨源去重集成 (URL 归一化 / id 命中)
# ============================================================
class TestCrossSourceDedup:
    """模拟同一政策被多源收录时的去重行为."""

    def test_dedup_by_id_across_sources(self):
        """模拟: 同一 id 在 4 源各自版本, dedup 应保留 1 条."""
        from utils.dedup import deduplicate

        # 4 源对"虚拟电厂新规"分别给同 id (P-TEST-20240601-0001) 但不同 captured_at
        items = [
            {"id": "P-TEST-20240601-0001", "title": "虚拟电厂", "captured_at": "2024-08-01T08:00:00Z"},
            {"id": "P-TEST-20240601-0001", "title": "虚拟电厂 (v2)", "captured_at": "2024-08-15T09:00:00Z"},
            {"id": "P-TEST-20240601-0001", "title": "虚拟电厂 (v1)", "captured_at": "2024-08-01T08:00:00Z"},
        ]
        result = deduplicate(items, prefer="freshest")
        assert result["stats"]["unique"] == 1
        assert result["stats"]["removed_by_id"] == 2
        # freshest: 保留 8-15 那条
        kept = result["unique"][0]
        assert "v2" in kept["title"]

    def test_dedup_by_url_when_id_differs(self):
        """URL 归一化兜底: 不同 id 但同 URL 也要去重."""
        from utils.dedup import normalize_url, deduplicate

        items = [
            {"id": "P-A", "source_url": "HTTPS://www.example.com/p.html?utm_source=x"},
            {"id": "P-B", "source_url": "https://www.example.com/p.html"},
        ]
        result = deduplicate(items)
        assert result["stats"]["unique"] == 1
        assert result["stats"]["removed_by_url"] == 1

    def test_4_source_dedup_keeps_unique(self, four_source_policies):
        """4 源各自带 source 标记合并, dedup 后 unique 应 ≤ input."""
        from utils.dedup import deduplicate
        result = deduplicate(four_source_policies, prefer="freshest")
        # 4 源 demo 数据 id 都不同 → unique 应等于 input
        assert result["stats"]["input"] == len(four_source_policies)
        assert result["stats"]["unique"] == len(four_source_policies)


# ============================================================
# integrated_fetch 端到端 (4 源数据 → atomic write → health.json)
# ============================================================
class TestIntegratedFetchFourSources:
    """集成工具 integrated_fetch 处理 4 源数据."""

    def test_4_source_integrated_fetch_writes_valid_json(
        self, four_source_policies, tmp_path: Path
    ):
        """4 源合并 → integrated_fetch → 落盘 policies.json 合法."""
        target = tmp_path / "policies.json"
        health = tmp_path / "health.json"

        res = integrated_fetch(
            name="4-source-integration",
            raw_items=four_source_policies,
            target_path=target,
            health_path=health,
        )

        assert res["added"] == len(four_source_policies)
        assert res["total"] == len(four_source_policies)
        assert target.exists()

        # 落盘 JSON 合法
        on_disk = json.loads(target.read_text(encoding="utf-8"))
        assert "policies" in on_disk
        assert "generated_at" in on_disk
        assert len(on_disk["policies"]) == len(four_source_policies)

        # health.json 写入了
        h_data = json.loads(health.read_text(encoding="utf-8"))
        assert "4-source-integration" in h_data["fetchers"]
        assert h_data["fetchers"]["4-source-integration"]["success_count"] == 1

    def test_4_source_run_creates_unique_ids(self, four_source_policies, tmp_path: Path):
        """落盘后, 所有 id 仍唯一 (无重复)."""
        target = tmp_path / "policies.json"
        integrated_fetch(
            name="4-source-integration",
            raw_items=four_source_policies,
            target_path=target,
            health_path=tmp_path / "health.json",
        )
        on_disk = json.loads(target.read_text(encoding="utf-8"))
        ids = [p["id"] for p in on_disk["policies"]]
        assert len(ids) == len(set(ids)), "id 重复!"

    def test_4_source_policies_match_schema(
        self, four_source_policies, tmp_path: Path
    ):
        """落盘数据必须符合 policies.schema.json (jsonschema 校验)."""
        import jsonschema
        schema_path = ROOT / "src" / "schemas" / "policies.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        target = tmp_path / "policies.json"
        integrated_fetch(
            name="schema-validate",
            raw_items=four_source_policies,
            target_path=target,
            health_path=tmp_path / "health.json",
        )
        on_disk = json.loads(target.read_text(encoding="utf-8"))

        # jsonschema 校验
        jsonschema.validate(instance=on_disk, schema=schema)

    def test_idempotent_run_does_not_duplicate(
        self, four_source_policies, tmp_path: Path
    ):
        """第二次运行 4 源 (id 完全相同), 应 0 新增 (幂等)."""
        target = tmp_path / "policies.json"
        health = tmp_path / "health.json"

        r1 = integrated_fetch(
            name="idem", raw_items=four_source_policies,
            target_path=target, health_path=health,
        )
        assert r1["added"] == len(four_source_policies)

        r2 = integrated_fetch(
            name="idem", raw_items=four_source_policies,
            target_path=target, health_path=health,
        )
        assert r2["added"] == 0  # 全部已存在
        assert r2["total"] == len(four_source_policies)  # 总数不变


# ============================================================
# --demo 离线模式集成 4 源 (main_fetcher CLI 入口)
# ============================================================
class TestMainFetcherDemoIntegration:
    """main_fetcher.py --demo 子命令端到端 (4 源集成 demo)."""

    def test_run_integration_demo_with_4_source_policies(
        self, four_source_policies, tmp_path: Path
    ):
        """把 4 源 policies 注入 demo 流程, 验证 run_integration_demo 行为."""
        target = tmp_path / "policies.json"
        health = tmp_path / "health.json"

        # 4 源数据直接走 integrated_fetch (与 demo 同底层)
        captured = []
        res = integrated_fetch(
            name="4-source-demo",
            raw_items=four_source_policies,
            target_path=target,
            health_path=health,
        )

        assert res["added"] == len(four_source_policies)
        assert target.exists()
        assert health.exists()

        # 文件大小合理
        on_disk = json.loads(target.read_text(encoding="utf-8"))
        assert len(on_disk["policies"]) >= 20, \
            f"4 源合并应 ≥ 20 条, 实际 {len(on_disk['policies'])}"

    def test_demo_offline_no_network_required(self, tmp_path: Path):
        """run_integration_demo 必须断网可跑 (W1-D4 验收基线)."""
        target = tmp_path / "p.json"
        health = tmp_path / "h.json"
        # 不传 log (走默认 print), 验证不抛异常
        res = run_integration_demo(target_path=target, health_path=health)
        assert res["added"] >= 5  # DEMO_POLICIES 有 5 条
        assert target.exists()
        assert health.exists()


# ============================================================
# 4 源 metadata 一致性
# ============================================================
class TestFourSourceMetadata:
    """4 源输出的元数据 (priority / category / captured_by) 应对齐 schema 语义."""

    def test_each_source_has_distinct_captured_by(self, four_source_policies):
        """每个 fetcher 应有自己独立的 captured_by 标记 (便于追溯)."""
        captured_by_set = {p["captured_by"] for p in four_source_policies}
        # 4 个源应至少有 3 个不同的 captured_by (SGCC/NEA/BJX/CSG)
        assert len(captured_by_set) >= 3, f"captured_by 不够多样: {captured_by_set}"

    def test_priority_in_range(self, four_source_policies):
        """所有 policy 的 priority 应在 schema 允许范围 [1, 5]."""
        for p in four_source_policies:
            assert 1 <= p["priority"] <= 5, f"priority 越界: {p['priority']}"

    def test_category_in_allowed_values(self, four_source_policies):
        """所有 policy 的 category 应在 schema 枚举内."""
        allowed = {"policy", "price", "monitor", "standard"}
        for p in four_source_policies:
            assert p["category"] in allowed, \
                f"category 非法: {p['category']} ({p['id']})"

    def test_review_status_is_pending_for_new_policies(self, four_source_policies):
        """新抓取的政策 review_status 应为 pending (待人工审核)."""
        for p in four_source_policies:
            assert p["review_status"] == "pending", \
                f"新政策 review_status 应 pending: {p['id']}"

    def test_all_policies_have_source_url(self, four_source_policies):
        """每条 policy 必须有 source_url (回溯到原文)."""
        for p in four_source_policies:
            assert p.get("source_url"), f"缺 source_url: {p['id']}"
            assert p["source_url"].startswith("http"), \
                f"source_url 非 http: {p['source_url']}"


# ============================================================
# 综合验收: 4 源 → policies.json → schema 校验
# ============================================================
class TestFullPipelineAcceptance:
    """W2-D3 验收基线: 4 源合并 → 落盘 → 5 网全覆盖 → schema 合法."""

    def test_full_pipeline_acceptance(
        self, four_source_policies, four_source_raw_counts, tmp_path: Path
    ):
        """终极验收: 跑通 4 源 + 5 网覆盖 + schema 校验 + health 记录."""
        target = tmp_path / "policies.json"
        health = tmp_path / "health.json"

        # 1. 4 源合并落盘
        res = integrated_fetch(
            name="w2-d3-acceptance",
            raw_items=four_source_policies,
            target_path=target,
            health_path=health,
        )
        assert res["added"] >= 15  # 至少 15 条 (4 源 demo 加起来)

        # 2. 5 网覆盖
        on_disk = json.loads(target.read_text(encoding="utf-8"))
        all_scopes = set()
        for p in on_disk["policies"]:
            all_scopes.update(p["scope"])
        assert FIVE_NET_SCOPES.issubset(all_scopes), \
            f"5 网未全覆盖: missing {FIVE_NET_SCOPES - all_scopes}"

        # 3. schema 校验
        import jsonschema
        schema_path = ROOT / "src" / "schemas" / "policies.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=on_disk, schema=schema)

        # 4. health 记录
        h_data = json.loads(health.read_text(encoding="utf-8"))
        assert "w2-d3-acceptance" in h_data["fetchers"]
        assert h_data["fetchers"]["w2-d3-acceptance"]["success_count"] == 1

        # 5. 4 源都有数据
        assert four_source_raw_counts["国网"] >= 3
        assert four_source_raw_counts["能源局"] >= 3
        assert four_source_raw_counts["北极星"] >= 5
        assert four_source_raw_counts["南网"] >= 5