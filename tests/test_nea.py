"""
W2-D1 · NEA fetcher 单元测试
============================
覆盖:
  - fetch_raw: 返回 3-5 条 demo, 必备字段齐全
  - parse: 标题 → scope 推断; id 稳定可复现; doc_number 透传
  - save: 写入 tmp 文件; dedup 生效; 路径以仓库根为锚

运行:
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe -m pytest tests/test_nea.py -v
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fetchers.nea import NeaFetcher  # noqa: E402


@pytest.fixture
def fetcher() -> NeaFetcher:
    return NeaFetcher()


# ============================================================
# fetch_raw
# ============================================================
class TestFetchRaw:
    """验证 fetch_raw 返回 demo 数据结构正确."""

    def test_returns_3_to_5_items(self, fetcher: NeaFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        assert isinstance(raw, list)
        assert 3 <= len(raw) <= 5, f"demo 数据应在 3-5 条, 实际 {len(raw)}"

    def test_each_item_has_required_fields(self, fetcher: NeaFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        for item in raw:
            assert "title" in item and item["title"]
            assert "url" in item and item["url"].startswith("http")
            assert "date" in item and item["date"]
            # W2-D1 扩展字段: doc_number (能源局红头文)
            assert "doc_number" in item and item["doc_number"]

    def test_all_urls_belong_to_nea(self, fetcher: NeaFetcher):
        """所有 URL 应锚定到 nea.gov.cn (防止 demo 串到其他站)."""
        raw = asyncio.run(fetcher.fetch_raw())
        for item in raw:
            assert "nea.gov.cn" in item["url"], f"URL 非能源局域: {item['url']}"


# ============================================================
# parse
# ============================================================
class TestParse:
    """验证 parse → 标准 policy schema."""

    def test_parse_produces_valid_policies(self, fetcher: NeaFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        assert len(policies) == len(raw)
        for p in policies:
            # schema 必填字段
            for field in ("id", "title", "department", "publish_date"):
                assert field in p, f"缺少必填字段: {field}"
            assert p["department"] == "国家能源局"
            # id 格式: P-NEA-YYYYMMDD-NNNN
            assert p["id"].startswith("P-NEA-")
            import re as _re
            assert _re.match(r"^P-NEA-\d{8}-\d{4}$", p["id"]), f"id 格式错: {p['id']}"
            # 日期 ISO
            assert _re.match(r"^\d{4}-\d{2}-\d{2}$", p["publish_date"])
            # captured_by
            assert p["captured_by"] == "nea-fetcher-v0.1"
            assert p["review_status"] == "pending"

    def test_id_is_stable_across_runs(self, fetcher: NeaFetcher):
        """同一 (date, url, title) 必须生成同一 id (sha1 → 跨进程稳定)."""
        raw = asyncio.run(fetcher.fetch_raw())
        p1 = fetcher.parse(raw)
        p2 = fetcher.parse(raw)
        ids1 = [p["id"] for p in p1]
        ids2 = [p["id"] for p in p2]
        assert ids1 == ids2

    def test_scope_inference_grid(self, fetcher: NeaFetcher):
        """包含 '电力/电网/储能/光伏' 的标题应被归入 grid."""
        raw = [
            {"title": "《电力领域综合监管工作通知》",
             "url": "https://www.nea.gov.cn/x.html", "date": "2024-04-15",
             "doc_number": "国能发监管〔2024〕45号"},
            {"title": "《新能源消纳监测预警管理办法》",
             "url": "https://www.nea.gov.cn/y.html", "date": "2024-05-09",
             "doc_number": "国能发新能〔2024〕62号"},
            {"title": "《新型储能并网调度运行管理规定》",
             "url": "https://www.nea.gov.cn/z.html", "date": "2024-06-18",
             "doc_number": "国能发电力〔2024〕78号"},
        ]
        policies = fetcher.parse(raw)
        for p in policies:
            assert "grid" in p["scope"], f"title={p['title']} scope={p['scope']}"
            assert "monitor" in p["scope"]  # 兜底

    def test_scope_inference_pipe_for_oil_gas(self, fetcher: NeaFetcher):
        """油气管道类应归入 pipe."""
        raw = [
            {"title": "《油气长输管道保护与安全监管工作要点》",
             "url": "https://www.nea.gov.cn/o.html", "date": "2024-07-02",
             "doc_number": "国能发油储〔2024〕89号"},
        ]
        policies = fetcher.parse(raw)
        assert "pipe" in policies[0]["scope"]
        assert "monitor" in policies[0]["scope"]

    def test_doc_number_passthrough(self, fetcher: NeaFetcher):
        """doc_number (国能发XX〔YYYY〕NN号) 应原样写入 policy."""
        raw = [{"title": "《电力领域综合监管工作通知》",
                "url": "https://www.nea.gov.cn/x.html",
                "date": "2024-04-15",
                "doc_number": "国能发监管〔2024〕45号"}]
        policies = fetcher.parse(raw)
        assert policies[0]["doc_number"] == "国能发监管〔2024〕45号"

    def test_category_and_priority(self, fetcher: NeaFetcher):
        """NEA 文应默认为 policy + priority=1 (监管类高优)."""
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        for p in policies:
            assert p["category"] == "policy"
            assert p["priority"] == 1


# ============================================================
# save
# ============================================================
class TestSave:
    """验证 BaseFetcher.save() 集成: dedup + atomic write."""

    def test_save_writes_to_repo_path(self, fetcher: NeaFetcher, tmp_path: Path):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        result = fetcher.save(policies, target=str(tmp_path / "policies.json"))
        assert result["added"] == len(policies)
        assert result["total"] == len(policies)
        assert Path(result["path"]).exists()

        # 内容校验
        on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        assert "policies" in on_disk
        ids = {p["id"] for p in on_disk["policies"]}
        for p in policies:
            assert p["id"] in ids

    def test_save_dedups_against_existing(self, fetcher: NeaFetcher, tmp_path: Path):
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

    def test_default_target_is_repo_data_policies(self, fetcher: NeaFetcher):
        """不传 target 时, save() 必须指向仓库根 data/policies.json (P0-2 修复)."""
        from fetchers.base import REPO_DATA_DIR
        # 用 REPO_DATA_DIR 解析, 而不是 str(REPO_DATA_DIR) - 因为 Path() 检查
        expected = REPO_DATA_DIR / "policies.json"
        # 只校验 BASE_FILE 路径解析逻辑是否锁定了仓库根
        from fetchers.base import BASE_FILE, REPO_ROOT
        assert REPO_ROOT == BASE_FILE.parents[2]
        assert expected.parent.name == "data"
        # 真实落盘不在测试里做 (会污染 data/policies.json), 由 CI 集成测覆盖


# ============================================================
# 集成: fetch_raw → parse → save 端到端
# ============================================================
class TestEndToEnd:
    def test_full_pipeline_produces_3_to_5_policies(
        self, fetcher: NeaFetcher, tmp_path: Path
    ):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        result = fetcher.save(policies, target=str(tmp_path / "policies.json"))

        assert result["added"] >= 3
        assert result["total"] >= 3

        on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        # 所有 policy 必须是 NEA 部门
        for p in on_disk["policies"]:
            assert p["department"] == "国家能源局"
            assert p["id"].startswith("P-NEA-")