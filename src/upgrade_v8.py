"""W2.5 → v8 升级：为 61 条 policies 添加产业链与投资节奏字段。"""
import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from prompts_v4 import detect_industry_chain, detect_investment_year

POLICY_FILE = Path(__file__).resolve().parent.parent / "data" / "policies.json"


def main():
    data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    policies = data["policies"]
    reevaluated = 0
    for policy in policies:
        text_title = policy.get("title", "")
        text_summary = policy.get("summary", "")
        chain = detect_industry_chain(text_title, text_summary)
        period = detect_investment_year(text_title, text_summary)
        if policy.get("industry_chain") != chain or policy.get("investment_period") != period:
            reevaluated += 1
        policy["industry_chain"] = chain
        policy["investment_period"] = period
        policy["v8_cers_dccib"] = True

    data["v8_upgraded_at"] = "2026-08-18T12:00:00Z"
    data["v8_source"] = "CERS DCICB 演讲第（三）张：4大核心受益产业链；十五五期间26.9万亿元"
    data["v8_chapter"] = "4产业链 + 26.9万亿元投资规模 + 三阶段节奏"
    data["v8_cers_dccib"] = True
    data["v8_investment_scale"] = {
        "total": "26.9万亿元",
        "annual": "5.4万亿元",
        "2026": ">7万亿元",
        "period": "十五五期间",
    }

    temp_file = POLICY_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_file.replace(POLICY_FILE)

    chain_count = Counter(p["industry_chain"] for p in policies)
    period_count = Counter(p["investment_period"] for p in policies)
    print("✅ v8 升级完成")
    print(f"   - 升级条数: {len(policies)}")
    print(f"   - 重新评估: {reevaluated}")
    print(f"   - 产业链分布: {dict(chain_count)}")
    print(f"   - 节奏分布: {dict(period_count)}")
    return len(policies)


if __name__ == "__main__":
    main()
