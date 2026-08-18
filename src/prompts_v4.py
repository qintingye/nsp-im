"""
NSP-IM v7 Prompt 模板
====================
基于 CERS DCICB 演讲第（三）节"六网协同方向"（重点任务 + 重点项目）

【核心论点·v7 战略升级】
聚焦"六网协同方向"的 24 项重点任务 + 30 项重点项目，谋划分"研究/实施/前期/储备/谋划"5 个批次。

【6 大协同方向 + 24 重点任务 + 30 重点项目】
01. 深化与水网协同（5 任务）
02. 深化与算力网协同（4 任务）
03. 深化与新一代通信网协同（2 任务）
04. 深化与地下管网协同（2 任务）
05. 深化与物流网协同（2 任务）
06. 深化"六网"综合协同（3 任务）
"""

# ============ 24 项重点任务（v7 升级）============
V7_TASKS = {
    1: {  # 深化与水网协同
        "name": "深化与水网协同",
        "tasks": [
            "推动流域水风光一体化开发调度",
            "推动中小型水库协同调度",
            "服务水网绿色灵活用能",
            "强化顶层规划协同",
            "强化工程建设协同",
        ],
    },
    2: {  # 深化与算力网协同
        "name": "深化与算力网协同",
        "tasks": [
            "强化算力基础设施供电保障",
            "构建电碳算协同调度能力",
            "探索算力负荷参与市场交易",
            "推进电网算力网同产业群发展",
        ],
    },
    3: {  # 深化与新一代通信网协同
        "name": "深化与新一代通信网协同",
        "tasks": [
            "提升电网与通信网双向支撑能力",
            "探索通信资源共享开放",
        ],
    },
    4: {  # 深化与地下管网协同
        "name": "深化与地下管网协同",
        "tasks": [
            "探索空间资源规划整合",
            "推动地下管廊协同运维",
        ],
    },
    5: {  # 深化与物流网协同
        "name": "深化与物流网协同",
        "tasks": [
            "构建绿色物流能源基础设施网络",
            "前瞻探索绿色物流数字凭证服务",
        ],
    },
    6: {  # 深化"六网"综合协同
        "name": "深化\"六网\"综合协同",
        "tasks": [
            "开展\"六网\"协同关键技术研究",
            "推进\"多站合一\"综合协同应用",
            "推进城市级综合协同应用",
            "服务双碳目标",
            "保障能源安全",
            "强化科技创新",
            "带动产业升级",
            "拓展国际合作",
            "打造示范工程",
        ],
    },
}

