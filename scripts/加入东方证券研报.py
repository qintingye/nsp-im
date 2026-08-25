#!/usr/bin/env python3
"""在 NSP-IM policies.json 中加入东方证券六张网研报条目"""
import json
from pathlib import Path

NEW_POLICY = {
    "id": "P-DFZQ-20260816-0001",
    "title": "东方证券《\"六张网\"追踪：高附加值环节更为受益》",
    "department": "东方证券研究所",
    "doc_number": "东方证券研报",
    "publish_date": "2026-08-16",
    "effective_date": "2026-08-16",
    "category": "research",  # 卖方研究（区别于 policy）
    "scope": ["grid", "compute", "telecom", "water", "pipe", "logi", "monitor"],
    "priority": 2,
    "summary": (
        "六张网投资主线 H2 展望：电网确定性最强（国网 H1 固投 3100 亿/同比+12.6%，"
        "H2 月均需从 517 亿升至 800 亿+）；算力网高增（智能算力 2185 EFLOPS/同比+177%）"
        "但发改委警示\"不能一哄而上\"，警惕地方政府非理性数据中心建设；"
        "地下管网\"量减但资金翻倍\"（100 万→77 万公里、2.4 万→5 万亿元），"
        "传统管材未必明显，智慧管网/综合管廊是高附加值板块；"
        "水网年化约 1% 低增速，看 REITs+水价改革；通信网总量下行但 5G-A/万兆光网细分有机会；"
        "物流网多式联运+冷链确定但分散；仓储物流是今年专项债累计同比始终为正的少数类别。"
    ),
    "key_points": [
        "国网 H1 固投 3100 亿/+12.6%",
        "H2 月均需 517→800 亿+",
        "智能算力 2185 EFLOPS/+177%",
        "算力网\"不能一哄而上\"",
        "地下管网 77 万公里/5 万亿",
        "智慧管网/综合管廊高附加值",
        "水网年化 1% + REITs",
        "5G-A/万兆光网细分机会",
        "仓储物流专项债正增长",
    ],
    "source_url": "https://www.dfzq.com.cn/research/report/liuzhangwang-tracking-20260816",
    "captured_at": "2026-08-20T09:00:00Z",
    "captured_by": "manual-learning-update-v2",
    "tags": [
        "东方证券", "卖方研究", "六张网", "高附加值",
        "国网投资", "算力网政策风险", "智慧管网", "517→800亿",
    ],
    "review_status": "pending",
    "support_direction": 0,
    "carrier_relation": "六网全景分析",
    "v4_cers_dccib": True,
    "v7_cers_dccib": True,
    "v8_cers_dccib": True,
    "industry_chain": "卖方研究 · 宏观经济",
    "investment_period": "十五五全周期",
    # 研报专有字段
    "report_type": "卖方研究",
    "report_series": "通往再平衡之路之十",
    "analysts": ["陈至奕", "黄汝南", "孙金霞", "孙国翔", "刘姜枫", "邵睿思"],
    "key_data": {
        "国网H1固投_亿元": 3100,
        "国网H1同比": 12.6,
        "国网H2月均目标_亿元": 800,
        "国网H1月均_亿元": 517,
        "国网十五五目标_万亿": 4,
        "智能算力_EFLOPS": 2185,
        "算力同比": 177,
        "地下管网十四五_万公里": 100,
        "地下管网十五五目标_万公里": 77,
        "地下管网十四五投资_万亿": 2.4,
        "地下管网十五五目标投资_万亿": 5,
        "水网年化增速": "约1%",
        "水网H1投资_亿元": 5151,
        "水网H1同比": -3.3,
    },
    "key_view": "高附加值环节更为受益",
}

FILES = [
    "D:/hermes-dev-team/nsp-im/data/policies.json",
    "D:/hermes-dev-team/nsp-im-v1/data/policies.json",
    "D:/hermes-dev-team/nsp-im/deploy-pkg/liuwang-jiankong/data/policies.json",
    "D:/hermes-dev-team/nsp-im/docs/preview/data/policies.json",
    "D:/hermes-dev-team/nsp-im-v1/docs/preview/data/policies.json",
]

for fpath in FILES:
    p = Path(fpath)
    if not p.exists():
        print(f"[skip] not found: {fpath}")
        continue
    with open(p, encoding="utf-8") as f:
        d = json.load(f)

    # 检查是否已存在
    if any(pp.get("id") == NEW_POLICY["id"] for pp in d["policies"]):
        print(f"[skip] {fpath} -> already exists")
        continue

    d["policies"].append(NEW_POLICY)
    # 更新 generated_at 和 count
    d["generated_at"] = "2026-08-20T09:00:00Z"
    d["count"] = len(d["policies"])

    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"[ok] {fpath} -> added ({len(d['policies'])} policies)")

print("DONE")