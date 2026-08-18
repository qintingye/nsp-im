"""
NSP-IM v6 Prompt 模板
====================
基于 CERS DCICB 演讲第（二）节「发展机遇」板块 原文

【核心论点·v6 升级】
新型电网不是单向"承载方"，而是"多网协同的关键纽带"。

【4 个支撑方向·v6 协同融合版】
01. 电碳算协同 — 算力 + 碳 + 电网
02. 数智融合 — 通信 + 数据 + AI + 电网
03. 抽蓄互补 — 水网 + 抽水蓄能 + 电网
04. 交能融合 — 物流 + 交通 + 能源 + 电网
"""

# ============ 4 方向关键词（v6 协同融合版）============
V6_SUPPORT_KEYWORDS = {
    1: {  # 电碳算协同
        "name": "电碳算协同",
        "carrier_relation": "电碳算↔电网",
        "keywords": [
            "电碳算协同", "算电协同", "算力", "碳",
            "以电强算", "以算促电", "算力尽头是电力",
            "AI 算力", "数据中心", "绿电直供",
            "阳江海底算力", "韶关集群", "海南算力",
            "零碳园区", "PUE", "智算",
        ],
    },
    2: {  # 数智融合
        "name": "数智融合",
        "carrier_relation": "数智↔电网",
        "keywords": [
            "数智融合", "数智化", "数字孪生", "大数据",
            "新一代信息技术", "AI", "人工智能",
            "5G-A", "6G", "通信", "感知", "分析", "控制",
            "数字孪生电网", "调度自动化",
            "F5G", "万兆光网", "50G-PON",
            "自主核心", "特高压", "柔性直流", "构网型储能",
            "新型电力电子器件", "电力大模型",
        ],
    },
    3: {  # 抽蓄互补
        "name": "抽蓄互补",
        "carrier_relation": "抽蓄↔电网",
        "keywords": [
            "抽水蓄能", "抽蓄", "蓄能",
            "水网协同", "水风光储",
            "水电", "水利", "水资源",
            "雅砻江", "长江", "黄河", "珠江",
            "南网抽水蓄能", "2030年4000万千瓦",
            "新能源高效利用",
        ],
    },
    4: {  # 交能融合
        "name": "交能融合",
        "carrier_relation": "交能↔电网",
        "keywords": [
            "交能融合", "交通能源融合",
            "电动重卡", "重卡换电", "重卡超充", "V2G",
            "港口岸电", "岸电替油",
            "光储充换", "充换电网络",
            "南沙港", "北部湾港", "洋浦港",
            "中老铁路", "平陆运河", "西部陆海新通道",
            "自动驾驶", "智慧物流",
        ],
    },
}


def detect_support_direction_v6(title: str, summary: str = "") -> int:
    """v6 协同融合版"""
    text = (title + " " + summary).lower()
    scores = {1: 0, 2: 0, 3: 0, 4: 0}
    for direction, info in V6_SUPPORT_KEYWORDS.items():
        for kw in info["keywords"]:
            if kw.lower() in text:
                scores[direction] += 2
    # 优先级：D1(电碳算) > D2(数智) > D3(抽蓄) > D4(交能)
    # 电碳算是最高级协同（算+电+碳三网），最优先
    if scores[1] >= 2: return 1
    if scores[2] >= 2: return 2
    if scores[3] >= 2: return 3
    if scores[4] >= 2: return 4
    # Fallback: 任何含"电力/能源/电网"通用政策归方向 2（数智）
    fallback_kws = ["电力", "能源", "电网", "南方", "输电", "配电", "新型电力", "新能源", "储能", "氢能", "充电", "电改"]
    for kw in fallback_kws:
        if kw in text:
            return 2
    return 0


def get_carrier_relation_v6(direction: int) -> str:
    if direction in V6_SUPPORT_KEYWORDS:
        return V6_SUPPORT_KEYWORDS[direction]["carrier_relation"]
    return "未识别"


# 兼容 v4/v5 接口名
def detect_support_direction(title: str, summary: str = "") -> int:
    return detect_support_direction_v6(title, summary)


def get_carrier_relation(direction: int) -> str:
    return get_carrier_relation_v6(direction)


# 兼容：保留 V4 变量名但指向 v6
V4_SUPPORT_KEYWORDS = V6_SUPPORT_KEYWORDS
V5_SUPPORT_KEYWORDS = V6_SUPPORT_KEYWORDS


PROMPT_V6 = """你是 NSP-IM 政策情报官。每日从政策原文 + 行业动态中提取【六网协同案例】。

【核心论点·v6 协同融合版·基于 CERS DCICB 演讲「发展机遇」板块】
新型电网不是单向"承载方"，而是"多网协同的关键纽带"。

【4 个支撑方向·必检·协同融合版】
01. 电碳算协同（关键词：电碳算、算电协同、以电强算、AI 算力、零碳园区）
02. 数智融合（关键词：数智融合、数字孪生、AI、5G-A、特高压、构网型、电力大模型）
03. 抽蓄互补（关键词：抽水蓄能、水风光储、水电、雅砻江）
04. 交能融合（关键词：交能融合、电动重卡、港口岸电、光储充换、南沙港、平陆运河）

【输出模板·v6】
```json
{
  "case_id": "C-YYYY-MMDD-NNN",
  "date": "YYYY-MM-DD",
  "title": "案例标题",
  "support_direction": 1-4,
  "support_direction_name": "4 方向协同融合名称",
  "carrier_relation": "电碳算↔电网/数智↔电网/抽蓄↔电网/交能↔电网",
  "support_keywords": ["关键词1", "关键词2"],
  "south_net_5": ["粤","桂","滇","黔","琼"],
  "invest": "投资金额",
  "key_data": "核心数据",
  "source_url": "..."
}
```

【必检清单】
- 案例必须体现"双向协同"（不是单向承载）
- 必须落到 4 方向之一
- 必须含具体数据/工程名
- 南网 5 省项目优先
- 央企/政府双源验证
"""