# ============ 30 项重点项目（v7 升级）============
V7_PROJECTS = [
    # 研究一批（4 项）
    {"name": "南方电网水风光储一体化开发与联合调度示范工程", "batch": "研究一批", "category": "水网"},
    {"name": "南方五省区电碳协同体系研究", "batch": "研究一批", "category": "算力网"},
    {"name": "广州、深圳城域级车网互动与共享虚拟电厂", "batch": "研究一批", "category": "算力网"},
    {"name": "南方五省区算电协同调度市场化交易机制与场景研究", "batch": "研究一批", "category": "算力网"},
    # 实施一批（8 项）
    {"name": "贵阳防灾减灾与综合能源调度示范工程", "batch": "实施一批", "category": "水网"},
    {"name": "南方五省区电碳协同示范工程", "batch": "实施一批", "category": "算力网"},
    {"name": "黔电送粤\"云电+绿电\"项目", "batch": "实施一批", "category": "算力网"},
    {"name": "广西边境绿色能源流电直供示范工程", "batch": "实施一批", "category": "算力网"},
    {"name": "平陆运河交能融合示范工程", "batch": "实施一批", "category": "物流网"},
    {"name": "多站合一示范工程", "batch": "实施一批", "category": "综合"},
    {"name": "贵安电算协同示范工程", "batch": "实施一批", "category": "算力网"},
    {"name": "汕头国际风电城零碳综合能源示范工程", "batch": "实施一批", "category": "综合"},
    # 前期一批（6 项）
    {"name": "\"空中一张车\"应急通信保障工程", "batch": "前期一批", "category": "通信网"},
    {"name": "大湾区低空基础设施保障工程", "batch": "前期一批", "category": "通信网"},
    {"name": "广州深圳临空区综合能源融合示范区", "batch": "前期一批", "category": "综合"},
    {"name": "广州深圳湾区大湾区融合示范区", "batch": "前期一批", "category": "综合"},
    {"name": "钦州平陆运河电网综合示范工程", "batch": "前期一批", "category": "物流网"},
    {"name": "广深超充走廊工程", "batch": "前期一批", "category": "物流网"},
    # 储备一批（6 项）
    {"name": "广州深圳交能融合电网综合工程", "batch": "储备一批", "category": "物流网"},
    {"name": "云贵粤港澳大湾区\"外电入粤\"重点工程", "batch": "储备一批", "category": "水网"},
    {"name": "广深\"快慢+通道\"氢储能协同与多元应用", "batch": "储备一批", "category": "储能"},
    {"name": "深圳能源互联网数字平台示范工程", "batch": "储备一批", "category": "综合"},
    {"name": "海南自贸港\"多能合一\"示范工程", "batch": "储备一批", "category": "综合"},
    {"name": "深城能源互联网综合能源工程", "batch": "储备一批", "category": "综合"},
    # 谋划一批（6 项）
    {"name": "算网融合超高速协同网络示范工程", "batch": "谋划一批", "category": "算力网"},
    {"name": "南网综合供能链新型电力系统数字认证平台", "batch": "谋划一批", "category": "综合"},
    {"name": "大湾区无人机输配电物流综合示范", "batch": "谋划一批", "category": "物流网"},
    {"name": "南网\"六网\"协同产业平台", "batch": "谋划一批", "category": "综合"},
    {"name": "多网协同市场化平台升级工程", "batch": "谋划一批", "category": "综合"},
    {"name": "智能化零碳园区与\"六网\"调控体系建设", "batch": "谋划一批", "category": "综合"},
]

# ============ 6 大协同方向关键词（v7 升级）============
V7_SUPPORT_KEYWORDS = {
    1: {  # 深化与水网协同
        "name": "深化与水网协同",
        "carrier_relation": "电网↔水网",
        "keywords": [
            "水网协同", "流域水风光", "水风光储", "抽水蓄能",
            "中小型水库", "水库调度", "流域调度",
            "防灾减灾", "水电", "水利", "水资源",
            "贵阳", "黔电", "云广直流", "西电东送",
        ],
    },
    2: {  # 深化与算力网协同
        "name": "深化与算力网协同",
        "carrier_relation": "电网↔算力网",
        "keywords": [
            "算力网协同", "电碳算", "电算协同",
            "数据中心", "绿电直供", "AI 算力", "智算",
            "算电融合", "算力负荷", "源网荷储一体化",
            "贵安", "韶关", "阳江", "贵阳",
            "黔电送粤", "云电入湾", "算力调度",
        ],
    },
    3: {  # 深化与新一代通信网协同
        "name": "深化与新一代通信网协同",
        "carrier_relation": "电网↔通信网",
        "keywords": [
            "通信网协同", "5G", "6G", "F5G",
            "通信基础设施", "应急通信",
            "一杆多用", "共享铁塔",
            "空中一张车", "低空基础设施",
            "通信资源共享", "通信双向支撑",
        ],
    },
    4: {  # 深化与地下管网协同
        "name": "深化与地下管网协同",
        "carrier_relation": "电网↔地下管网",
        "keywords": [
            "地下管网协同", "综合管廊", "GIL入廊", "电力隧道", "电缆入廊",
            "电缆通道", "管线共建", "城市地下空间", "管廊运维",
            "城市生命线", "城市更新", "供水管网", "燃气管网", "油气管道",
            "DMA", "分区计量", "漏损治理", "智慧水务", "管网更新",
            "老旧管网", "长输管道", "海水淡化",
        ],
    },
    5: {  # 深化与物流网协同
        "name": "深化与物流网协同",
        "carrier_relation": "电网↔物流网",
        "keywords": [
            "物流网协同", "绿色物流", "新能源重卡", "重卡换电", "绿电物流", "氢能重卡",
            "港口岸电", "光储充换", "V2G", "超充走廊", "多式联运",
            "铁水联运", "江海联运", "公铁联运", "空铁联运",
            "超充", "换电", "平陆运河", "中老铁路",
            "数字凭证", "绿电凭证", "碳排放",
            "广州深圳", "大湾区", "海南自贸港",
        ],
    },
    6: {  # 深化"六网"综合协同
        "name": "深化\"六网\"综合协同",
        "carrier_relation": "电网↔5网综合",
        "keywords": [
            "六网综合", "六网协同", "多站合一", "城市级协同",
            "数字底座", "零碳园区", "综合能源",
            "南方电网", "南网", "示范区",
        ],
    },
}


