#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把今天（2026-08-25）老板转载的 4 篇公众号文章统一入库到 NSP-IM
- 人民日报: 六张网如何赋能现代化产业体系 (P-NEWS-20260825-0001)
- 南网50Hz: 六网协同 当电网遇见通信网 (P-CSG-20260825-0001)
- 北大纵横: 六网战略部署政策意图制度逻辑产业图谱 (P-INST-20260825-0001)
- 北极星电力: 电价怎么算出来 (P-MEDIA-20260825-0001)
"""
import json
from pathlib import Path

NEW_ENTRIES = [
    # 人民日报
    {
        "id": "P-NEWS-20260825-0001",
        "title": "人民日报 六张网如何赋能现代化产业体系",
        "department": "PEOPLE-DAILY",
        "doc_number": "人民日报 2026-07-26 第1版",
        "publish_date": "2026-07-26",
        "category": "research",
        "scope": ["grid", "compute", "telecom", "water", "pipe", "logi"],
        "priority": 1,
        "summary": "人民日报头版首次系统解读六张网：定位为现代化基础设施体系核心载体，是新质生产力同频共振的新型基础设施。通过山东潍柴雷沃超级工厂（500台机器人/4分钟下线）、南京江宁低空物流（7.4公里/6G无蜂窝）等案例，论证六张网赋能现代化产业体系。",
        "key_points": [
            "六张网=新水电煤（算力网+通信网已成基础设施）",
            "现代化产业体系载体=传统产业+新兴产业+未来产业+服务业+现代化基础设施体系",
            "山东潍柴超级工厂：500台机器人/5G-A/AI质检/4分钟下线",
            "南京江宁低空物流：7.4公里/6G无蜂窝/时间减半",
            "脑机接口+生物制造+核聚变=未来产业三大方向",
            "水网=生命线/城市地下管网=韧性底座（隐性守护）",
            "作者：李心萍 编辑：石石磊、阮可欣"
        ],
        "source_url": "https://mp.weixin.qq.com/s/6VdxBqbkM533sudDls64Ig",
        "captured_at": "2026-08-25T01:30:00Z",
        "captured_by": "manual-learning-article-batch-20260825",
        "tags": ["人民日报", "六张网", "新水电煤", "现代化产业体系", "党媒", "新质生产力", "央广最高背书", "李心萍"],
        "review_status": "pending",
        "support_direction": None,
        "carrier_relation": "六张网=现代化产业体系载体",
        "v4_cers_dccib": True,
        "v7_cers_dccib": True,
        "v8_cers_dccib": True,
        "interpretation_source": "人民日报头版/老板转载",
        "backup_sources": ["https://mp.weixin.qq.com/s/6VdxBqbkM533sudDls64Ig"],
        "related_policies": ["942号文", "999号文"],
        "report_type": "党媒头版/战略叙事"
    },
    # 南网50Hz (已在之前的脚本里入库)
    {
        "id": "P-CSG-20260825-0002",
        "title": "南网50Hz 六网协同 当电网遇见通信网 会碰撞出什么（补录）",
        "department": "CSG",
        "doc_number": "南网官方公众号 2026-08-25",
        "publish_date": "2026-08-25",
        "category": "research",
        "scope": ["grid", "telecom", "monitor"],
        "priority": 1,
        "summary": "南网首次披露电网+通信网协同真实落地数据：共享铁塔3000座/节地9万平米/省3亿元；深圳虚拟电厂5G基站储能857万kWh/2.3亿元；广州棠下8站合一700万kWh/年；2026年六张网投资预计超7万亿元。南网坦白4大困境：安全隔离/技术耦合/成本分账/规划分治。",
        "key_points": [
            "2026年六张网投资预计超7万亿元（国家发改委测算）",
            "共享铁塔3000座/9万平米/3亿元（南网五省累计）",
            "深圳虚拟电厂：6方合作/857万kWh/2.3亿元",
            "广州棠下多站合一：8站合一/700万kWh/年/30-40%节地",
            "南网4大图景：公网感知/空天地应急/电鸿互联/统一市场",
            "电力求解器天权：国内首套自主可控",
            "南网4大困境：安全隔离/技术耦合/成本分账/规划分治",
            "作者：谢婧繁/刘洋洋 编辑：谢婧繁/黄璐"
        ],
        "source_url": "https://mp.weixin.qq.com/s/iinv0hf2t5vnhvSCWTBDaQ",
        "captured_at": "2026-08-25T01:30:00Z",
        "captured_by": "manual-learning-article-batch-20260825",
        "tags": ["南网50Hz", "电网+通信网协同", "共享铁塔", "虚拟电厂", "8站合一", "电鸿", "天权求解器", "谢婧繁"],
        "review_status": "pending",
        "support_direction": 2,
        "carrier_relation": "新型电网 通信网 电网通信网协同",
        "v4_cers_dccib": True,
        "v7_cers_dccib": True,
        "v8_cers_dccib": True,
        "interpretation_source": "南网官方公众号/老板转载",
        "backup_sources": ["https://mp.weixin.qq.com/s/iinv0hf2t5vnhvSCWTBDaQ"],
        "related_policies": ["942号文", "999号文"]
    },
    # 北大纵横
    {
        "id": "P-INST-20260825-0001",
        "title": "北大纵横 六网战略部署的政策意图制度逻辑与产业图谱",
        "department": "INST-THINKTANK",
        "doc_number": "北大纵横宏观经济研究院 2026-08-25",
        "publish_date": "2026-08-25",
        "category": "research",
        "scope": ["grid", "compute", "telecom", "water", "pipe", "logi"],
        "priority": 1,
        "summary": "对2026年4月28日中央政治局会议的深度学术解读：六网是中央最高决策层级首次将六大基础设施作为整体性战略框架系统化部署。2026年六张网投资预期超5万亿元；国网+南网合计5万亿；南网2026年固投1800亿元；城市地下管网70万公里/5万亿元。",
        "key_points": [
            "2026年4月28日中央政治局会议首次系统部署六网",
            "2026年六张网投资超5万亿元",
            "国网+南网十五五合计5万亿元",
            "南网2026年固投1800亿元",
            "城市地下管网70万公里/5万亿元投资",
            "2026年超长期特别国债1.3万亿/两重8000亿",
            "四稳方针：稳就业/稳企业/稳市场/稳预期",
            "5G基站495.8万个/千兆端口3201万个",
            "6大产业链图谱详细分析",
            "4大制度逻辑：资金匹配/市场治理/创新驱动/风险化解",
            "3个关键变量：央地博弈/民间资本/十五五规划承接"
        ],
        "source_url": "https://mp.weixin.qq.com/s/M1FGFojKXyXNbZDXZZN79w",
        "captured_at": "2026-08-25T01:30:00Z",
        "captured_by": "manual-learning-article-batch-20260825",
        "tags": ["北大纵横", "六网", "政治局会议", "超长期特别国债", "两重建设", "宏观研究", "产业图谱"],
        "review_status": "pending",
        "support_direction": None,
        "carrier_relation": "六网战略=压舱石工程",
        "v4_cers_dccib": True,
        "v7_cers_dccib": True,
        "v8_cers_dccib": True,
        "interpretation_source": "北大纵横宏观经济研究院/老板转载",
        "backup_sources": ["https://mp.weixin.qq.com/s/M1FGFojKXyXNbZDXZZN79w"],
        "related_policies": ["942号文", "999号文"],
        "report_type": "宏观研究/深度解析"
    },
    # 北极星电力
    {
        "id": "P-MEDIA-20260825-0001",
        "title": "北极星电力 电价到底是怎么算出来的 从报价到出清的全过程",
        "department": "MEDIA-BJX",
        "doc_number": "北极星电力公众号 2026-08-25",
        "publish_date": "2026-08-25",
        "category": "research",
        "scope": ["grid"],
        "priority": 2,
        "summary": "电力现货市场微观机制：日前+日内+实时三层结构；SCUC+SCED双层优化模型；LMP节点边际电价=电能量价格+阻塞价格+网损价格。2026-01容量电价机制完善。山西日前vs实时价差-194.7至84.97元/MWh；广东-73.37至114.40元/MWh。",
        "key_points": [
            "现货市场三层：日前/日内/实时",
            "电价形成5 步：报价/曲线/交点/约束/结算",
            "SCUC安全约束机组组合+SCED安全约束经济调度",
            "LMP=电能量+阻塞+网损三部分",
            "双结算机制：日前+实时分别结算",
            "2026-01容量电价机制完善",
            "山西日前价差区间-194.7至84.97元/MWh",
            "广东日前价差区间-73.37至114.40元/MWh"
        ],
        "source_url": "https://mp.weixin.qq.com/s/doAe2QuZAz7xyf9m4SFIUg",
        "captured_at": "2026-08-25T01:30:00Z",
        "captured_by": "manual-learning-article-batch-20260825",
        "tags": ["北极星电力", "电力现货市场", "SCUC", "SCED", "LMP节点电价", "容量电价", "双结算机制"],
        "review_status": "pending",
        "support_direction": None,
        "carrier_relation": "新型电网-电价形成机制",
        "v4_cers_dccib": True,
        "v7_cers_dccib": True,
        "v8_cers_dccib": True,
        "interpretation_source": "北极星电力公众号/老板转载",
        "backup_sources": ["https://mp.weixin.qq.com/s/doAe2QuZAz7xyf9m4SFIUg"],
        "related_policies": ["容量电价机制 2026-01"],
        "report_type": "技术讲解/电力市场微观机制"
    }
]

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
    existing_ids = {p.get('id') for p in d['policies']}
    added = 0
    for entry in NEW_ENTRIES:
        if entry['id'] not in existing_ids:
            d['policies'].insert(0, entry)
            added += 1
    if added > 0:
        d['generated_at'] = '2026-08-25T01:30:00Z'
        with open(pf, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f'[ok] {pf} (+{added} new, total {len(d["policies"])})')
    else:
        print(f'[skip-no-new] {pf} ({len(d["policies"])} policies)')

print('\n入库完成：4 篇公众号文章全部进入 NSP-IM 知识库')