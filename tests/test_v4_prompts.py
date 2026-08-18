"""
测试 v4 prompt 升级
基于 CERS DCICB 演讲核心论点
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from prompts_v4 import detect_support_direction, get_carrier_relation, V4_SUPPORT_KEYWORDS


class TestDetectDirection:
    def test_算力_绿电_方向1(self):
        assert detect_support_direction("阳江海底算电协同项目", "1.15GW") == 1

    def test_通信_稳定供电_方向2(self):
        assert detect_support_direction("南方电网 5G 专网", "调度自动化") == 2

    def test_物流_能源_方向3(self):
        assert detect_support_direction("南沙港岸电", "重卡 V2G") == 3

    def test_基建_电力兜底_方向4(self):
        assert detect_support_direction("雄安容东 GIL 入廊", "高压电缆入廊") == 4

    def test_fallback_电力_归方向4(self):
        assert detect_support_direction("《关于加强电网调峰储能的通知》", "") == 4

    def test_fallback_能源_归方向4(self):
        assert detect_support_direction("《国家能源发展规划》", "") == 4

    def test_未识别_返回0(self):
        assert detect_support_direction("《国务院办公厅关于全面推进乡村振兴的意见》", "") == 0


class TestCarrierRelation:
    def test_方向1_算力绿电(self):
        assert get_carrier_relation(1) == "算力→绿电"

    def test_方向2_通信稳定供电(self):
        assert get_carrier_relation(2) == "通信→稳定供电"

    def test_方向3_物流能源保障(self):
        assert get_carrier_relation(3) == "物流→能源保障"

    def test_方向4_基建电力兜底(self):
        assert get_carrier_relation(4) == "基建→电力兜底"

    def test_方向0_未识别(self):
        assert get_carrier_relation(0) == "未识别"


class TestV4Keywords:
    def test_方向1_关键词数(self):
        assert len(V4_SUPPORT_KEYWORDS[1]["keywords"]) >= 10

    def test_方向2_关键词数(self):
        assert len(V4_SUPPORT_KEYWORDS[2]["keywords"]) >= 10

    def test_方向3_关键词数(self):
        assert len(V4_SUPPORT_KEYWORDS[3]["keywords"]) >= 10

    def test_方向4_关键词数(self):
        assert len(V4_SUPPORT_KEYWORDS[4]["keywords"]) >= 10

    def test_4方向都存在(self):
        assert set(V4_SUPPORT_KEYWORDS.keys()) == {1, 2, 3, 4}


class TestV4DataUpgrade:
    """验证 policies.json 已升级"""

    @staticmethod
    def _load():
        policy_file = Path(__file__).parent.parent / "data" / "policies.json"
        return json.loads(policy_file.read_text(encoding="utf-8"))

    def test_数据_已包含v4字段(self):
        d = self._load()
        assert "v4_source" in d, "应包含 v4_source 标记"
        assert d["v4_source"] == "CERS DCICB 演讲第(二)节第2张"

    def test_61条都升级(self):
        d = self._load()
        for p in d["policies"]:
            assert "support_direction" in p, f"{p.get('id')} 缺 support_direction"
            assert "carrier_relation" in p, f"{p.get('id')} 缺 carrier_relation"
            assert "v4_cers_dccib" in p, f"{p.get('id')} 缺 v4_cers_dccib"

    def test_4方向分布合理(self):
        d = self._load()
        from collections import Counter
        c = Counter(p["support_direction"] for p in d["policies"])
        # 4 方向都有数据
        assert c[1] > 0, "方向1 算力绿电 应有数据"
        assert c[4] > 0, "方向4 基建电力兜底 应有数据"
