"""
测试 v5 prompt 升级
基于 CERS DCICB 演讲第（二）节第 2 张原文（精读后修正版）
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from prompts_v4 import detect_support_direction, get_carrier_relation, V4_SUPPORT_KEYWORDS


class TestV5Detect:
    def test_方向1_算力绿电(self):
        assert detect_support_direction("阳江海底算电协同", "AI 算力·数据中心") == 1

    def test_方向2_通信稳定供电(self):
        assert detect_support_direction("南方电网 5G-A 专网", "5G-A·不间断") == 2

    def test_方向3_城市物流能源(self):
        assert detect_support_direction("南沙港岸电", "智慧城市·电动化") == 3

    def test_方向4_水网源网荷储(self):
        assert detect_support_direction("西部绿电送东部", "源网荷储·西电东送") == 4

    def test_方向4_优先级最高(self):
        """D4（水网/能源转型）应优先于 D1（绿电）"""
        # 文本同时含"绿电"(D1) 和"源网荷储"(D4)，应优先 D4
        assert detect_support_direction("源网荷储一体化·绿电直供", "") == 4

    def test_fallback_电力(self):
        assert detect_support_direction("《关于加强电网调峰储能通知》", "") == 4


class TestV5Names:
    def test_方向1_名称(self):
        assert "算力网" in V4_SUPPORT_KEYWORDS[1]["name"]
        assert "绿色动能" in V4_SUPPORT_KEYWORDS[1]["name"]

    def test_方向2_名称(self):
        assert "通信网" in V4_SUPPORT_KEYWORDS[2]["name"]
        assert "运行保障" in V4_SUPPORT_KEYWORDS[2]["name"]

    def test_方向3_名称(self):
        assert "智慧城市" in V4_SUPPORT_KEYWORDS[3]["name"]
        assert "物流网" in V4_SUPPORT_KEYWORDS[3]["name"]

    def test_方向4_名称(self):
        assert "水网" in V4_SUPPORT_KEYWORDS[4]["name"]
        assert "能源转型" in V4_SUPPORT_KEYWORDS[4]["name"]


class TestV5Carrier:
    def test_方向1_关系(self):
        assert get_carrier_relation(1) == "算力←绿电"

    def test_方向2_关系(self):
        assert get_carrier_relation(2) == "通信←稳定供电"

    def test_方向3_关系(self):
        assert get_carrier_relation(3) == "城市/物流←能源支撑"

    def test_方向4_关系(self):
        assert get_carrier_relation(4) == "水网/能源转型←源网荷储"


class TestV5DataUpgrade:
    @staticmethod
    def _load():
        return json.loads((Path(__file__).parent.parent / "data" / "policies.json").read_text(encoding="utf-8"))

    def test_数据_v5标记(self):
        d = self._load()
        assert d.get("v5_source", "").startswith("CERS DCICB") or d.get("v4_source", "").startswith("CERS DCICB")

    def test_61条都升级(self):
        d = self._load()
        for p in d["policies"]:
            assert "support_direction" in p
            assert "carrier_relation" in p
            assert "v4_cers_dccib" in p

    def test_方向4_有数据(self):
        d = self._load()
        from collections import Counter
        c = Counter(p["support_direction"] for p in d["policies"])
        assert c[4] > 0

    def test_方向4_占比合理(self):
        """方向4 兜底应占多数"""
        d = self._load()
        total = len(d["policies"])
        d4_count = sum(1 for p in d["policies"] if p["support_direction"] == 4)
        assert d4_count / total > 0.3  # 至少 30%