def detect_support_direction_v7(title: str, summary: str = "") -> int:
    """v7 6 大协同方向识别（精确版）"""
    text = (title + " " + summary).lower()
    scores = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    for direction, info in V7_SUPPORT_KEYWORDS.items():
        for kw in info["keywords"]:
            if kw.lower() in text:
                scores[direction] += 2
    # 优先级：D1(水) > D2(算力,最热) > D5(物流) > D3(通) > D4(管) > D6(综合)
    if scores[1] >= 2: return 1
    if scores[2] >= 2: return 2
    if scores[5] >= 2: return 5
    if scores[3] >= 2: return 3
    if scores[4] >= 2: return 4
    if scores[6] >= 2: return 6
    # Fallback: 任何"电力/能源/电网"归方向 6（综合）
    fallback_kws = ["电力", "能源", "电网", "南方", "输电", "配电", "新型电力", "新能源", "储能", "氢能", "充电", "电改"]
    for kw in fallback_kws:
        if kw in text:
            return 6
    return 0


def get_carrier_relation_v7(direction: int) -> str:
    if direction in V7_SUPPORT_KEYWORDS:
        return V7_SUPPORT_KEYWORDS[direction]["carrier_relation"]
    return "未识别"


# 兼容 v4-v6 接口名
def detect_support_direction(title: str, summary: str = "") -> int:
    return detect_support_direction_v7(title, summary)


def get_carrier_relation(direction: int) -> str:
    return get_carrier_relation_v7(direction)


# 兼容：保留 V4/V5/V6 变量名但指向 v7
V4_SUPPORT_KEYWORDS = V7_SUPPORT_KEYWORDS
V5_SUPPORT_KEYWORDS = V7_SUPPORT_KEYWORDS
V6_SUPPORT_KEYWORDS = V7_SUPPORT_KEYWORDS


# ============ v8 产业链 + 投资规模 + 投资节奏识别 ============
# 基于 CERS DCICB 演讲第（三）张：4 大核心受益产业链。
V8_INDUSTRY_CHAINS = {
    "电力与新能源": {
        "keywords": [
            "电力", "电网", "新能源", "风电", "光伏", "储能", "抽水蓄能",
            "绿电", "输配电", "特高压", "消纳", "电源", "电站",
        ],
        "theme": "能源转型",
    },
    "算力与通信": {
        "keywords": [
            "算力", "数据中心", "智算", "算电", "电碳算", "通信", "5G",
            "6G", "专网", "光缆", "互联网", "数字底座", "信息基础设施",
        ],
        "theme": "数字底座",
    },
    "工程与机械": {
        "keywords": [
            "工程", "机械", "施工", "设备", "管网", "管廊", "地下空间",
            "城市更新", "城市生命线", "基础设施", "改造", "建设", "招标",
            "变压器", "换流站", "工程总包",
        ],
        "theme": "基建提质",
    },
    "现代物流": {
        "keywords": [
            "物流", "多式联运", "港口", "岸电", "运河", "铁路", "公铁",
            "铁水", "江海联运", "绿色物流", "重卡", "换电", "超充",
            "运输", "供应链", "水道",
        ],
        "theme": "降本增效",
    },
}

