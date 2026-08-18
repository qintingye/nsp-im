"""
W2-D3 四源集成测试: NEA + CSG + SGCC + BJX 全链路

四源 = 政府 (能源局) + 央企 (国网 / 南网) + 行业媒体 (北极星),
构成 "政策方向 → 行业实操 → 招标采购 → 媒体解读" 的纵向证据链。

验证:
  1. 每个 fetcher 的 fetch_with_retry() 都能跑通 (fetch_raw → parse)
  2. 产出条目符合 policies schema 关键字段 (department 带公司后缀等)
  3. fetch_raw 原始条目数在 3-8 条区间
  4. 多源合并 + deduplicate() 去重, 总数 >= 15 条, id 全局唯一
  5. 注入重复条目能被 dedup 正确剔除

注: 用 asyncio.run 驱动协程, 不依赖 pytest-asyncio 插件。
    NDRC 为真实网络抓取源, 离线环境不纳入本集成测试 (见 tests/test_d3.py)。
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetchers.bjx import BjxFetcher  # noqa: E402
from src.fetchers.csg import CsgFetcher  # noqa: E402
from src.fetchers.nea import NeaFetcher  # noqa: E402
from src.fetchers.sgcc import SgccFetcher  # noqa: E402
from src.utils.dedup import deduplicate  # noqa: E402

# 4 源: 政府 + 央企双源 + 行业媒体 (均为 W2 离线 demo, 可确定性集成)
FETCHER_CLASSES = [NeaFetcher, CsgFetcher, SgccFetcher, BjxFetcher]

EXPECTED_DEPARTMENTS = {
    "能源局": "国家能源局",
    "南网": "南方电网公司",
    "国网": "国家电网公司",
    "北极星": "北极星电力",
}

EXPECTED_ID_PREFIX = {
    "能源局": "NEA",
    "南网": "CSG",
    "国网": "SGCC",
    "北极星": "BJX",
}

REQUIRED_FIELDS = (
    "id", "title", "department", "publish_date", "effective_date", "category",
    "scope", "priority", "summary", "source_url", "captured_at",
    "captured_by", "tags", "review_status",
)


def _fetch_all() -> dict[str, list[dict]]:
    """并发跑全部 fetcher 的 fetch_with_retry, 返回 {源名: 政策列表}."""
    async def _run():
        fetchers = [cls() for cls in FETCHER_CLASSES]
        results = await asyncio.gather(*(f.fetch_with_retry() for f in fetchers))
        return {f.name: items for f, items in zip(fetchers, results)}

    return asyncio.run(_run())


@pytest.fixture(scope="module")
def all_policies() -> dict[str, list[dict]]:
    return _fetch_all()


class TestEachSourceFetches:
    """逐源验证 fetch_raw / fetch_with_retry 可跑通."""

    @pytest.mark.parametrize("cls", FETCHER_CLASSES, ids=lambda c: c.__name__)
    def test_fetch_raw_item_count(self, cls):
        raw = asyncio.run(cls().fetch_raw())
        assert isinstance(raw, list)
        assert 3 <= len(raw) <= 8, f"{cls.__name__} fetch_raw 应 3-8 条, 实际 {len(raw)}"
        for it in raw:
            assert it.get("title"), f"{cls.__name__} 原始条目缺 title"
            assert it.get("url"), f"{cls.__name__} 原始条目缺 url"

    @pytest.mark.parametrize("cls", FETCHER_CLASSES, ids=lambda c: c.__name__)
    def test_fetch_with_retry_returns_parsed_policies(self, cls):
        fetcher = cls()
        raw = asyncio.run(fetcher.fetch_raw())
        policies = asyncio.run(fetcher.fetch_with_retry())
        assert isinstance(policies, list)
        assert len(policies) == len(raw), f"{cls.__name__} parse 后条数应等于原始条数"
        for p in policies:
            for field in REQUIRED_FIELDS:
                assert field in p, f"{cls.__name__} 缺字段 {field}"
            assert p["review_status"] == "pending"
            assert p["priority"] in (1, 2, 3)
            assert isinstance(p["scope"], list) and p["scope"]
            assert "monitor" in p["scope"], f"{cls.__name__} scope 应含 monitor 兜底"
            assert p["source_url"].startswith("http")


class TestMultiSourceMerge:
    """多源合并 + 去重."""

    def test_all_four_sources_present(self, all_policies):
        assert set(all_policies) == set(EXPECTED_DEPARTMENTS)
        for name, items in all_policies.items():
            assert items, f"{name} 未产出任何条目"

    def test_departments_match_expected(self, all_policies):
        for name, expected in EXPECTED_DEPARTMENTS.items():
            for p in all_policies[name]:
                assert p["department"] == expected, f"{name} department 应为 {expected}"

    def test_id_prefixes_unique_per_source(self, all_policies):
        for name, items in all_policies.items():
            prefixes = {p["id"].split("-")[1] for p in items}
            assert prefixes == {EXPECTED_ID_PREFIX[name]}, f"{name} id 前缀异常: {prefixes}"
        assert len(set(EXPECTED_ID_PREFIX.values())) == len(EXPECTED_ID_PREFIX)

    def test_merged_total_at_least_15(self, all_policies):
        merged = [p for items in all_policies.values() for p in items]
        assert len(merged) >= 15, f"4 源合并后应 >= 15 条, 实际 {len(merged)}"

    def test_dedup_keeps_all_distinct_items(self, all_policies):
        merged = [p for items in all_policies.values() for p in items]
        result = deduplicate(merged)
        unique = result["unique"]
        assert len(unique) >= 15, f"去重后应 >= 15 条, 实际 {len(unique)}"
        assert len(unique) == len(merged), (
            f"跨源无真重复, 不应删除: input={len(merged)} unique={len(unique)}"
        )
        assert result["stats"]["input"] == len(merged)

    def test_dedup_removes_injected_duplicate(self, all_policies):
        merged = [p for items in all_policies.values() for p in items]
        result = deduplicate(merged + [dict(merged[0])])
        assert len(result["unique"]) == len(merged)
        removed = result["stats"]["removed_by_id"] + result["stats"]["removed_by_url"]
        assert removed >= 1, "注入的重复条目未被剔除"

    def test_ids_globally_unique_after_merge(self, all_policies):
        ids = [p["id"] for items in all_policies.values() for p in items]
        assert len(set(ids)) == len(ids), "合并后 id 应全局唯一"

    def test_scope_coverage_across_sources(self, all_policies):
        scopes = {s for items in all_policies.values() for p in items for s in p["scope"]}
        assert "grid" in scopes, "4 源合并应覆盖 grid"
        assert len(scopes) >= 4, f"4 源合并 scope 覆盖过窄: {scopes}"
