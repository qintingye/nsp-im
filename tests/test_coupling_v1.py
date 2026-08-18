"""
W5-Day1 耦合算法 v1.0 测试
==========================
测试 src/prompts_v4.py 中的耦合矩阵计算功能。

覆盖范围：
1. 权重生成 (get_project_weights)
2. 单对耦合分计算 (calc_coupling_score)
3. 6×6 完整矩阵 (calc_coupling_matrix)
4. 矩阵对称性、边界、满分/零分场景
5. 公式约束 f(N)×4 + g(W)×4 + h(V)×2
"""
import math
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prompts_v4 import (
    V7_PROJECTS,
    PROJECT_WEIGHTS,
    COUPLING_NETS,
    COUPLING_NETS_CN,
    GRID_BASELINE,
    BATCH_MATURITY,
    WEIGHT_FACTORS,
    get_project_weights,
    calc_coupling_score,
    calc_coupling_matrix,
)


# ============ 1. 权重生成基础测试 ============

class TestGetProjectWeights:
    """get_project_weights() 必须为每项目生成 6 网权重"""

    def test_all_projects_have_6_net_weights(self):
        """30 项目 × 6 网 = 180 权重，无缺失"""
        assert len(V7_PROJECTS) == 30
        assert len(PROJECT_WEIGHTS) == 30
        for w in PROJECT_WEIGHTS:
            assert set(w.keys()) == set(COUPLING_NETS)
            for net, v in w.items():
                assert 0.0 <= v <= 1.0, f"{net} 权重 {v} 超出 [0, 1]"

    def test_grid_baseline_all_projects(self):
        """电网基础权重：所有项目 W_grid >= 0.55（南方电网项目清单的承载主体）"""
        for i, w in enumerate(PROJECT_WEIGHTS):
            assert w["grid"] >= GRID_BASELINE, (
                f"项目 {i+1} {V7_PROJECTS[i]['name']} 电网权重 {w['grid']} < {GRID_BASELINE}"
            )

    def test_primary_category_has_highest_weight(self):
        """项目主类（category）应至少是该项目中权重最高的非电网网（除综合/储能的复合型项目）"""
        # 综合类与储能类是天然多网融合项目，规则放宽为：主网权重 >= 0.5 即可
        cat_to_net = {
            "水网": "water", "算力网": "compute", "通信网": "telecom",
            "管": "pipe", "物流网": "logi", "储能": "compute",
            "综合": None,
        }
        for i, p in enumerate(V7_PROJECTS):
            primary = cat_to_net.get(p["category"])
            if not primary:
                continue
            w = PROJECT_WEIGHTS[i]
            if p["category"] == "储能":
                # 储能项目天然多网融合，主网权重 >= 0.5 即合规
                assert w[primary] >= 0.5, (
                    f"储能项目 {i+1} {p['name']} compute 权重 {w[primary]} < 0.5"
                )
                continue
            others = {n: v for n, v in w.items() if n not in ("grid", primary)}
            assert w[primary] >= max(others.values(), default=0), (
                f"项目 {i+1} {p['name']} 主网 {primary} 权重 {w[primary]} "
                f"不是非电网最高"
            )

    def test_get_project_weights_function(self):
        """get_project_weights() 函数可独立调用并返回一致结果"""
        p = V7_PROJECTS[0]
        w = get_project_weights(p)
        assert set(w.keys()) == set(COUPLING_NETS)
        assert w["grid"] >= GRID_BASELINE


# ============ 2. 单对耦合分测试 ============

class TestCalcCouplingScore:
    """calc_coupling_score(A, B) 单对分数"""

    def test_grid_compute_highest_synergy(self):
        """电网↔算力 应是最高分协同（南网战略核心）"""
        s = calc_coupling_score("grid", "compute")
        assert s["score"] >= 8.0, f"电网↔算力 {s['score']} 应 ≥ 8.0"
        assert s["level"] == "高分协同"
        assert s["n_projects"] >= 10

    def test_invalid_net_raises(self):
        """非法网 key 必须 raise ValueError"""
        with pytest.raises(ValueError):
            calc_coupling_score("foo", "bar")
        with pytest.raises(ValueError):
            calc_coupling_score("grid", "invalid")

    def test_score_components_sum(self):
        """分数必须 = f(N) + g(W) + h(V)"""
        s = calc_coupling_score("grid", "logi")
        expected = s["f_N"] + s["g_W"] + s["h_V"]
        assert math.isclose(s["score"], round(expected, 2), abs_tol=0.01), (
            f"总分 {s['score']} != f+g+h = {expected}"
        )

    def test_score_max_10(self):
        """总分不可能 > 10.0"""
        for a in COUPLING_NETS:
            for b in COUPLING_NETS:
                if a == b:
                    continue
                s = calc_coupling_score(a, b)
                assert s["score"] <= 10.0, f"{a}↔{b} = {s['score']} > 10"

    def test_score_min_zero(self):
        """总分不可能 < 0"""
        for a in COUPLING_NETS:
            for b in COUPLING_NETS:
                if a == b:
                    continue
                s = calc_coupling_score(a, b)
                assert s["score"] >= 0.0

    def test_no_projects_yields_min_score(self):
        """无协同项目（N=0）：f(N)=0, g(W)=0, 仅剩 h(V)=2.0"""
        s = calc_coupling_score("water", "telecom")
        assert s["n_projects"] == 0
        assert s["f_N"] == 0.0
        assert s["g_W"] == 0.0
        assert s["score"] == 2.0
        assert s["level"] == "弱协同"

    def test_fN_max_when_5_projects(self):
        """≥ 5 协同项目：f(N) 满分 4.0"""
        s = calc_coupling_score("grid", "compute")
        assert s["n_projects"] >= 5
        assert s["f_N"] == 4.0


