"""
NSP-IM v4 Prompt 模板
====================
基于 CERS DCICB 演讲第（二）节第 2 张："新型电网是支撑六张网体系运转的核心与基石"

【核心论点】
新型电网是核心枢纽型基础设施。所有协同案例必须能体现"新型电网=承载方"叙事。

【4 个支撑方向·必检】
1. 算力网需要绿电支撑 → 算电协同/绿电直供/PUE/阳江海底算力/韶关集群
2. 通信网需要稳定供电 → 5G 专网/变电站/F5G/广西双万兆/海南万兆自贸港
3. 产业物流需要能源保障 → 港口岸电/岸电替油/重卡 V2G/冷库蓄冷/南沙港
4. 城乡基建需要电力兜底 → GIL入廊/综合管廊/地下管网/城市生命线/雄安容东
"""

# ============ 4 方向关键词（v4 新增）============
V4_SUPPORT_KEYWORDS = {
    1: {  # 算力+绿电
        "name": "算力网需要绿电支撑",
        "carrier_relation": "算力→绿电",
        "keywords": [
            "算电协同", "绿电直供", "绿电聚合", "PUE",
            "阳江海底算力", "韶关集群", "海南算力", "东盟数据",
            "数据中心绿电", "源网荷储", "零碳园区",
        ],
    },
    2: {  # 通信+稳定供电
        "name": "通信网需要稳定供电",
        "carrier_relation": "通信→稳定供电",
        "keywords": [
            "5G 专网", "5G-A", "F5G", "万兆光网", "50G-PON",
            "变电站", "调度自动化", "通信覆盖",
            "广西双万兆", "海南万兆自贸港", "云南中老光缆",
            "通信基站", "共享铁塔", "一杆多用",
        ],
    },
    3: {  # 物流+能源保障
        "name": "产业物流需要能源保障",
        "carrier_relation": "物流→能源保障",
        "keywords": [
            "港口岸电", "岸电替油", "重卡超充", "重卡换电", "V2G",
            "冷库蓄冷", "光储充换", "充换电",
            "南沙港", "北部湾港", "洋浦港",
            "中老铁路", "平陆运河", "西部陆海新通道",
        ],
    },
    4: {  # 城乡基建+电力兜底
        "name": "城乡基建需要电力兜底",
        "carrier_relation": "基建→电力兜底",
        "keywords": [
            "GIL入廊", "高压电缆入廊", "综合管廊", "地下管网",
            "城市生命线", "城市更新", "城市基础设施",
            "雄安容东", "雄安昝西", "横琴", "前海", "南沙",
            "透明配电网", "智能巡检", "40年免维护",
        ],
    },
}

# ============ 智能识别：自动判断 case 属于哪个支撑方向 ============
def detect_support_direction(title: str, summary: str = "") -> int:
    """根据标题/摘要智能判断 4 个支撑方向之一。返回 1/2/3/4。"""
    text = (title + " " + summary).lower()
    scores = {1: 0, 2: 0, 3: 0, 4: 0}
    for direction, info in V4_SUPPORT_KEYWORDS.items():
        for kw in info["keywords"]:
            if kw.lower() in text:
                scores[direction] += 2
    # 算力优先（关键词最少）
    if scores[1] >= 2: return 1
    # 取最高分
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    # Fallback: 任何含"电力/能源/电网/南方/北/西/东/输/配"的通用政策归"基建→电力兜底"
    fallback_kws = ["电力", "能源", "电网", "南方", "输电", "配电", "输配", "新型电力", "新能源", "储能", "氢能", "充电", "电改"]
    for kw in fallback_kws:
        if kw in text:
            return 4
    return 0  # 未能识别


def get_carrier_relation(direction: int) -> str:
    if direction in V4_SUPPORT_KEYWORDS:
        return V4_SUPPORT_KEYWORDS[direction]["carrier_relation"]
    return "未识别"


# ============ V4 Prompt 模板（用于抓取 Agent）============
PROMPT_V4 = """你是 NSP-IM 政策情报官。每日从政策原文 + 行业动态中提取【六网协同案例】。

【核心论点·v4 新增】
新型电网是支撑"六张网"体系运转的核心与基石。所有协同案例必须能体现"新型电网=承载方"叙事。

【4 个支撑方向·必检】
1. 算力网需要绿电支撑（关键词：算电协同、绿电直供、PUE、阳江海底算力、韶关集群）
2. 通信网需要稳定供电（关键词：5G 专网、变电站、F5G、广西双万兆、海南万兆自贸港）
3. 产业物流需要能源保障（关键词：港口岸电、岸电替油、重卡 V2G、南沙港）
4. 城乡基建需要电力兜底（关键词：GIL入廊、综合管廊、雄安容东）

【输出模板·v4】
```json
{
  "case_id": "C-YYYY-MMDD-NNN",
  "date": "YYYY-MM-DD",
  "title": "案例标题",
  "support_direction": 1-4,
  "support_direction_name": "4 方向名称",
  "carrier_relation": "算力→绿电/通信→稳定供电/物流→能源保障/基建→电力兜底",
  "support_keywords": ["关键词1", "关键词2"],
  "south_net_5": ["粤","桂","滇","黔","琼"],
  "invest": "投资金额",
  "key_data": "核心数据",
  "source_url": "..."
}
```

【必检清单】
- 案例必须含明确的"承载方=新型电网"
- 必须落到 4 支撑方向之一（否则 reject）
- 必须含具体数据/工程名
- 南网 5 省项目优先
- 央企/政府双源验证
"""
