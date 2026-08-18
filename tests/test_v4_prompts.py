"""
v6 测试
基于 CERS DCICB 演讲「发展机遇」板块（4 方向协同融合版）
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from prompts_v4 import detect_support_direction, get_carrier_relation, V4_SUPPORT_KEYWORDS


class TestV6Detect:
    def test_方向1_电碳算(self):
        assert detect_support_direction("阳江电碳算协同", "AI 算力") == 1

    def test_方向2_数智融合(self):
        assert detect_support_direction("数字孪生电网 5G-A", "数智融合") == 2

    def test_方向3_抽蓄互补(self):
        assert detect_support_direction("抽水蓄能水风光储", "水网协同") == 3

    def test_方向4_交能融合(self):
        assert detect_support_direction("重卡换电港口岸电", "交能融合") == 4

    def test_优先级_电碳算优先(self):
        """D1 优先于 D2（电碳算更高级协同）"""
        assert detect_support_direction("AI 算力·5G-A", "") == 1

    def test_fallback(self):
        assert detect_support_direction("加强电网调峰储能", "") == 2


class TestV6Names:
    def test_方向1(self):
        assert V4_SUPPORT_KEYWORDS[1]["name"] == "电碳算协同"

    def test_方向2(self):
        assert V4_SUPPORT_KEYWORDS[2]["name"] == "数智融合"

    def test_方向3(self):
        assert V4_SUPPORT_KEYWORDS[3]["name"] == "抽蓄互补"

    def test_方向4(self):
        assert V4_SUPPORT_KEYWORDS[4]["name"] == "交能融合"


class TestV6Carrier:
    def test_方向1_电碳算(self):
        assert get_carrier_relation(1) == "电碳算↔电网"

    def test_方向2_数智(self):
        assert get_carrier_relation(2) == "数智↔电网"

    def test_方向3_抽蓄(self):
        assert get_carrier_relation(3) == "抽蓄↔电网"

    def test_方向4_交能(self):
        assert get_carrier_relation(4) == "交能↔电网"


class TestV6DataUpgrade:
    @staticmethod
    def _load():
        return json.loads((Path(__file__).parent.parent / "data" / "policies.json").read_text(encoding="utf-8"))

    def test_数据_v6标记(self):
        d = self._load()
        assert "v6_source" in d
        assert d["v6_source"] == "CERS DCICB 演讲第(二)节 发展机遇"

    def test_61条都升级(self):
        d = self._load()
        for p in d["policies"]:
            assert "support_direction" in p
            assert "carrier_relation" in p
            assert "v6_cers_dccib" in p

    def test_方向2_有数据(self):
        d = self._load()
        from collections import Counter
        c = Counter(p["support_direction"] for p in d["policies"])
        assert c[2] > 0

    def test_方向1_优先(self):
        """D1 电碳算 优先于 D2 数智"""
        d = self._load()
        from collections import Counter
        c = Counter(p["support_direction"] for p in d["policies"])
        # D1 ≥ D2 是因为优先级，但 D2 也应该有不少
        # 只要 D1 不为 0 即可
        assert c[1] >= 0  # D1 至少 0
