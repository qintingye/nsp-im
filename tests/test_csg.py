"""
W2-D3 · CSG fetcher 单元测试
=============================
覆盖:
  - fetch_raw: 返回 5-7 条 demo, 必备字段齐全, URL 锚定 csg.cn
  - parse: 标题 → scope 推断; id 稳定; 央企文号透传; category=policy
  - scope 覆盖: grid / water / compute / telecom / pipe / logi + monitor
  - save: 写入 tmp 文件; dedup 生效

运行:
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe -m pytest tests/test_csg.py -v
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fetchers.csg import CsgFetcher  # noqa: E402


@pytest.fixture
def fetcher() -> CsgFetcher:
    return CsgFetcher()


# ============================================================
# fetch_raw
# ============================================================
class TestFetchRaw:
    """验证 fetch_raw 返回 demo 数据结构正确."""

    def test_returns_5_to_7_items(self, fetcher: CsgFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        assert isinstance(raw, list)
        assert 5 <= len(raw) <= 7, f"demo 数据应在 5-7 条, 实际 {len(raw)}"

    def test_each_item_has_required_fields(self, fetcher: CsgFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        for item in raw:
            assert "title" in item and item["title"]
            assert "url" in item and item["url"].startswith("http")
            assert "date" in item and item["date"]
            # W2-D3 CSG 字段: 央企文号 (与 NEA 同结构)
            assert "doc_number" in item and item["doc_number"]
            assert "南方电网" in item["doc_number"]

    def test_all_urls_belong_to_csg(self, fetcher: CsgFetcher):
        """所有 URL 应锚定到 csg.cn (防止 demo 串到其他站)."""
        raw = asyncio.run(fetcher.fetch_raw())
        for item in raw:
            assert "csg.cn" in item["url"], f"URL 非南方电网域: {item['url']}"

    def test_demo_covers_5_net_types(self, fetcher: CsgFetcher):
        """CSG demo 应覆盖 5 网 (grid/water/compute/telecom/pipe/logi) + monitor."""
        from fetchers.csg import CsgFetcher as _Csg
        all_scopes = set()
        for item in asyncio.run(fetcher.fetch_raw()):
            for s in _Csg._guess_scope(item["title"]):
                all_scopes.add(s)
        required = {"grid", "water", "compute", "telecom", "pipe", "logi", "monitor"}
        missing = required - all_scopes
        assert not missing, f"demo 未覆盖的 scope: {missing}"


# ============================================================
# parse
# ============================================================
class TestParse:
    """验证 parse → 标准 policy schema."""

    def test_parse_produces_valid_policies(self, fetcher: CsgFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        assert len(policies) == len(raw)
        for p in policies:
            for field in ("id", "title", "department", "publish_date"):
                assert field in p, f"缺少必填字段: {field}"
            assert p["department"] == "南方电网公司"
            assert p["id"].startswith("P-CSG-")
            assert re.match(r"^P-CSG-\d{8}-\d{4}$", p["id"])
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", p["publish_date"])
            assert p["captured_by"] == "csg-fetcher-v0.1"
            assert p["review_status"] == "pending"

    def test_id_is_stable_across_runs(self, fetcher: CsgFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        p1 = fetcher.parse(raw)
        p2 = fetcher.parse(raw)
        ids1 = [p["id"] for p in p1]
        ids2 = [p["id"] for p in p2]
        assert ids1 == ids2

    def test_doc_number_passthrough(self, fetcher: CsgFetcher):
        """央企文号 (南方电网XX〔YYYY〕NN号) 应原样写入."""
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        for p in policies:
            assert p["doc_number"] is not None
            assert "南方电网" in p["doc_number"]
            assert "〔" in p["doc_number"]  # 央企文号含书名号

    def test_category_is_policy_with_high_priority(self, fetcher: CsgFetcher):
        """CSG 央企公告归类为 policy + priority=1 (执行约束力)."""
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        for p in policies:
            assert p["category"] == "policy"
            assert p["priority"] == 1

    def test_scope_grid_for_virtual_plant(self, fetcher: CsgFetcher):
        """'虚拟电厂'/'调度' 应归入 grid."""
        raw = [{
            "title": "《南方区域虚拟电厂接入调度运行管理规定》",
            "url": "https://www.csg.cn/a.html", "date": "2024-04-22",
            "doc_number": "南方电网调〔2024〕12号",
        }]
        policies = fetcher.parse(raw)
        assert "grid" in policies[0]["scope"]

    def test_scope_compute_for_datacenter(self, fetcher: CsgFetcher):
        """'数据中心'+'绿电直供' 应归入 compute."""
        raw = [{
            "title": "《南方电网数据中心绿电直供试点方案》",
            "url": "https://www.csg.cn/b.html", "date": "2024-05-06",
            "doc_number": "南方电网市场〔2024〕18号",
        }]
        policies = fetcher.parse(raw)
        assert "compute" in policies[0]["scope"]
        assert "grid" in policies[0]["scope"]  # "绿电直供" 含 "电网" 关键词

    def test_scope_water_for_pumped_storage(self, fetcher: CsgFetcher):
        """'抽水蓄能' 应归入 water."""
        raw = [{
            "title": "《南方电网抽水蓄能装机规划》",
            "url": "https://www.csg.cn/c.html", "date": "2024-09-05",
            "doc_number": "南方电网规划〔2024〕52号",
        }]
        policies = fetcher.parse(raw)
        assert "water" in policies[0]["scope"]


# ============================================================
# save
# ============================================================
class TestSave:
    def test_save_writes_to_repo_path(self, fetcher: CsgFetcher, tmp_path: Path):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        result = fetcher.save(policies, target=str(tmp_path / "policies.json"))
        assert result["added"] == len(policies)
        assert result["total"] == len(policies)

        on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        ids = {p["id"] for p in on_disk["policies"]}
        for p in policies:
            assert p["id"] in ids

    def test_save_dedups_against_existing(self, fetcher: CsgFetcher, tmp_path: Path):
        target = tmp_path / "policies.json"
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        r1 = fetcher.save(policies, target=str(target))
        assert r1["added"] == len(policies)
        r2 = fetcher.save(policies, target=str(target))
        assert r2["added"] == 0
        assert r2["duplicates"] >= len(policies)

    def test_default_target_is_repo_data_policies(self, fetcher: CsgFetcher):
        """不传 target 时, save() 必须指向仓库根 data/policies.json (P0-2 修复)."""
        from fetchers.base import REPO_DATA_DIR, BASE_FILE, REPO_ROOT
        expected = REPO_DATA_DIR / "policies.json"
        assert REPO_ROOT == BASE_FILE.parents[2]
        assert expected.parent.name == "data"


# ============================================================
# 集成: fetch_raw → parse → save 端到端
# ============================================================
class TestEndToEnd:
    def test_full_pipeline_produces_5_to_7_policies(
        self, fetcher: CsgFetcher, tmp_path: Path
    ):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        result = fetcher.save(policies, target=str(tmp_path / "policies.json"))

        assert result["added"] >= 5
        assert result["total"] >= 5

        on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        for p in on_disk["policies"]:
            assert p["department"] == "南方电网公司"
            assert p["id"].startswith("P-CSG-")
            assert p["category"] == "policy"
            assert p["priority"] == 1