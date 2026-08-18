"""v8 tests: CERS DCICB 第(三)张的产业链、投资规模与节奏识别。"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prompts_v4 import (
    V8_INDUSTRY_CHAINS,
    V8_INVESTMENT_SCALE,
    detect_industry_chain,
    detect_investment_year,
)


class TestV8IndustryChains:
    def test_four_core_chains_exist(self):
        assert set(V8_INDUSTRY_CHAINS) == {
            "电力与新能源",
            "算力与通信",
            "工程与机械",
            "现代物流",
        }

    def test_power_new_energy_detection(self):
        assert detect_industry_chain("新能源消纳与储能项目", "风电光伏并网") == "电力与新能源"

    def test_compute_telecom_detection(self):
        assert detect_industry_chain("数据中心算力枢纽建设", "5G 专网与绿电直供") == "算力与通信"

    def test_engineering_machinery_detection(self):
        assert detect_industry_chain("城市地下管网更新改造工程", "综合管廊施工设备") == "工程与机械"

    def test_modern_logistics_detection(self):
        assert detect_industry_chain("平陆运河水网物流融合", "港口岸电和多式联运") == "现代物流"

    def test_unknown_chain_is_none(self):
        assert detect_industry_chain("文化活动通知", "") == "未识别"

    def test_specific_phrase_wins_over_generic_keyword(self):
        assert detect_industry_chain("算力网与通信网融合", "数字底座") == "算力与通信"


class TestV8InvestmentScale:
    def test_scale_has_269_trillion(self):
        assert V8_INVESTMENT_SCALE["total"] == "26.9万亿元"

    def test_scale_has_annual_and_2026_opening(self):
        assert V8_INVESTMENT_SCALE["annual"] == "5.4万亿元"
        assert V8_INVESTMENT_SCALE["2026"] == ">7万亿元"

    def test_start_period_detection(self):
        assert detect_investment_year("2026年开局投资超7万亿元", "") == "2026起步"

    def test_mid_period_detection(self):
        assert detect_investment_year("算力网建设", "2027-2028年进入中期") == "2027-2028中期"

    def test_late_period_detection(self):
        assert detect_investment_year("2029—2030年后期项目", "") == "2029-2030后期"

    def test_mid_late_release_detection(self):
        assert detect_investment_year("城市地下管网", "中后期放量") == "中后期放量"

    def test_full_fifteenth_five_detection(self):
        assert detect_investment_year("十五五期间基础设施投资", "26.9万亿元") == "十五五全周期"

    def test_unknown_period_is_none(self):
        assert detect_investment_year("一般行业通知", "") == "未明确"


class TestV8Policies:
    @staticmethod
    def _load():
        return json.loads((Path(__file__).parent.parent / "data" / "policies.json").read_text(encoding="utf-8"))

    def test_all_61_policies_have_v8_fields(self):
        data = self._load()
        assert len(data["policies"]) == 61
        assert data["v8_cers_dccib"] is True
        assert "26.9万亿元" in data["v8_source"]
        assert all("industry_chain" in p and "investment_period" in p for p in data["policies"])

    def test_all_policy_chain_values_are_known_or_unknown(self):
        data = self._load()
        valid = set(V8_INDUSTRY_CHAINS) | {"未识别"}
        assert all(p["industry_chain"] in valid for p in data["policies"])

    def test_all_policy_period_values_are_valid(self):
        data = self._load()
        valid = {"2026起步", "2027-2028中期", "2029-2030后期", "中后期放量", "十五五全周期", "未明确"}
        assert all(p["investment_period"] in valid for p in data["policies"])

    def test_each_chain_has_policy_coverage(self):
        data = self._load()
        counts = Counter(p["industry_chain"] for p in data["policies"])
        assert all(counts[name] > 0 for name in V8_INDUSTRY_CHAINS)
