"""
W2.5 → v7 · 升级：现有 61 条 policies 添加 support_direction 字段
基于 CERS DCICB 演讲《发展机遇》板块（4 方向协同融合版）
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from prompts_v4 import detect_support_direction, get_carrier_relation

POLICY_FILE = Path("data/policies.json")

def main():
    data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    policies = data["policies"]
    
    upgraded = 0
    reevaluated = 0
    for p in policies:
        title = p.get("title", "")
        summary = p.get("summary", "")
        direction = detect_support_direction(title, summary)
        if direction == 0:
            direction = 0
        new_relation = get_carrier_relation(direction) if direction else "未识别"
        # 强制重评（即使已有 direction）
        if p.get("support_direction") != direction or p.get("carrier_relation") != new_relation:
            reevaluated += 1
        p["support_direction"] = direction
        p["carrier_relation"] = new_relation
        p["v7_cers_dccib"] = True
        upgraded += 1
    
    # 统计
    from collections import Counter
    direction_count = Counter(p["support_direction"] for p in policies)
    carrier_count = Counter(p.get("carrier_relation") for p in policies)
    
    data["v7_upgraded_at"] = "2026-08-18T10:50:00Z"
    data["v7_source"] = "CERS DCICB 演讲第(二)节 发展机遇"
    data["v7_chapter"] = "机遇三 + 机遇四"
    # 保留 v4/v5 标记
    data["v4_source"] = "CERS DCICB 演讲第(二)节第2张"
    data["v5_source"] = "CERS DCICB 演讲第(二)节第2张 v5 修正"
    
    # 原子写入
    tmp = POLICY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(POLICY_FILE)
    
    print(f"✅ v7 升级完成")
    print(f"   - 升级条数: {upgraded}")
    print(f"   - 重新评估: {reevaluated}")
    print(f"   - 总条数: {len(policies)}")
    print(f"\n📊 4 方向分布（v7 协同融合版）:")
    for d in [1, 2, 3, 4, 5, 6]:
        names = ["", "电碳算协同", "数智融合", "抽蓄互补", "交能融合"]
        rels = ["", "电碳算↔电网", "数智↔电网", "抽蓄↔电网", "交能↔电网"]
        print(f"   D{d} {names[d]} ({rels[d]}): {direction_count.get(d, 0)} 条")
    if 0 in direction_count:
        print(f"   D0 未识别: {direction_count[0]} 条")
    
    return upgraded

if __name__ == "__main__":
    main()