# 统一使用中文可读字段，同时保留可供前端仪表盘消费的数值。
V8_INVESTMENT_SCALE = {
    "total": "26.9万亿元",
    "十五五期间": "26.9万亿元",
    "total_trillion": 26.9,
    "period": "十五五期间",
    "annual": "5.4万亿元",
    "年均": "5.4万亿元",
    "annual_trillion": 5.4,
    "2026": ">7万亿元",
    "2026年": ">7万亿元",
    "2026_trillion_min": 7.0,
    "phases": {
        "2026起步": {"years": [2026], "label": "2026 起步"},
        "2027-2028中期": {"years": [2027, 2028], "label": "2027-2028 中期"},
        "2029-2030后期": {"years": [2029, 2030], "label": "2029-2030 后期"},
        "中后期放量": {"years": [2027, 2028, 2029, 2030], "label": "中后期放量"},
        "十五五全周期": {"years": [2026, 2027, 2028, 2029, 2030], "label": "十五五全周期"},
    },
}
V8_INVESTMENT_SCALE["节奏"] = V8_INVESTMENT_SCALE["phases"]


def detect_industry_chain(title: str, summary: str = "") -> str:
    """识别政策最主要受益产业链，无法识别时返回 ``未识别``。

    采用关键词计分而非单一首个命中，避免“算电协同”等复合表述被误归类。
    同分时按电力、新算、工程、物流的稳定顺序返回，保证批量重跑可复现。
    """
    text = f"{title or ''} {summary or ''}".lower()
    scores = {}
    for chain, info in V8_INDUSTRY_CHAINS.items():
        scores[chain] = sum(1 for kw in info["keywords"] if kw.lower() in text)
    best = max(scores, key=scores.get)
    return best if scores[best] else "未识别"


def detect_investment_year(title: str, summary: str = "") -> str:
    """识别十五五投资节奏，返回标准化阶段值或 ``未明确``。"""
    text = f"{title or ''} {summary or ''}".lower()
    # 先匹配具体年份窗口（中后期措辞放最后，避免误判"2027-2028中期"）
    if any(k in text for k in ("2029-2030", "2029—2030", "2029–2030", "2029至2030", "2029 年至 2030 年")):
        return "2029-2030后期"
    if any(k in text for k in ("2027-2028", "2027—2028", "2027–2028", "2027至2028", "2027 年至 2028 年")):
        return "2027-2028中期"
    if "2026" in text and any(k in text for k in ("起步", "开局", "年度", "年投资", "年重点工程")):
        return "2026起步"
    if "十五五" in text and any(k in text for k in ("期间", "规划", "投资", "建设")):
        return "十五五全周期"
    if "中后期" in text or any(k in text for k in ("城市地下管网", "地下管网", "地下管廊", "算力网", "算力基础设施")):
        return "中后期放量"
    return "未明确"


# =====================================================================
# ============ W5-Day1 · 耦合算法 v1.0 ===============================
# =====================================================================
# 参考：docs/耦合算法-v1.0.md
# 核心公式：耦合分(网A, 网B) = f(N)×4 + g(W)×4 + h(V)×2   (满分 10)
#   f(N) = min(协同项目数 / 5, 1.0) × 4
#   g(W) = (1/N) × Σ √(W_Ai × W_Bi) × 4
#   h(V) = (有政策×0.7 + 有投资×0.8 + 有工程×1.0) / 2.5 × 2
# =====================================================================

# 6 网常量（顺序与权重数组严格一致）
COUPLING_NETS = ("grid", "water", "compute", "telecom", "pipe", "logi")
COUPLING_NETS_CN = {
    "grid":    "电网",
    "water":   "水网",
    "compute": "算力网",
    "telecom": "通信网",
    "pipe":    "地下管网",
    "logi":    "物流网",
}
# 网格基础权重：电网作为承载主体，所有项目至少包含电网
GRID_BASELINE = 0.55

# 推进批次 → 工程成熟度系数（用于验证因子 h(V) 的"工程"维度与 W 校准）
BATCH_MATURITY = {
    "研究一批": 0.40,
    "实施一批": 0.95,
    "前期一批": 0.70,
    "储备一批": 0.55,
    "谋划一批": 0.45,
}

# 4 因子权重（投资 40 + 技术 30 + 政策 20 + 工程 10 = 100%）
WEIGHT_FACTORS = {
    "invest":  0.40,   # 投资占比
    "tech":    0.30,   # 技术依赖
    "policy":  0.20,   # 政策提及
    "engineer": 0.10,  # 工程阶段
}