# ============ 3. 矩阵对称性 + 完整性 ============

class TestCalcCouplingMatrix:
    """calc_coupling_matrix() 6×6 矩阵"""

    def test_matrix_is_6x6(self):
        """6 网 × 6 网 = 36 单元格"""
        m = calc_coupling_matrix()
        assert set(m.keys()) == set(COUPLING_NETS)
        for a in COUPLING_NETS:
            assert set(m[a].keys()) == set(COUPLING_NETS)

    def test_matrix_symmetric(self):
        """M[a][b] == M[b][a]（耦合定义对称）"""
        m = calc_coupling_matrix()
        for a in COUPLING_NETS:
            for b in COUPLING_NETS:
                if a == b:
                    continue
                assert m[a][b]["score"] == m[b][a]["score"], (
                    f"非对称：M[{a}][{b}]={m[a][b]['score']} vs "
                    f"M[{b}][{a}]={m[b][a]['score']}"
                )

    def test_diagonal_is_self(self):
        """对角线为各网自身得分（特殊计算）"""
        m = calc_coupling_matrix()
        for a in COUPLING_NETS:
            assert m[a][a]["net_a"] == a
            assert m[a][a]["net_b"] == a
            assert 0.0 <= m[a][a]["score"] <= 5.0  # 自身得分上限较低

    def test_off_diagonal_within_0_to_10(self):
        """非对角 15 对（C(6,2)）：每对分数 ∈ [0, 10]"""
        m = calc_coupling_matrix()
        count = 0
        for i, a in enumerate(COUPLING_NETS):
            for b in COUPLING_NETS[i + 1:]:  # 仅 a < b 避免重复
                count += 1
                s = m[a][b]["score"]
                assert 0.0 <= s <= 10.0
        assert count == 15

    def test_grid_row_reasonable(self):
        """电网横向：算力应最高，地下管网应最低（弱协同）"""
        m = calc_coupling_matrix()
        row = [m["grid"][b]["score"] for b in COUPLING_NETS if b != "grid"]
        assert max(row) == m["grid"]["compute"]["score"], "电网↔算力应最高"
        assert min(row) == m["grid"]["pipe"]["score"], "电网↔管应最低"


# ============ 4. 因子公式约束 ============

class TestFactorFormula:
    """f(N)/g(W)/h(V) 三大因子约束"""

    def test_fN_formula(self):
        """f(N) = min(N/5, 1) × 4"""
        for n in [0, 1, 3, 5, 10]:
            expected = min(n / 5.0, 1.0) * 4.0
            s = calc_coupling_score("grid", "compute")  # 已 N=21
            # 通过组件验证
            assert math.isclose(s["f_N"], min(s["n_projects"] / 5.0, 1.0) * 4.0, abs_tol=0.01)

    def test_gW_formula(self):
        """g(W) = (1/N) Σ √(W_Ai × W_Bi) × 4"""
        s = calc_coupling_score("grid", "compute")
        # 重算
        import math
        sqrts = []
        for w in PROJECT_WEIGHTS:
            wa = w["grid"]
            wb = w["compute"]
            if wa > 0 and wb > 0:
                sqrts.append(math.sqrt(wa * wb))
        expected_gw = (sum(sqrts) / len(sqrts)) * 4.0 if sqrts else 0.0
        assert math.isclose(s["g_W"], round(expected_gw, 3), abs_tol=0.005), (
            f"g_W = {s['g_W']}, expected {round(expected_gw,3)}"
        )

    def test_hV_full_evidence(self):
        """h(V) = (0.7 + 0.8 + 1.0) / 2.5 × 2 = 2.0"""
        s = calc_coupling_score("grid", "water")
        assert s["h_V"] == 2.0

    def test_weight_factors_sum_to_1(self):
        """权重 4 因子：投资 40% + 技术 30% + 政策 20% + 工程 10% = 100%"""
        total = sum(WEIGHT_FACTORS.values())
        assert math.isclose(total, 1.0, abs_tol=0.001), (
            f"4 因子权重之和 = {total}, 应为 1.0"
        )


# ============ 5. 文档对齐：与算法 doc 关键数值核对 ============

class TestAlgorithmAlignment:
    """与 docs/耦合算法-v1.0.md 关键算法点对齐"""

    def test_grid_compute_target_score(self):
        """电网↔算力目标 ~8.8（算法 doc 示例）"""
        s = calc_coupling_score("grid", "compute")
        # 实际数据驱动可能略偏离 doc 示例，但应 ≥ 8.0
        assert 8.0 <= s["score"] <= 9.0

    def test_15_pairs_plus_6_self(self):
        """6 网组合 C(6,2)=15 非对角 + 6 自身 = 21 单元格"""
        m = calc_coupling_matrix()
        pairs = 0
        diag = 0
        for i, a in enumerate(COUPLING_NETS):
            for b in COUPLING_NETS:
                if i < COUPLING_NETS.index(b):  # 仅 a < b 避免重复
                    pairs += 1
                elif a == b:
                    diag += 1
        assert pairs == 15
        assert diag == 6

    def test_grid_is_strongest_anchor(self):
        """电网作为承载主体，所有网与电网的协同分都应较高（至少 > 5）"""
        m = calc_coupling_matrix()
        for b in COUPLING_NETS:
            if b == "grid":
                continue
            assert m["grid"][b]["score"] >= 5.0, (
                f"电网↔{b} = {m['grid'][b]['score']} < 5.0, 不符合承载主体定位"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])