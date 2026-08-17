"""
W1-D1-BE · JSON Schema 自校验单测
====================================

测试目的：
  1) src/schemas/ 下 3 个 schema 文件本身能被 jsonschema.Draft7Validator 加载（schema 语法合法）
  2) 构造符合 schema 的最小数据样本能通过校验
  3) 故意违反 required/pattern/enum 的样本会被拒绝

运行：
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe tests/test_schemas.py
或：
    python tests/test_schemas.py（已激活 venv 时）
"""
import json
import sys
import unittest
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft7Validator
except ImportError:
    print("ERROR: jsonschema 未安装。请运行: pip install jsonschema", file=sys.stderr)
    raise


# ---------- 路径定位 ----------
ROOT = Path(__file__).resolve().parent.parent          # .../nsp-im
SCHEMAS_DIR = ROOT / "src" / "schemas"

POLICIES_SCHEMA_PATH    = SCHEMAS_DIR / "policies.schema.json"
INTELLIGENCE_SCHEMA_PATH = SCHEMAS_DIR / "intelligence.schema.json"
SCENES_SCHEMA_PATH      = SCHEMAS_DIR / "scenes.schema.json"


def _load_schema(path: Path) -> dict:
    """读取并解析 schema 文件。返回 dict。"""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


class TestSchemasAreValidDraft07(unittest.TestCase):
    """schema 文件自身必须能被 Draft7Validator 加载（即 schema 语法合法）。"""

    def setUp(self):
        self.policies     = _load_schema(POLICIES_SCHEMA_PATH)
        self.intelligence = _load_schema(INTELLIGENCE_SCHEMA_PATH)
        self.scenes       = _load_schema(SCENES_SCHEMA_PATH)

    def test_policies_schema_loads(self):
        Draft7Validator.check_schema(self.policies)

    def test_intelligence_schema_loads(self):
        Draft7Validator.check_schema(self.intelligence)

    def test_scenes_schema_loads(self):
        Draft7Validator.check_schema(self.scenes)

    def test_schemas_have_required_top_level_keys(self):
        """intelligence / scenes 必须含 $schema/type/properties/required 完整结构。"""
        for name, schema in (
            ("intelligence", self.intelligence),
            ("scenes",       self.scenes),
        ):
            with self.subTest(schema=name):
                for key in ("$schema", "type", "properties", "required"):
                    self.assertIn(
                        key, schema,
                        f"{name} schema 缺少顶层 {key}（W1-D1 修复目标）",
                    )
                self.assertEqual(schema["type"], "object")
                self.assertIsInstance(schema["required"], list)
                self.assertGreaterEqual(len(schema["required"]), 1)
                self.assertIsInstance(schema["properties"], dict)
                self.assertGreaterEqual(len(schema["properties"]), 1)


class TestPoliciesSchemaBehavior(unittest.TestCase):
    """针对 policies schema 的正反例测试。"""

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema(POLICIES_SCHEMA_PATH)
        cls.validator = Draft7Validator(cls.schema)

    def _minimal_policy_item(self) -> dict:
        """构造符合 policies schema 的最小合法政策条目。"""
        return {
            "id": "P-NDRC-20260818-1234",
            "title": "示例政策标题",
            "department": "国家发改委",
            "publish_date": "2026-08-18",
        }

    def test_minimal_policy_passes(self):
        """最小合法样本必须通过校验。"""
        data = {
            "version": "1.0",
            "generated_at": "2026-08-18T01:00:00Z",
            "policies": [self._minimal_policy_item()],
        }
        errors = list(self.validator.iter_errors(data))
        self.assertEqual(errors, [], f"最小样本应通过校验，但有错误: {errors}")

    def test_missing_required_field_rejected(self):
        """缺 id 必填字段必须被拒。"""
        bad_item = self._minimal_policy_item()
        del bad_item["id"]
        data = {
            "version": "1.0",
            "generated_at": "2026-08-18T01:00:00Z",
            "policies": [bad_item],
        }
        errors = list(self.validator.iter_errors(data))
        self.assertGreater(len(errors), 0, "缺 id 的样本应被拒绝")
        # 至少有一条错误指向 'id' 必填
        self.assertTrue(
            any("'id' is a required property" in e.message for e in errors),
            f"应有 'id' is required 错误，实得: {[e.message for e in errors]}",
        )

    def test_invalid_id_pattern_rejected(self):
        """id pattern 必须 8 位日期段 + 4 位序号（与 ndrc fetcher 输出对齐）。"""
        bad_item = self._minimal_policy_item()
        # 旧 schema 接受的"P-NDRC-123-4567"（无 8 位日期段）现在必须被拒
        bad_item["id"] = "P-NDRC-123-4567"
        data = {
            "version": "1.0",
            "generated_at": "2026-08-18T01:00:00Z",
            "policies": [bad_item],
        }
        errors = list(self.validator.iter_errors(data))
        self.assertGreater(len(errors), 0, "P-NDRC-123-4567 应被 pattern 拒绝")
        self.assertTrue(
            any("does not match" in e.message or "pattern" in e.message for e in errors),
            f"应有 pattern 错误，实得: {[e.message for e in errors]}",
        )

    def test_ndrc_fetcher_format_passes(self):
        """模拟 ndrc fetcher L46 实际输出格式 P-NDRC-YYYYMMDD-NNNN 必须通过。"""
        item = self._minimal_policy_item()
        item["id"] = "P-NDRC-20260818-1234"
        item["publish_date"] = "2026-08-18"
        data = {
            "version": "1.0",
            "generated_at": "2026-08-18T01:00:00Z",
            "policies": [item],
        }
        errors = list(self.validator.iter_errors(data))
        self.assertEqual(errors, [], f"ndrc fetcher 格式应通过，错误: {errors}")