# 主网 → (投资, 技术, 政策, 工程) 4 因子模板；非主网按名称关键字补充
# 数字 0-1，越高代表该项目对该网的依赖越强
_PRIMARY_TEMPLATES = {
    # 水网项目：水电/抽蓄/水库为主，但所有电网项目都依赖电网
    "水网":   {"water": (0.65, 0.95, 0.90, 0.95), "grid": (0.30, 0.70, 0.85, 0.90)},
    # 算力网：电算协同，数据中心依赖电网+算力
    "算力网": {"compute": (0.70, 0.95, 0.95, 0.90), "grid": (0.50, 0.90, 0.90, 0.90)},
    # 通信网：5G/6G/低空，主电网+通信
    "通信网": {"telecom": (0.70, 0.95, 0.90, 0.90), "grid": (0.40, 0.75, 0.85, 0.85)},
    # 地下管网：综合管廊/电力隧道入廊，电网与管网共建
    "管":     {"pipe":    (0.60, 0.90, 0.85, 0.85), "grid": (0.45, 0.85, 0.80, 0.85)},
    # 物流网：重卡/岸电/超充走廊，强电网依赖
    "物流网": {"logi":    (0.65, 0.90, 0.90, 0.90), "grid": (0.45, 0.85, 0.85, 0.85)},
    # 储能：跨算力/水/电的综合，多网共济
    "储能":   {"compute": (0.40, 0.80, 0.85, 0.80), "grid": (0.55, 0.95, 0.90, 0.90), "water": (0.30, 0.60, 0.60, 0.70)},
    # 综合：六网都沾，按项目名字细调
    "综合":   {"grid": (0.50, 0.85, 0.90, 0.90)},
}

