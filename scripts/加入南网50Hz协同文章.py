#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把南网50Hz 关键数据加入 NSP-IM policies.json"""
import json
from pathlib import Path

NEW_POLICY = {
    "id": "P-CSG-20260825-0001",
    "title": "南网50Hz《六网协同 当电网遇见通信网》",
    "department": "CSG",
    "doc_number": "南网官方公众号文章 2026-08-25",
    "publish_date": "2026-08-25",
    "effective_date": None,
    "category": "policy",
    "scope": ["grid", "telecom", "monitor"],
    "priority": 1,
    "summary": "南方电网首次系统披露六网协同在电网+通信网领域的真实落地数据:共享铁塔3000座/节约土地9万平米/节省建设成本3亿元;深圳虚拟电厂调节857万kWh/社会效益2.3亿元;广州棠下8站合一节地30-40%;2026年六张网投资预计超7万亿元。",
    "key_points": [
        "国家发改委测算2026年六张网投资超7万亿元",
        "共享铁塔:南网五省累计3000座/节约土地9万平米/节省3亿元",
        "深圳虚拟电厂:5G基站+三大运营商+华为六方合作/857万kWh/2.3亿元",
        "广州棠下多站合一:8站合一/700万kWh/年/节约用地30-40%",
        "南网14511+五个一批协同推进机制",
        "电鸿走出去+矿鸿+交鸿互联互通",
        "国内首套自主可控电力求解器天权系统",
        "南方电网坦白4大困境:安全隔离/技术耦合/成本分账/规划分治",
        "广州供电通信双通道协同模式",
        "深圳龙岗鸿蒙之区协同示范项目"
    ],
    "source_url": "https://mp.weixin.qq.com/s/iinv0hf2t5vnhvSCWTBDaQ",
    "captured_at": "2026-08-25T01:30:00Z",
    "captured_by": "manual-learning-article-20260825",
    "tags": ["南网50Hz", "六网协同", "电网通信网协同", "共享铁塔", "虚拟电厂", "多站合一", "电鸿", "天权求解器", "深圳虚拟电厂", "广州棠下", "7万亿投资"],
    "review_status": "pending",
    "support_direction": 2,
    "carrier_relation": "新型电网 通信网 电网通信网协同",
    "v4_cers_dccib": True,
    "v7_cers_dccib": True,
    "v8_cers_dccib": True,
    "interpretation_source": "老板转载南网官方公众号文章 2026-08-25",
    "official_document_url": None,
    "backup_sources": [
        "https://mp.weixin.qq.com/s/iinv0hf2t5vnhvSCWTBDaQ"
    ],
    "related_policies": ["发改能源2026-942号", "发改能源2026-999号"],
    "key_data": {
        "2026_total_investment": "超7万亿元",
        "shared_tower_count": "3000+座",
        "shared_tower_land_saved": "近9万平方米",
        "shared_tower_cost_saved": "超3亿元",
        "shenzhen_vpp_total_adjustment": "857万kWh",
        "shenzhen_vpp_carbon_reduction": "7168吨",
        "shenzhen_vpp_economic_benefit": "2.3亿元",
        "guangzhou_tangxia_stations": 8,
        "guangzhou_tangxia_electricity_saved": "700万kWh/年",
        "guangzhou_tangxia_land_saved": "30-40%",
        "5g_base_stations_china": "483.8万座",
        "first_shared_tower": "云南东郭二回线6号塔 2017",
        "csg_chinatower_partnership": "2018年战略合作"
    },
    "four_dilemmas": {
        "1_safe_isolation": "共享铁塔仅物理空间复用 不开展跨网数据/控制交互",
        "2_tech_coupling": "电网通信网耦合建模研究滞后 关键技术攻关中",
        "3_cost_allocation": "看得见效益 算不清账本",
        "4_planning_partition": "电网归口能源部门 通信归口工信部门 一张蓝图格局未形成"
    },
    "csg_four_new_visions": {
        "1_public_network_sensing": "5G+千兆光网电力终端规模化应用",
        "2_satellite_emergency": "无线数字集群+卫星主站+卫星备用通道",
        "3_dianhong_interconnect": "电鸿走出去+矿鸿+交鸿/深圳龙岗鸿蒙之区",
        "4_unified_market": "站址资源运营平台+电力求解器天权"
    },
    "tracking_signals": [
        "共享铁塔新增数量 季度发布",
        "深圳虚拟电厂扩容进度",
        "广州棠下模式向其他城市复制",
        "电鸿生态拓展 矿鸿/交鸿接入",
        "电力求解器天权应用落地",
        "首批发电类虚拟电厂交易额"
    ]
}

POLICY_FILES = [
    'D:/hermes-dev-team/nsp-im/data/policies.json',
    'D:/hermes-dev-team/nsp-im-v1/data/policies.json',
    'D:/hermes-dev-team/nsp-im/deploy-pkg/liuwang-jiankong/data/policies.json',
    'D:/hermes-dev-team/nsp-im/docs/preview/data/policies.json',
    'D:/hermes-dev-team/nsp-im-v1/docs/preview/data/policies.json',
]

for pf in POLICY_FILES:
    if not Path(pf).exists():
        print(f'[skip] {pf}')
        continue
    with open(pf, encoding='utf-8') as f:
        d = json.load(f)
    exists = any(p.get('id') == NEW_POLICY['id'] for p in d['policies'])
    if exists:
        print(f'[skip-exists] {pf}')
        continue
    d['policies'].insert(0, NEW_POLICY)
    d['generated_at'] = '2026-08-25T01:30:00Z'
    with open(pf, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f'[ok] {pf} ({len(d["policies"])} policies)')

print('\nNSP-IM 入库完成：南网50Hz 8-25 关键数据 + 7 万亿投资信号')