class TestIntelligenceSchemaBehavior(unittest.TestCase):
    """针对 intelligence schema 的正反例测试。"""

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema(INTELLIGENCE_SCHEMA_PATH)
        cls.validator = Draft7Validator(cls.schema)

    def _minimal_intelligence(self) -> dict:
        return {
            "date": "2026-08-18",
            "generated_at": "2026-08-18T01:00:00Z",
            "summary": "今日新增 0 份政策，0 个项目更新",
            "highlights": [],
            "by_net": {
                "water": 0, "compute": 0, "telecom": 0,
                "pipe": 0, "logi": 0, "monitor": 0,
            },
            "data_freshness": {
                "last_successful_fetch": "2026-08-18T01:00:00Z",
                "failed_sources": [],
                "next_scheduled": "2026-08-19T01:00:00Z",
            },
        }

    def test_minimal_intelligence_passes(self):
        """最小情报样本必须通过。"""
        data = self._minimal_intelligence()
        errors = list(self.validator.iter_errors(data))
        self.assertEqual(errors, [], f"最小样本应通过，错误: {errors}")

    def test_missing_summary_rejected(self):
        """summary 必填，缺失必须被拒。"""
        data = self._minimal_intelligence()
        del data["summary"]
        errors = list(self.validator.iter_errors(data))
        self.assertGreater(len(errors), 0)

    def test_invalid_severity_rejected(self):
        """severity 不在 enum [high,medium,low] 必须被拒。"""
        data = self._minimal_intelligence()
        data["highlights"] = [{
            "id": "HL-2026-08-18-01",
            "category": "policy",
            "severity": "critical",   # 非法值
            "title": "示例",
            "one_liner": "一句话",
            "captured_at": "2026-08-18T01:00:00Z",
        }]
        errors = list(self.validator.iter_errors(data))
        self.assertGreater(len(errors), 0)
        # absolute_path 形如 deque(['highlights', 0, 'severity']) → 转 str 含 'severity'
        # jsonschema enum 错误消息模板是 "'X' is not one of [...]"，无 'enum' 字样
        self.assertTrue(
            any(
                "severity" in str(e.absolute_path) and "not one of" in e.message.lower()
                for e in errors
            ),
            f"应有 severity enum 错误，实得: "
            f"{[(str(e.absolute_path), e.message) for e in errors]}",
        )

    def test_by_net_missing_key_rejected(self):
        """by_net 使用 additionalProperties=false，缺 monitor 必须被拒。"""
        data = self._minimal_intelligence()
        del data["by_net"]["monitor"]
        errors = list(self.validator.iter_errors(data))
        self.assertGreater(len(errors), 0)


class TestScenesSchemaBehavior(unittest.TestCase):
    """针对 scenes schema 的正反例测试。"""

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema(SCENES_SCHEMA_PATH)
        cls.validator = Draft7Validator(cls.schema)

    def _minimal_scenes(self) -> dict:
        return {
            "version": "1.0",
            "scenes": [{
                "id": "S-C1",
                "name": "阳江海底算力",
                "net": "compute",
                "region": "广东",
                "score": 4.25,
            }],
        }

    def test_minimal_scenes_passes(self):
        data = self._minimal_scenes()
        errors = list(self.validator.iter_errors(data))
        self.assertEqual(errors, [], f"最小样本应通过，错误: {errors}")

    def test_invalid_net_rejected(self):
        """net 不在六网 enum 必须被拒。"""
        data = self._minimal_scenes()
        data["scenes"][0]["net"] = "ai"   # 非法
        errors = list(self.validator.iter_errors(data))
        self.assertGreater(len(errors), 0)

    def test_score_out_of_range_rejected(self):
        """score 范围 0-5，超出必须被拒。"""
        data = self._minimal_scenes()
        data["scenes"][0]["score"] = 7.5
        errors = list(self.validator.iter_errors(data))
        self.assertGreater(len(errors), 0)


if __name__ == "__main__":
    # -v 让每个用例都打印；CI/手动都能看清
    unittest.main(verbosity=2)