"""
NSP-IM v5 Prompt 模板
====================
基于 CERS DCICB 演讲第（二）节第 2 张 原文（精读后修正版）

【核心论点】
新型电网是支撑"六张网"体系运转的核心与基石。

【4 个支撑方向·精确版】
01. 为"算力网"注入绿色动能 — 算电协同 / 数据中心 / AI 算力
02. 为"通信网"提供运行保障 — 5G-A/6G / 海量通信基站
03. 赋能"智慧城市"与"物流网" — 地下管网 / 电动化 / 自动驾驶
04. 支撑"水网"与能源转型 — 源网荷储 / 西部绿电东部负荷
"""

# ============ 4 方向关键词（v5 精确版）============
V5_SUPPORT_KEYWORDS = {
    1: {  # 为算力网注入绿色动能
        "name": "为'算力网'注入绿色动能",
        "carrier_relation": "算力←绿电",
        "keywords": [
            "AI 算力", "吞电巨兽", "数据中心", "算电协同", "绿电",
            "阳江海底算力", "韶关集群", "海南算力", "东盟数据",
            "智算", "超算", "PUE", "零碳园区",
        ],
    },
    2: {  # 为通信网提供运行保障
        "name": "为'通信网'提供运行保障",
        "carrier_relation": "通信←稳定供电",
        "keywords": [
            "5G-A", "6G", "通信基站", "海量通信", "不间断",
            "F5G", "万兆光网", "50G-PON",
            "调度自动化", "通信覆盖", "稳定运行",
            "广西双万兆", "海南万兆自贸港", "中老光缆",
            "共享铁塔", "一杆多用",
        ],
    },
    3: {  # 赋能智慧城市与物流网
        "name": "赋能'智慧城市'与'物流网'",
        "carrier_relation": "城市/物流←能源支撑",
        "keywords": [
            "智慧城市", "城市地下管网", "城市生命线", "地下管网",
            "物流网", "电动化", "智能化", "自动驾驶",
            "港口岸电", "重卡超充", "重卡换电", "V2G",
            "南沙港", "北部湾港", "洋浦港",
            "中老铁路", "平陆运河", "西部陆海新通道",
        ],
    },
    4: {  # 支撑水网与能源转型
        "name": "支撑'水网'与能源转型",
        "carrier_relation": "水网/能源转型←源网荷储",
        "keywords": [
            "水网", "源网荷储", "西部绿电", "东部负荷",
            "新能源高效利用", "能源转型",
            "绿电直供", "西电东送", "抽水蓄能",
            "虚拟电厂", "新型储能", "新能源消纳",
            "源网荷储一体化",
        ],
    },
}


def detect_support_direction_v5(title: str, summary: str = "") -> int:
    """v5 精确识别"""
    text = (title + " " + summary).lower()
    scores = {1: 0, 2: 0, 3: 0, 4: 0}
    for direction, info in V5_SUPPORT_KEYWORDS.items():
        for kw in info["keywords"]:
            if kw.lower() in text:
                scores[direction] += 2
    # 优先级：水网/能源转型(D4) > 算力(D1) > 通信(D2) > 城市/物流(D3)
    # 因为 D4 是最大集合（兜底），避免算力关键词喧宾夺主
    if scores[4] >= 2: return 4
    if scores[1] >= 2: return 1
    if scores[2] >= 2: return 2
    if scores[3] >= 2: return 3
    # Fallback: 任何含"电力/能源/电网"通用政策归方向 4
    fallback_kws = ["电力", "能源", "电网", "南方", "输电", "配电", "新型电力", "新能源", "储能", "氢能", "充电", "电改"]
    for kw in fallback_kws:
        if kw in text:
            return 4
    return 0


def get_carrier_relation_v5(direction: int) -> str:
    if direction in V5_SUPPORT_KEYWORDS:
        return V5_SUPPORT_KEYWORDS[direction]["carrier_relation"]
    return "未识别"


# 兼容 v4 接口名（不破坏现有测试）
def detect_support_direction(title: str, summary: str = "") -> int:
    return detect_support_direction_v5(title, summary)


def get_carrier_relation(direction: int) -> str:
    return get_carrier_relation_v5(direction)


# 兼容：保留 V4 变量名但指向 v5
V4_SUPPORT_KEYWORDS = V5_SUPPORT_KEYWORDS


PROMPT_V5 = """你是 NSP-IM 政策情报官。每日从政策原文 + 行业动态中提取【六网协同案例】。

【核心论点·v5 精确版·基于 CERS DCICB 演讲原文】
新型电网是支撑"六张网"体系运转的核心与基石。所有协同案例必须能体现"新型电网=承载方"叙事。

【4 个支撑方向·必检·精确版】
01. 为"算力网"注入绿色动能（关键词：AI 算力、吞电巨兽、数据中心、算电协同、绿电）
02. 为"通信网"提供运行保障（关键词：5G-A、6G、海量通信基站、不间断、稳定运行）
03. 赋能"智慧城市"与"物流网"（关键词：智慧城市、城市地下管网、物流网、电动化、自动驾驶）
04. 支撑"水网"与能源转型（关键词：水网、源网荷储、西部绿电、东部负荷、新能源高效利用）

【输出模板·v5】
```json
{
  "case_id": "C-YYYY-MMDD-NNN",
  "date": "YYYY-MM-DD",
  "title": "案例标题",
  "support_direction": 1-4,
  "support_direction_name": "4 方向精确名称",
  "carrier_relation": "算力←绿电/通信←稳定供电/城市/物流←能源支撑/水网/能源转型←源网荷储",
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
