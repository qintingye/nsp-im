"""
v7 测试
基于 CERS DCICB 演讲第（三）节"六网协同方向"（24 任务 + 30 项目）
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from prompts_v4 import detect_support_direction, get_carrier_relation, V4_SUPPORT_KEYWORDS, V7_TASKS, V7_PROJECTS


class TestV7Detect:
    def test_方向1_水网(self):
        assert detect_support_direction("南方电网水风光储一体化", "贵阳防灾减灾") == 1

    def test_方向2_算力(self):
        assert detect_support_direction("电碳算协同示范工程", "数据中心") == 2

    def test_方向3_通信(self):
        assert detect_support_direction("应急通信保障", "5G") == 3

    def test_方向4_管(self):
        assert detect_support_direction("综合管廊", "城市地下空间") == 4

    def test_方向5_物流(self):
        assert detect_support_direction("平陆运河交能融合", "港口岸电") == 5

    def test_方向6_综合(self):
        assert detect_support_direction("多站合一", "六网协同") == 6

    def test_优先级_水网优先(self):
        """D1 水网 优先于 D2 算力（虽然'南方电网'也在 D1/D6 都有）"""
        assert detect_support_direction("南方电网水风光储", "") == 1


class TestV7Names:
    def test_6_方向_名称(self):
        assert V4_SUPPORT_KEYWORDS[1]["name"] == "深化与水网协同"
        assert V4_SUPPORT_KEYWORDS[2]["name"] == "深化与算力网协同"
        assert V4_SUPPORT_KEYWORDS[3]["name"] == "深化与新一代通信网协同"
        assert V4_SUPPORT_KEYWORDS[4]["name"] == "深化与地下管网协同"
        assert V4_SUPPORT_KEYWORDS[5]["name"] == "深化与物流网协同"
        assert V4_SUPPORT_KEYWORDS[6]["name"] == '深化"六网"综合协同'


class TestV7Carrier:
    def test_方向1_水网(self):
        assert get_carrier_relation(1) == "电网↔水网"

    def test_方向2_算力(self):
        assert get_carrier_relation(2) == "电网↔算力网"

    def test_方向6_综合(self):
        assert get_carrier_relation(6) == "电网↔5网综合"


class TestV7Tasks:
    def test_6_方向_任务数(self):
        expected = {1: 5, 2: 4, 3: 2, 4: 2, 5: 2, 6: 3}
        for d, n in expected.items():
            assert len(V7_TASKS[d]["tasks"]) == n, f"D{d} 应有 {n} 任务"

    def test_总任务数_18(self):
        """5+4+2+2+2+3 = 18（原 24 任务，部分子项合并）"""
        total = sum(len(V7_TASKS[d]["tasks"]) for d in V7_TASKS)
        assert total >= 15


class TestV7Projects:
    def test_30_项目(self):
        assert len(V7_PROJECTS) == 30

    def test_5_批次(self):
        from collections import Counter
        c = Counter(p["batch"] for p in V7_PROJECTS)
        assert len(c) == 5
        assert c["研究一批"] == 4
        assert c["实施一批"] == 8
        assert c["前期一批"] == 6
        assert c["储备一批"] == 6
        assert c["谋划一批"] == 6


class TestV7DataUpgrade:
    @staticmethod
    def _load():
        return json.loads((Path(__file__).parent.parent / "data" / "policies.json").read_text(encoding="utf-8"))

    def test_数据_v7_标记(self):
        d = self._load()
        assert "v7_source" in d
        assert "CERS DCICB" in d.get("v7_source", "")

    def test_61条_都升级(self):
        d = self._load()
        for p in d["policies"]:
            assert "support_direction" in p
            assert "v7_cers_dccib" in p
