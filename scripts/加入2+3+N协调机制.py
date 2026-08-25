#!/usr/bin/env python3
"""
在 NSP-IM policies.json 中新增"2+3+N 协调机制"专项条目
- 含老板亲笔公文版5 大优势解析
- 关联 942 号文 / 999 号文
- priority=1 (核心政策)
"""
import json
import sys
from pathlib import Path

NEW_POLICY = {
    "id": "P-NDRC-20260820-0007",
    "title": "NDRC 2+3+N 协调机制（新型电网+算力网+通信网跨主体统筹调度）",
    "department": "NDRC",
    "doc_number": "（首次披露于8-19 NDRC发布会；正式发文待跟踪）",
    "publish_date": "2026-08-19",
    "effective_date": None,
    "category": "policy",
    "scope": ["grid", "compute", "telecom", "monitor"],
    "priority": 1,
    "summary": "2+3+N 是新型电网、算力网、新一代通信网三张新网的跨主体统筹调度机制，破解过去分头规划、各自建设、行业壁垒等突出问题。主要优势5个方面：破除行业壁垒、避免重复建设、加快项目落地、优化资源匹配、完善市场化生态。首次披露于 2026-08-19 NDRC 主任郑栅洁民营企业座谈会。",
    "key_points": [
        "2+3+N=国网+南网+三大运营商+N家算力企业",
        "破除行业壁垒：算电协同、算网协同、同步预审",
        "避免重复建设：杆塔/管廊/路由/土地共建共享",
        "加快项目落地：发改委牵头+多部委协同+联动会商",
        "资源优化匹配：算力向新能源富集区布局+绿电绿算融合",
        "市场化生态：国有底座（2+3）+市场化运营（N）",
        "首次披露：2026-08-19 NDRC 主任郑栅洁民营企业座谈会",
        "跟踪信号：三部委联合发文 + 主体名单公示 + 示范项目开工"
    ],
    "source_url": "https://www.ndrc.gov.cn/xwdt/xwfb/202608/t20260819_1407047.html",
    "captured_at": "2026-08-21T15:30:00Z",
    "captured_by": "manual-learning-update-v2",
    "tags": ["2+3+N", "协调机制", "算电协同", "六网融合", "新型电网", "算力网", "通信网", "942号文", "999号文", "郑栅洁", "NDRC", "公文版", "汇报材料"],
    "review_status": "pending",
    "support_direction": 1,  # 01 电网→算力网
    "carrier_relation": "新型电网→算力网/通信网（跨主体协调）",
    "v4_cers_dccib": True,
    "v7_cers_dccib": True,
    "v8_cers_dccib": True,
    "interpretation_source": "老板亲笔公文版解析（2026-08-21 整理）",
    "official_document_url": None,
    "backup_sources": [
        "https://www.nbd.com.cn/articles/2026-08-21/...",
        "https://www.stcn.com/articles/...",
        "https://www.yicai.com/articles/...",
        "https://www.ndrc.gov.cn/xwdt/xwfb/202608/t20260819_1407047.html"
    ],
    "related_policies": ["发改能源〔2026〕942号", "发改能源〔2026〕999号"],
    "five_advantages": {
        "1_破除行业壁垒": "算电协同、算网协同、同步规划/预审/开工",
        "2_避免重复建设": "杆塔/管廊/路由/土地共建共享，降低基建成本",
        "3_加快项目落地": "发改委牵头+多部委协同+联动会商，压缩前期周期",
        "4_优化资源匹配": "算力向新能源富集区布局+绿电绿算融合",
        "5_市场化生态": "国有底座(2+3)+市场化运营(N)，新业态培育"
    },
    "tracking_signals": [
        "NDRC+NEA+MIIT 联合发文",
        "三大运营商算电协同战略公告",
        "国网/南网算电协同示范项目招标",
        "市场化算力企业(N)首批名单披露",
        "示范项目数据指标(绿电直供/跨域时延/共建共享率)"
    ]
}

def main():
    policy_files = [
        'D:/hermes-dev-team/nsp-im/data/policies.json',
        'D:/hermes-dev-team/nsp-im-v1/data/policies.json',
        'D:/hermes-dev-team/nsp-im/deploy-pkg/liuwang-jiankong/data/policies.json',
        'D:/hermes-dev-team/nsp-im/docs/preview/data/policies.json',
        'D:/hermes-dev-team/nsp-im-v1/docs/preview/data/policies.json',
    ]
    for pf in policy_files:
        if not Path(pf).exists():
            print(f"[skip] {pf}")
            continue
        with open(pf, encoding='utf-8') as f:
            d = json.load(f)
        # 检查是否已存在
        exists = False
        for p in d['policies']:
            if p.get('id') == NEW_POLICY['id']:
                exists = True
                break
        if exists:
            print(f"[skip-exists] {pf}")
            continue
        d['policies'].insert(0, NEW_POLICY)  # 头部插入（高优先级）
        d['generated_at'] = '2026-08-21T15:30:00Z'
        with open(pf, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"[ok] {pf}  ({len(d['policies'])} policies)")

if __name__ == '__main__':
    main()