# 各项目名 → 次级 (net, factors) 调整项（项目级精度微调）
_PROJECT_OVERRIDES = {
    # 项目 9 平陆运河交能融合：水运+能源
    "平陆运河交能融合示范工程": {"water": (0.55, 0.85, 0.85, 0.85), "pipe": (0.20, 0.50, 0.50, 0.60)},
    # 项目 17 钦州平陆运河：水运+电
    "钦州平陆运河电网综合示范工程": {"water": (0.45, 0.75, 0.75, 0.80)},
    # 多站合一：变电站+储能+5G+数据 → 通信/算力加成
    "多站合一示范工程": {"compute": (0.45, 0.85, 0.85, 0.85), "telecom": (0.40, 0.80, 0.80, 0.80)},
    # 贵安电算协同
    "贵安电算协同示范工程": {"compute": (0.85, 0.95, 0.95, 0.95), "telecom": (0.30, 0.70, 0.70, 0.70)},
    # 电碳算 + 算电协同
    "南方五省区电碳协同体系研究": {"compute": (0.75, 0.95, 0.95, 0.85)},
    "南方五省区电碳协同示范工程": {"compute": (0.80, 0.95, 0.95, 0.90)},
    "南方五省区算电协同调度市场化交易机制与场景研究": {"compute": (0.80, 0.95, 0.90, 0.85)},
    # 车网互动/虚拟电厂
    "广州、深圳城域级车网互动与共享虚拟电厂": {"compute": (0.50, 0.85, 0.85, 0.85), "logi": (0.45, 0.75, 0.75, 0.80)},
    # 黔电送粤 / 云电+绿电：远距离输电+算力消纳
    "黔电送粤\"云电+绿电\"项目": {"water": (0.45, 0.80, 0.85, 0.85), "compute": (0.70, 0.90, 0.90, 0.85)},
    # 广西边境绿色能源流电直供
    "广西边境绿色能源流电直供示范工程": {"compute": (0.55, 0.85, 0.85, 0.80)},
    # 贵阳防灾减灾
    "贵阳防灾减灾与综合能源调度示范工程": {"pipe": (0.45, 0.80, 0.85, 0.85), "water": (0.55, 0.85, 0.85, 0.85)},
    # 汕头国际风电城零碳
    "汕头国际风电城零碳综合能源示范工程": {"compute": (0.30, 0.65, 0.70, 0.75), "logi": (0.30, 0.65, 0.70, 0.75)},
    # 空中一张车应急通信
    "\"空中一张车\"应急通信保障工程": {"telecom": (0.80, 0.95, 0.90, 0.85), "logi": (0.30, 0.60, 0.60, 0.65)},
    # 大湾区低空基础设施
    "大湾区低空基础设施保障工程": {"telecom": (0.80, 0.95, 0.90, 0.85), "logi": (0.40, 0.75, 0.75, 0.75)},
    # 广州深圳临空区综合能源
    "广州深圳临空区综合能源融合示范区": {"telecom": (0.40, 0.75, 0.75, 0.75), "logi": (0.55, 0.85, 0.85, 0.85)},
    # 湾区大湾区融合
    "广州深圳湾区大湾区融合示范区": {"logi": (0.50, 0.80, 0.80, 0.80), "compute": (0.40, 0.75, 0.75, 0.75)},
    # 广深超充走廊
    "广深超充走廊工程": {"logi": (0.85, 0.95, 0.95, 0.90), "telecom": (0.20, 0.50, 0.50, 0.55)},
    # 广州深圳交能融合
    "广州深圳交能融合电网综合工程": {"logi": (0.80, 0.95, 0.90, 0.85), "telecom": (0.30, 0.65, 0.65, 0.65)},
    # 云贵粤港澳大湾区"外电入粤"
    "云贵粤港澳大湾区\"外电入粤\"重点工程": {"water": (0.55, 0.85, 0.85, 0.80), "compute": (0.40, 0.75, 0.75, 0.75)},
    # 广深氢储能
    "广深\"快慢+通道\"氢储能协同与多元应用": {"logi": (0.55, 0.85, 0.85, 0.80), "compute": (0.35, 0.70, 0.70, 0.70)},
    # 深圳能源互联网数字平台
    "深圳能源互联网数字平台示范工程": {"compute": (0.50, 0.85, 0.85, 0.80)},
    # 海南自贸港多能合一
    "海南自贸港\"多能合一\"示范工程": {"logi": (0.40, 0.75, 0.75, 0.75), "compute": (0.30, 0.65, 0.65, 0.70)},
    # 深城能源互联网综合能源
    "深城能源互联网综合能源工程": {"compute": (0.40, 0.75, 0.75, 0.75)},
    # 算网融合超高速协同网络
    "算网融合超高速协同网络示范工程": {"compute": (0.80, 0.95, 0.90, 0.80), "telecom": (0.55, 0.85, 0.85, 0.80)},
    # 南网综合供能链数字认证
    "南网综合供能链新型电力系统数字认证平台": {"compute": (0.50, 0.85, 0.85, 0.80)},
    # 大湾区无人机输配电物流
    "大湾区无人机输配电物流综合示范": {"telecom": (0.55, 0.85, 0.85, 0.80), "logi": (0.65, 0.90, 0.90, 0.85)},
    # 南网六网协同产业平台
    "南网\"六网\"协同产业平台": {"compute": (0.45, 0.80, 0.85, 0.85), "telecom": (0.35, 0.70, 0.70, 0.70), "logi": (0.30, 0.65, 0.70, 0.70)},
    # 多网协同市场化平台升级
    "多网协同市场化平台升级工程": {"compute": (0.50, 0.85, 0.85, 0.85)},
    # 智能化零碳园区与六网调控
    "智能化零碳园区与\"六网\"调控体系建设": {"compute": (0.40, 0.75, 0.75, 0.75), "telecom": (0.35, 0.70, 0.70, 0.70), "logi": (0.30, 0.65, 0.65, 0.70)},
    # 水风光储一体化
    "南方电网水风光储一体化开发与联合调度示范工程": {"water": (0.85, 0.95, 0.95, 0.90), "compute": (0.30, 0.70, 0.70, 0.75)},
}


def _factors_to_weight(factors: tuple, batch: str) -> float:
    """4 因子加权合成单网权重 W = 投资×0.4 + 技术×0.3 + 政策×0.2 + 工程×0.1"""
    inv, tech, pol, eng = factors
    eng *= BATCH_MATURITY.get(batch, 0.5)
    w = (inv * WEIGHT_FACTORS["invest"]
         + tech * WEIGHT_FACTORS["tech"]
         + pol * WEIGHT_FACTORS["policy"]
         + eng * WEIGHT_FACTORS["engineer"])
    # 截断到 [0, 1]
    return max(0.0, min(1.0, round(w, 3)))


