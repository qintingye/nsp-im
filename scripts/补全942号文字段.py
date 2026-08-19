#!/usr/bin/env python3
"""补全 NSP-IM policies.json 中 942 号文字段"""
import json
import sys
from pathlib import Path

POLICY_942 = {
    "doc_number": "发改能源〔2026〕942号",
    "priority": 1,
    "scope": ["grid", "compute", "telecom", "water", "pipe", "logi", "monitor"],
    "carrier_relation": "电网↔算力/通信/水/管/物流/监测（六网枢纽）",
    "summary": (
        "十五五新型电力系统建设纲领性文件。2030年非化石能源发电量占比 50%"
        "（2025年 42.3%）；总装机 54 亿 kW（38.9→54）；"
        "新型储能 3 亿 kW（1.36→3，+121%）；"
        "虚拟电厂 5000 万 kW（1685→5000，+197%）；"
        "车网互动 5000 万 kW（+400%）；充电桩 4000 万（+99%）；"
        "西电东送 >4.2 亿 kW；非化石装机占比 65%。"
        "唯一约束性指标'电力供应充裕度 >1.1'。"
        "第十一章专章讲'促进电力与算力协同发展'——算电协同获国家级背书。"
    ),
    "key_points": [
        "非化石发电量 50%",
        "新型储能 3 亿 kW",
        "VPP 5000 万 kW",
        "车网互动 5000 万 kW",
        "充电桩 4000 万",
        "西电东送 >4.2 亿 kW",
        "算电协同专章",
        "南网14511体系对位",
    ],
    "tags": [
        "新型电力系统", "十五五", "算电协同", "新型储能",
        "虚拟电厂", "车网互动", "南网14511", "942号文",
    ],
    "publish_date": "2026-07-21",
    "captured_at": "2026-08-19T12:00:00Z",
    "captured_by": "manual-learning-update-v1",
    "source_url_interpretation": "https://mp.weixin.qq.com/s/2TJVJOK3xv28XtqBhjZvkg",
    "interpretation_source": "新华国研经济学研究院 · 宏观经济研究部 · 2026-08-19",
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
    n_updated = 0
    for pp in d["policies"]:
        title = (pp.get("title") or "")
        if "新型电力系统建设" in title and "942" in title:
            for k, v in POLICY_942.items():
                pp[k] = v
            n_updated += 1
    if n_updated > 0:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"[ok] {fpath} -> updated {n_updated} policy")
    else:
        print(f"[skip] {fpath} -> no 942 found")

print("DONE")