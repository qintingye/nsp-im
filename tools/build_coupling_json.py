"""W5-Day2:生成完整耦合矩阵 JSON(6×6 + 每对协同项目清单)

输入:src/prompts_v4.py 的 calc_coupling_matrix() + get_project_weights() + V7_PROJECTS
输出:docs/coupling_matrix.json + data/coupling_matrix.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"D:/hermes-dev-team/nsp-im")
sys.path.insert(0, str(ROOT / "src"))

from prompts_v4 import (  # noqa: E402
    COUPLING_NETS,
    COUPLING_NETS_CN,
    V7_PROJECTS,
    calc_coupling_matrix,
    get_project_weights,
)


def projects_for_pair(net_a: str, net_b: str):
    """返回 (a, b) 协同权重 > 0 的项目清单(自身对只要求 a 网权重 > 0)"""
    result = []
    for i, p in enumerate(V7_PROJECTS):
        w = get_project_weights(p)
        wa = w.get(net_a, 0)
        wb = w.get(net_b, 0)
        if net_a == net_b:
            if wa > 0:
                result.append({
                    "idx": i + 1,
                    "name": p["name"],
                    "batch": p["batch"],
                    "category": p["category"],
                    "weight": round(wa, 3),
                })
        else:
            if wa > 0 and wb > 0:
                result.append({
                    "idx": i + 1,
                    "name": p["name"],
                    "batch": p["batch"],
                    "category": p["category"],
                    "weight_a": round(wa, 3),
                    "weight_b": round(wb, 3),
                    "w_prod": round((wa * wb) ** 0.5, 3),
                })
    return result


def build():
    matrix = calc_coupling_matrix()
    output = {
        "version": "1.0",
        "generated_at": "2026-08-19",
        "algorithm": "f(N)×4 + g(W)×4 + h(V)×2 (满分 10)",
        "nets": list(COUPLING_NETS),
        "nets_cn": dict(COUPLING_NETS_CN),
        "total_projects": len(V7_PROJECTS),
        "matrix": matrix,
        "pairs": {},
    }

    seen = set()
    for a in COUPLING_NETS:
        for b in COUPLING_NETS:
            if a == b:
                key = f"{a}__self"
            else:
                key = "__".join(sorted([a, b]))
            if key in seen:
                continue
            seen.add(key)
            output["pairs"][key] = {
                "type": "self" if a == b else "couple",
                "net_a": a,
                "net_b": b,
                "score": matrix[a][b]["score"],
                "level": matrix[a][b]["level"],
                "n_projects": matrix[a][b]["n_projects"],
                "f_N": matrix[a][b]["f_N"],
                "g_W": matrix[a][b]["g_W"],
                "h_V": matrix[a][b]["h_V"],
                "projects": projects_for_pair(a, b),
            }

    # 双写出
    targets = [
        ROOT / "docs" / "coupling_matrix.json",
        ROOT / "data" / "coupling_matrix.json",
    ]
    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  -> {t}  ({t.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
    # 抽样校验
    with open(ROOT / "docs" / "coupling_matrix.json", encoding="utf-8") as f:
        d = json.load(f)
    print("\n抽样校验:")
    print(f"  电网↔算力网  分={d['matrix']['grid']['compute']['score']}  "
          f"项目数={d['matrix']['grid']['compute']['n_projects']}")
    print(f"  pairs 键数: {len(d['pairs'])}  "
          f"(期望 15+6=21)")
    p = d["pairs"]["compute__grid"]
    print(f"  compute__grid projects: {len(p['projects'])} 条")
    if p["projects"]:
        print(f"    例: {p['projects'][0]['name']} (w_prod={p['projects'][0]['w_prod']})")