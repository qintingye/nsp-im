"""
W2-D3 · BJX fetcher 单元测试
=============================
覆盖:
  - fetch_raw: 返回 5-8 条 demo, 必备字段齐全, URL 锚定 bjx.com.cn
  - parse: 标题 → scope 推断; id 稳定可复现; doc_number=None 透传;
           category=monitor (媒体视角)
  - scope 覆盖: grid / water / compute / telecom / pipe / logi + monitor 兜底
  - save: 写入 tmp 文件; dedup 生效; 路径以仓库根为锚

运行:
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe -m pytest tests/test_bjx.py -v
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

from fetchers.bjx import BjxFetcher  # noqa: E402


@pytest.fixture
def fetcher() -> BjxFetcher:
    return BjxFetcher()


# ============================================================
# fetch_raw
# ============================================================
class TestFetchRaw:
    """验证 fetch_raw 返回 demo 数据结构正确."""

    def test_returns_5_to_8_items(self, fetcher: BjxFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        assert isinstance(raw, list)
        assert 5 <= len(raw) <= 8, f"demo 数据应在 5-8 条 (覆盖 5 网), 实际 {len(raw)}"

    def test_each_item_has_required_fields(self, fetcher: BjxFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        for item in raw:
            assert "title" in item and item["title"]
            assert "url" in item and item["url"].startswith("http")
            assert "date" in item and item["date"]
            # W2-D3 BJX 字段: doc_number=None (媒体文章无文号)
            assert "doc_number" in item
            assert item["doc_number"] is None  # BJX 文章全部为 None

    def test_all_urls_belong_to_bjx(self, fetcher: BjxFetcher):
        """所有 URL 应锚定到 bjx.com.cn (防止 demo 串到其他站)."""
        raw = asyncio.run(fetcher.fetch_raw())
        for item in raw:
            assert "bjx.com.cn" in item["url"], f"URL 非北极星域: {item['url']}"

    def test_demo_covers_all_5_net_types(self, fetcher: BjxFetcher):
        """8 条 demo 必须覆盖 5 网 (grid/water/compute/telecom/pipe/logi) + monitor 兜底."""
        raw = asyncio.run(fetcher.fetch_raw())
        from fetchers.bjx import BjxFetcher as _Bjx  # 重复 import 不污染
        all_scopes = set()
        for item in raw:
            for s in _Bjx._guess_scope(item["title"]):
                all_scopes.add(s)
        required = {"grid", "water", "compute", "telecom", "pipe", "logi", "monitor"}
        missing = required - all_scopes
        assert not missing, f"demo 未覆盖的 scope: {missing}"

    def test_dates_are_iso_format(self, fetcher: BjxFetcher):
        """所有 demo 日期应为 ISO YYYY-MM-DD."""
        raw = asyncio.run(fetcher.fetch_raw())
        for item in raw:
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", item["date"]), \
                f"日期非 ISO: {item['date']}"


# ============================================================
# parse
# ============================================================
class TestParse:
    """验证 parse → 标准 policy schema."""

    def test_parse_produces_valid_policies(self, fetcher: BjxFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        assert len(policies) == len(raw)
        for p in policies:
            # schema 必填字段
            for field in ("id", "title", "department", "publish_date"):
                assert field in p, f"缺少必填字段: {field}"
            assert p["department"] == "北极星电力"
            # id 格式: P-BJX-YYYYMMDD-NNNN
            assert p["id"].startswith("P-BJX-")
            assert re.match(r"^P-BJX-\d{8}-\d{4}$", p["id"]), f"id 格式错: {p['id']}"
            # 日期 ISO
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", p["publish_date"])
            # captured_by
            assert p["captured_by"] == "bjx-fetcher-v0.1"
            assert p["review_status"] == "pending"

    def test_id_is_stable_across_runs(self, fetcher: BjxFetcher):
        """同一 (date, url, title) 必须生成同一 id (sha1 → 跨进程稳定)."""
        raw = asyncio.run(fetcher.fetch_raw())
        p1 = fetcher.parse(raw)
        p2 = fetcher.parse(raw)
        ids1 = [p["id"] for p in p1]
        ids2 = [p["id"] for p in p2]
        assert ids1 == ids2

    def test_doc_number_is_none_for_media_source(self, fetcher: BjxFetcher):
        """BJX 是媒体源, doc_number 全部为 None (媒体文章无文号)."""
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        for p in policies:
            assert p["doc_number"] is None

    def test_category_is_monitor_for_bjx(self, fetcher: BjxFetcher):
        """BJX 文章归类为 monitor (媒体动态/解读, 非政府红头文)."""
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        for p in policies:
            assert p["category"] == "monitor"
            assert p["priority"] == 2  # 媒体视角低于 NEA priority=1

    def test_scope_inference_grid_5g_pipeline(self, fetcher: BjxFetcher):
        """包含 '虚拟电厂'/'5G'/'通信切片' 的标题应被归入 grid + telecom."""
        raw = [{
            "title": "《虚拟电厂 5G 通信切片落地, 调度响应提升 90%》",
            "url": "https://www.bjx.com.cn/x.html", "date": "2024-06-20",
            "doc_number": None,
        }]
        policies = fetcher.parse(raw)
        assert "grid" in policies[0]["scope"]
        assert "telecom" in policies[0]["scope"]
        assert "monitor" in policies[0]["scope"]  # 兜底

    def test_scope_inference_pumped_hydro_water(self, fetcher: BjxFetcher):
        """'抽水蓄能' 应归入 water (精确匹配, 不命中其它 keyword)."""
        raw = [{
            "title": "《抽水蓄能装机突破 5000 万千瓦》",
            "url": "https://www.bjx.com.cn/y.html", "date": "2024-05-28",
            "doc_number": None,
        }]
        policies = fetcher.parse(raw)
        assert "water" in policies[0]["scope"]

    def test_scope_inference_heavy_truck_logi(self, fetcher: BjxFetcher):
        """'重卡换电干线' 应归入 logi."""
        raw = [{
            "title": "《重卡换电干线网络加速布局》",
            "url": "https://www.bjx.com.cn/z.html", "date": "2024-07-15",
            "doc_number": None,
        }]
        policies = fetcher.parse(raw)
        assert "logi" in policies[0]["scope"]

    def test_scope_inference_pipe_for_oil_gas(self, fetcher: BjxFetcher):
        """'西气东输'/'油气长输' 应归入 pipe."""
        raw = [{
            "title": "《西气东输四线投产》",
            "url": "https://www.bjx.com.cn/o.html", "date": "2024-08-10",
            "doc_number": None,
        }]
        policies = fetcher.parse(raw)
        assert "pipe" in policies[0]["scope"]

    def test_scope_inference_compute_datacenter(self, fetcher: BjxFetcher):
        """'算电协同'/'数据中心' 应归入 compute."""
        raw = [{
            "title": "《数据中心算电协同新范式》",
            "url": "https://www.bjx.com.cn/c.html", "date": "2024-05-10",
            "doc_number": None,
        }]
        policies = fetcher.parse(raw)
        assert "compute" in policies[0]["scope"]

    def test_scope_monitor_fallback_for_uncategorized(self, fetcher: BjxFetcher):
        """未命中 5 网 keyword 的标题应只剩 monitor (兜底)."""
        raw = [{
            "title": "《全国碳市场扩容: 钢铁/铝/水泥三大行业纳入倒计时》",
            "url": "https://www.bjx.com.cn/m.html", "date": "2024-09-12",
            "doc_number": None,
        }]
        policies = fetcher.parse(raw)
        # 关键词扫描: 没有 5 网 keyword 命中 → scope 应只剩 ["monitor"]
        assert policies[0]["scope"] == ["monitor"], \
            f"应只剩 monitor, 实际 {policies[0]['scope']}"


# ============================================================
# save
# ============================================================
class TestSave:
    """验证 BaseFetcher.save() 集成: dedup + atomic write."""

    def test_save_writes_to_repo_path(self, fetcher: BjxFetcher, tmp_path: Path):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        result = fetcher.save(policies, target=str(tmp_path / "policies.json"))
        assert result["added"] == len(policies)
        assert result["total"] == len(policies)
        assert Path(result["path"]).exists()

        on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        assert "policies" in on_disk
        ids = {p["id"] for p in on_disk["policies"]}
        for p in policies:
            assert p["id"] in ids

    def test_save_dedups_against_existing(self, fetcher: BjxFetcher, tmp_path: Path):
        """第二次调用同 id 应去重, 不应膨胀."""
        target = tmp_path / "policies.json"
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        # 第 1 次: 全新增
        r1 = fetcher.save(policies, target=str(target))
        assert r1["added"] == len(policies)
        # 第 2 次: 同样的 (id 完全相同) → 0 新增
        r2 = fetcher.save(policies, target=str(target))
        assert r2["added"] == 0
        assert r2["duplicates"] >= len(policies)
        # 文件内容不变 (长度稳定)
        after = json.loads(target.read_text(encoding="utf-8"))
        assert len(after["policies"]) == len(policies)

    def test_default_target_is_repo_data_policies(self, fetcher: BjxFetcher):
        """不传 target 时, save() 必须指向仓库根 data/policies.json (P0-2 修复)."""
        from fetchers.base import REPO_DATA_DIR
        expected = REPO_DATA_DIR / "policies.json"
        from fetchers.base import BASE_FILE, REPO_ROOT
        assert REPO_ROOT == BASE_FILE.parents[2]
        assert expected.parent.name == "data"
        # 真实落盘不在测试里做 (会污染 data/policies.json), 由 CI 集成测覆盖

    def test_save_5_net_types_preserved(self, fetcher: BjxFetcher, tmp_path: Path):
        """save 后, 落盘文件中应仍可见 5 网 + monitor 全覆盖."""
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        target = tmp_path / "policies.json"
        fetcher.save(policies, target=str(target))

        on_disk = json.loads(target.read_text(encoding="utf-8"))
        all_scopes = set()
        for p in on_disk["policies"]:
            all_scopes.update(p["scope"])
        required = {"grid", "water", "compute", "telecom", "pipe", "logi", "monitor"}
        missing = required - all_scopes
        assert not missing, f"落盘后丢失 scope: {missing}"


# ============================================================
# 集成: fetch_raw → parse → save 端到端
# ============================================================
class TestEndToEnd:
    def test_full_pipeline_produces_5_to_8_policies(
        self, fetcher: BjxFetcher, tmp_path: Path
    ):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        result = fetcher.save(policies, target=str(tmp_path / "policies.json"))

        assert result["added"] >= 5
        assert result["total"] >= 5

        on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        # 所有 policy 必须是 BJX 部门
        for p in on_disk["policies"]:
            assert p["department"] == "北极星电力"
            assert p["id"].startswith("P-BJX-")
            assert p["category"] == "monitor"
            assert p["doc_number"] is None
            assert p["priority"] == 2