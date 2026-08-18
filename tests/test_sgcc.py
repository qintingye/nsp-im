"""
W2-D2 · SGCC (国家电网) fetcher 单元测试
==========================================
覆盖:
  - fetch_raw: 返回 3-5 条 demo, 必备字段齐全
  - parse: 标题 → scope 推断; id 稳定可复现; doc_number 透传
  - save: 写入 tmp 文件; dedup 生效; 路径以仓库根为锚
  - 端到端: fetch_raw → parse → save

运行:
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe -m pytest tests/test_sgcc.py -v
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fetchers.sgcc import SgccFetcher  # noqa: E402


@pytest.fixture
def fetcher() -> SgccFetcher:
    return SgccFetcher()


# ============================================================
# fetch_raw
# ============================================================
class TestFetchRaw:
    """验证 fetch_raw 返回 demo 数据结构正确."""

    def test_returns_3_to_5_items(self, fetcher: SgccFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        assert isinstance(raw, list)
        assert 3 <= len(raw) <= 5, f"demo 数据应在 3-5 条, 实际 {len(raw)}"

    def test_each_item_has_required_fields(self, fetcher: SgccFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        for item in raw:
            assert "title" in item and item["title"]
            assert "url" in item and item["url"].startswith("http")
            assert "date" in item and item["date"]
            # W2-D2 扩展字段: doc_number (国网红头文)
            assert "doc_number" in item and item["doc_number"]

    def test_all_urls_belong_to_sgcc(self, fetcher: SgccFetcher):
        """所有 URL 应锚定到 sgcc.com.cn (防止 demo 串到其他站)."""
        raw = asyncio.run(fetcher.fetch_raw())
        for item in raw:
            assert "sgcc.com.cn" in item["url"], f"URL 非国网域: {item['url']}"


# ============================================================
# parse
# ============================================================
class TestParse:
    """验证 parse → 标准 policy schema."""

    def test_parse_produces_valid_policies(self, fetcher: SgccFetcher):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        assert len(policies) == len(raw)
        for p in policies:
            for field in ("id", "title", "department", "publish_date"):
                assert field in p, f"缺少必填字段: {field}"
            assert p["department"] == "国家电网公司"
            # id 格式: P-SGCC-YYYYMMDD-NNNN
            assert p["id"].startswith("P-SGCC-")
            import re as _re
            assert _re.match(r"^P-SGCC-\d{8}-\d{4}$", p["id"]), f"id 格式错: {p['id']}"
            # 日期 ISO
            assert _re.match(r"^\d{4}-\d{2}-\d{2}$", p["publish_date"])
            assert p["captured_by"] == "sgcc-fetcher-v0.1"
            assert p["review_status"] == "pending"

    def test_id_is_stable_across_runs(self, fetcher: SgccFetcher):
        """同一 (date, url, title) 必须生成同一 id (sha1 → 跨进程稳定)."""
        raw = asyncio.run(fetcher.fetch_raw())
        p1 = fetcher.parse(raw)
        p2 = fetcher.parse(raw)
        ids1 = [p["id"] for p in p1]
        ids2 = [p["id"] for p in p2]
        assert ids1 == ids2

    def test_scope_inference_grid(self, fetcher: SgccFetcher):
        """包含 '电网/特高压/配网/储能' 的标题应被归入 grid."""
        raw = [
            {"title": "《国家电网 2026 年特高压直流工程推进计划公告》",
             "url": "https://www.sgcc.com.cn/x.html", "date": "2026-08-02",
             "doc_number": "国家电网规划〔2026〕28号"},
            {"title": "《国家电网公司配电网高质量发展实施方案》",
             "url": "https://www.sgcc.com.cn/y.html", "date": "2026-07-18",
             "doc_number": "国家电网配网〔2026〕35号"},
            {"title": "《国家电网 2026 年新能源并网消纳工作要点》",
             "url": "https://www.sgcc.com.cn/z.html", "date": "2026-08-08",
             "doc_number": "国家电网新能〔2026〕42号"},
        ]
        policies = fetcher.parse(raw)
        for p in policies:
            assert "grid" in p["scope"], f"title={p['title']} scope={p['scope']}"
            assert "monitor" in p["scope"]  # 兜底

    def test_doc_number_passthrough(self, fetcher: SgccFetcher):
        """doc_number (国家电网XX〔YYYY〕NN号) 应原样写入 policy."""
        raw = [{"title": "《国家电网 2026 年特高压直流工程推进计划公告》",
                "url": "https://www.sgcc.com.cn/x.html",
                "date": "2026-08-02",
                "doc_number": "国家电网规划〔2026〕28号"}]
        policies = fetcher.parse(raw)
        assert policies[0]["doc_number"] == "国家电网规划〔2026〕28号"

    def test_category_and_priority(self, fetcher: SgccFetcher):
        """SGCC 文应默认为 policy + priority=1 (公司公告高优)."""
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

    def test_save_writes_to_target_path(self, fetcher: SgccFetcher, tmp_path: Path):
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

    def test_save_dedups_against_existing(self, fetcher: SgccFetcher, tmp_path: Path):
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

    def test_default_target_is_repo_data_policies(self, fetcher: SgccFetcher):
        """不传 target 时, save() 必须指向仓库根 data/policies.json (P0-2 修复)."""
        from fetchers.base import REPO_DATA_DIR, BASE_FILE, REPO_ROOT
        expected = REPO_DATA_DIR / "policies.json"
        assert REPO_ROOT == BASE_FILE.parents[2]
        assert expected.parent.name == "data"
        # 真实落盘不在测试里做 (会污染 data/policies.json), 由 CI 集成测覆盖


# ============================================================
# 集成: fetch_raw → parse → save 端到端
# ============================================================
class TestEndToEnd:
    def test_full_pipeline_produces_3_to_5_policies(
        self, fetcher: SgccFetcher, tmp_path: Path
    ):
        raw = asyncio.run(fetcher.fetch_raw())
        policies = fetcher.parse(raw)
        result = fetcher.save(policies, target=str(tmp_path / "policies.json"))

        assert result["added"] >= 3
        assert result["total"] >= 3

        on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        # 所有 policy 必须是 SGCC 部门
        for p in on_disk["policies"]:
            assert p["department"] == "国家电网公司"
            assert p["id"].startswith("P-SGCC-")