def get_project_weights(project: dict) -> dict:
    """为单个项目生成 6 网权重向量 W_Ai（电网/水/算/通/管/物）"""
    cat = project.get("category", "综合")
    batch = project.get("batch", "研究一批")
    name = project.get("name", "")

    # 1) 主网模板
    factors_map = {}
    primary = _PRIMARY_TEMPLATES.get(cat, _PRIMARY_TEMPLATES["综合"])
    for net, fac in primary.items():
        factors_map.setdefault(net, fac)

    # 2) 项目级 override（精度微调）
    override = _PROJECT_OVERRIDES.get(name, {})
    for net, fac in override.items():
        factors_map[net] = fac

    # 3) 计算 6 网权重
    weights = {}
    for net in COUPLING_NETS:
        if net == "grid":
            # 电网：所有项目都至少给 GRID_BASELINE，叠加项目 override
            fac_grid = factors_map.get("grid", (0.50, 0.85, 0.90, 0.90))
            w = _factors_to_weight(fac_grid, batch)
            weights[net] = max(GRID_BASELINE, w)
        else:
            if net in factors_map:
                weights[net] = _factors_to_weight(factors_map[net], batch)
            else:
                weights[net] = 0.0
    return weights


# 全量项目权重表（缓存）
PROJECT_WEIGHTS = [get_project_weights(p) for p in V7_PROJECTS]


def _fN(projects_count: int) -> float:
    """项目数因子 f(N) = min(N/5, 1) × 4"""
    return round(min(projects_count / 5.0, 1.0) * 4.0, 3)


def _gW(net_a: str, net_b: str) -> float:
    """利益因子 g(W) = (1/N) Σ √(W_Ai × W_Bi) × 4"""
    if not PROJECT_WEIGHTS:
        return 0.0
    s = 0.0
    n = 0
    for w in PROJECT_WEIGHTS:
        wa = w.get(net_a, 0.0)
        wb = w.get(net_b, 0.0)
        if wa <= 0 or wb <= 0:
            continue
        s += (wa * wb) ** 0.5
        n += 1
    if n == 0:
        return 0.0
    return round((s / n) * 4.0, 3)


def _hV() -> float:
    """验证因子 h(V)：5 源政策 + 投资金额 + 在建/规划工程 三维度

    南网 5 源政策已完整入库，假设 3 维度均有 → 取 0.7 + 0.8 + 1.0 = 2.5 / 2.5 × 2 = 2.0
    """
    return round((0.7 + 0.8 + 1.0) / 2.5 * 2.0, 3)


def calc_coupling_score(net_a: str, net_b: str) -> dict:
    """耦合综合分 v1.0：f(N)×4 + g(W)×4 + h(V)×2 (满分 10)

    Args:
        net_a: 网 A 英文 key (grid/water/compute/telecom/pipe/logi)
        net_b: 网 B 英文 key

    Returns:
        {
          "net_a": ..., "net_b": ...,
          "f_N": ..., "g_W": ..., "h_V": ...,
          "score": ...,
          "level": "高分协同/中等协同/弱协同",
        }
    """
    if net_a not in COUPLING_NETS or net_b not in COUPLING_NETS:
        raise ValueError(f"net must be one of {COUPLING_NETS}")
    # 协同项目数：两网权重都 > 0 的项目数
    n = sum(1 for w in PROJECT_WEIGHTS
            if w.get(net_a, 0) > 0 and w.get(net_b, 0) > 0)
    fN = _fN(n)
    gW = _gW(net_a, net_b)
    hV = _hV()
    score = round(fN + gW + hV, 2)
    score = min(score, 10.0)
    if score >= 8.0:
        level = "高分协同"
    elif score >= 6.0:
        level = "中等协同"
    else:
        level = "弱协同"
    return {
        "net_a": net_a,
        "net_b": net_b,
        "n_projects": n,
        "f_N": fN,
        "g_W": gW,
        "h_V": hV,
        "score": score,
        "level": level,
    }


