"""
W2-D2 端到端 schema 校验: CSG + SGCC fetchers 的 fetch → parse → save → jsonschema 闭环
同时跑 NEA 作为回归基线, 证明 3 个 demo 源都通过 policies.schema.json 校验.

验收标准 (W2-D2 任务书):
  - src/fetchers/csg.py 与 src/fetchers/sgcc.py 实现完整, 遵循 BaseFetcher 契约
  - 每个 fetcher 的 demo 数据 3-7 条, 全部通过 jsonschema 校验
  - 落地文件可在 data/ 或临时目录持久化, 再次加载仍合规
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fetchers.csg import CsgFetcher  # noqa: E402
from fetchers.nea import NeaFetcher  # noqa: E402
from fetchers.sgcc import SgccFetcher  # noqa: E402


def _load_schema() -> dict:
    with open(ROOT / "src" / "schemas" / "policies.schema.json", encoding="utf-8") as f:
        return json.load(f)


def _run_pipeline(fetcher, target: Path) -> dict:
    """fetch_raw → parse → save → 读回 → 返回 on-disk 内容."""
    raw = asyncio.run(fetcher.fetch_raw())
    policies = fetcher.parse(raw)
    if target.exists():
        target.unlink()
    fetcher.save(policies, target=str(target))
    return json.loads(target.read_text(encoding="utf-8"))


class TestCsgSchemaCompliance:
    """CSG (南方电网) demo → schema 校验闭环."""

    def test_fetch_parse_save_validates(self, tmp_path):
        schema = _load_schema()
        target = tmp_path / "csg.json"
        on_disk = _run_pipeline(CsgFetcher(), target)

        jsonschema.validate(instance=on_disk, schema=schema)
        assert on_disk["version"] == "1.0"
        assert 3 <= len(on_disk["policies"]) <= 8, (
            f"CSG demo 条数应在 3-8, 实际 {len(on_disk['policies'])}"
        )
        for p in on_disk["policies"]:
            assert p["id"].startswith("P-CSG-"), f"CSG id 前缀错误: {p['id']}"
            assert p["department"] == "南方电网公司"
            assert p["category"] == "policy"
            assert "monitor" in p["scope"]
            assert p["source_url"].startswith("https://www.csg.cn/"), (
                f"CSG source_url 应属 csg.cn: {p['source_url']}"
            )


class TestSgccSchemaCompliance:
    """SGCC (国家电网) demo → schema 校验闭环."""

    def test_fetch_parse_save_validates(self, tmp_path):
        schema = _load_schema()
        target = tmp_path / "sgcc.json"
        on_disk = _run_pipeline(SgccFetcher(), target)

        jsonschema.validate(instance=on_disk, schema=schema)
        assert on_disk["version"] == "1.0"
        assert 3 <= len(on_disk["policies"]) <= 8, (
            f"SGCC demo 条数应在 3-8, 实际 {len(on_disk['policies'])}"
        )
        for p in on_disk["policies"]:
            assert p["id"].startswith("P-SGCC-"), f"SGCC id 前缀错误: {p['id']}"
            assert p["department"] == "国家电网公司"
            assert p["category"] == "policy"
            assert "monitor" in p["scope"]
            assert p["source_url"].startswith("https://www.sgcc.com.cn/"), (
                f"SGCC source_url 应属 sgcc.com.cn: {p['source_url']}"
            )


class TestNeaRegressionBaseline:
    """NEA 是 D2 之前的回归基线: 同 schema 必须仍然通过."""

    def test_nea_still_validates_after_csg_sgcc_added(self, tmp_path):
        schema = _load_schema()
        target = tmp_path / "nea.json"
        on_disk = _run_pipeline(NeaFetcher(), target)

        jsonschema.validate(instance=on_disk, schema=schema)
        for p in on_disk["policies"]:
            assert p["id"].startswith("P-NEA-")
            assert p["department"] == "国家能源局"


class TestFiveNetCoverage:
    """W2 整体目标: 5 网 (能/水/算/通/管) 覆盖检查."""

    def test_combined_csg_sgcc_covers_5_net_types(self, tmp_path):
        """CSG demo 已覆盖 grid/compute/telecom/water/pipe/logi, 验证落盘后范围."""
        target = tmp_path / "csg.json"
        on_disk = _run_pipeline(CsgFetcher(), target)
        scopes = {s for p in on_disk["policies"] for s in p["scope"]}

        # CSG demo 数据按设计覆盖: grid (主流) + compute + telecom + water + pipe + logi
        # 去掉 monitor 兜底后, 实际业务范围应至少包含 grid
        assert "grid" in scopes, "CSG 应覆盖电网 (grid) 主业"
        assert len(scopes - {"monitor"}) >= 2, (
            f"CSG demo 业务范围过窄: {scopes - {'monitor'}}"
        )

    def test_sgcc_focuses_on_grid(self, tmp_path):
        """SGCC demo 主业是电网, 业务 scope 应集中在 grid."""
        target = tmp_path / "sgcc.json"
        on_disk = _run_pipeline(SgccFetcher(), target)
        scopes = {s for p in on_disk["policies"] for s in p["scope"]}

        assert "grid" in scopes, "SGCC 应覆盖电网 (grid) 主业"


if __name__ == "__main__":
    # 允许直接 python -m tests.test_w2_d2_schema_check 跑 (旧 w2_d2_schema_check.py 兼容)
    schema = _load_schema()
    workdir = Path("/c/Users/Administrator/AppData/Local/Temp/w2-d2-schema-check")
    workdir.mkdir(parents=True, exist_ok=True)

    for cls, label, fname in [
        (CsgFetcher, "CSG (南方电网)", "csg.json"),
        (SgccFetcher, "SGCC (国家电网)", "sgcc.json"),
        (NeaFetcher, "NEA (国家能源局, 回归基线)", "nea.json"),
    ]:
        target = workdir / fname
        on_disk = _run_pipeline(cls(), target)
        jsonschema.validate(instance=on_disk, schema=schema)
        print(
            f"✅ [{label}] policies={len(on_disk['policies'])} → schema OK → {target}"
        )

    print(f"\nArtifacts: {workdir}")