def calc_coupling_matrix() -> dict:
    """计算完整 6×6 耦合矩阵（含 15 对非对角 + 6 自身）"""
    matrix = {}
    for a in COUPLING_NETS:
        matrix[a] = {}
        for b in COUPLING_NETS:
            if a == b:
                # 自身对：取 max(g_W) × 0.5 + h_V，反映单网成熟度
                w_self = [w.get(a, 0) for w in PROJECT_WEIGHTS]
                if not w_self:
                    score = 0.0
                else:
                    avg = sum(w_self) / len(w_self)
                    score = round(min(avg * 0.5, 1.0) * 4.0 + _hV(), 2)
                matrix[a][b] = {
                    "net_a": a, "net_b": b,
                    "n_projects": sum(1 for x in w_self if x > 0),
                    "f_N": 4.0 if any(x > 0 for x in w_self) else 0.0,
                    "g_W": round(avg * 4.0, 3) if w_self else 0.0,
                    "h_V": _hV(),
                    "score": score,
                    "level": "自身",
                }
            else:
                matrix[a][b] = calc_coupling_score(a, b)
    return matrix


PROMPT_V8 = """你是 NSP-IM 政策情报官。基于 CERS DCICB 演讲第（三）张，提取六网协同政策的产业链与投资节奏。

【v8 必检】
- 4 大核心受益产业链：电力与新能源（能源转型）、算力与通信（数字底座）、工程与机械（基建提质）、现代物流（降本增效）
- 十五五期间投资 26.9 万亿元，年均 5.4 万亿元，2026 年开局超过 7 万亿元
- 三阶段：2026 起步、2027-2028 中期、2029-2030 后期；城市地下管网/算力网中后期放量
- 跨界机会：城市生命线安全（机械+服务）、水网与物流网融合（水道兴物流旺）

【输出新增字段】
```json
{
  "industry_chain": "电力与新能源/算力与通信/工程与机械/现代物流/未识别",
  "investment_period": "2026起步/2027-2028中期/2029-2030后期/中后期放量/十五五全周期/未明确",
  "investment_scale": "十五五期间26.9万亿元；年均5.4万亿元；2026年开局>7万亿元"
}
```
"""


PROMPT_V7 = """你是 NSP-IM 政策情报官。每日从政策原文 + 行业动态中提取【六网协同案例】。

【核心论点·v7 战略升级版·基于 CERS DCICB 演讲第（三）节"六网协同方向"】
聚焦"六网协同方向"的 24 项重点任务 + 30 项重点项目，谋划分"研究/实施/前期/储备/谋划"5 个批次。

【6 大协同方向·必检·v7 战略版】
01. 深化与水网协同（5 任务）— 水风光/水网/抽水蓄能
02. 深化与算力网协同（4 任务）— 电碳算/电算协同/数据中心
03. 深化与新一代通信网协同（2 任务）— 5G/6G/通信基础设施
04. 深化与地下管网协同（2 任务）— 综合管廊/城市地下空间
05. 深化与物流网协同（2 任务）— 绿色物流/港口岸电/超充
06. 深化"六网"综合协同（3 任务）— 多站合一/城市级协同/零碳园区

【输出模板·v7】
```json
{
  "case_id": "C-YYYY-MMDD-NNN",
  "date": "YYYY-MM-DD",
  "title": "案例标题",
  "support_direction": 1-6,
  "support_direction_name": "6 大协同方向",
  "carrier_relation": "电网↔水网/电网↔算力/电网↔通信/电网↔管/电网↔物流/电网↔5网",
  "batch": "研究一批/实施一批/前期一批/储备一批/谋划一批",
  "support_keywords": ["关键词1", "关键词2"],
  "south_net_5": ["粤","桂","滇","黔","琼"],
  "invest": "投资金额",
  "key_data": "核心数据",
  "source_url": "..."
}
```

【必检清单】
- 案例必须落到 6 大协同方向之一
- 必须标注推进批次（研究/实施/前期/储备/谋划）
- 必须含具体数据/工程名
- 南网 5 省项目优先
- 央企/政府双源验证
"""