# `data/` 目录说明

## 用途
存放 NSP-IM Agent 每日抓取产出的政策/价格/标准/监测数据,供下游 monitor / compute / case 模块消费。

## 文件清单

### `policies.json`
- 当前为 **W1-D2 阶段 demo 数据**(`source: manual-demo`)
- 由后端手工写入,用于打通「生成 → 校验 → 消费」链路,避免 Day1 真实抓取政府站点触发 429 反爬
- 待 W1-D3+ `NdrcFetcher.run()` 接入后,会被真实抓取数据合并覆盖;demo 数据将被归档至 `data/cases/demo-20260819.json`

### 验证方式
```bash
# 1. JSON 合法
python -m json.tool data/policies.json > /dev/null && echo "OK"

# 2. Schema 合规(需 jsonschema)
pip install jsonschema
python -c "import json, jsonschema; \
  s=json.load(open('src/schemas/policies.schema.json')); \
  d=json.load(open('data/policies.json')); \
  jsonschema.validate(d, s); print('Schema OK')"
```

## Demo 数据来源说明

| ID | 范围 | 类别 | 说明 |
|---|---|---|---|
| P-NDRC-20260519-0001 | compute,monitor | policy | 绿电直连 — 算 |
| P-NDRC-20260603-0002 | water,monitor | policy | 供水管网漏损 — 水 |
| P-NDRC-20260618-0003 | telecom,grid,monitor | policy | 5G 专网 — 通 |
| P-NDRC-20260705-0004 | pipe,monitor | price | 燃气管网改造 — 管 |
| P-NDRC-20260722-0005 | logi,monitor | policy | 多式联运 — 物 |
| P-NDRC-20260802-0006 | monitor,grid | monitor | 价格监测 — monitor |
| P-NDRC-20260812-0007 | compute,monitor | standard | 算力计量 — 标准类示例 |

**数据来源**:政策文档编号与标题参考公开政策文本规范,内容为后端手工编写的演示样本,文档编号、URL、日期均为示意,**非真实抓取结果**。W1-D3 接入真实抓取后会用真实数据替换。

**覆盖维度**:
- 5 网(算/水/通/管/物)+ monitor 全覆盖(共 7 条)
- `category` 覆盖 `policy` / `price` / `monitor` / `standard` 四类
- `priority` 覆盖 1/2/3 三档
- `review_status` 全部为 `pending`(待人工/规则复核)
- 所有 `id` 符合 `^P-NDRC-YYYYMMDD-NNNN$` 模式,与 `src/fetchers/ndrc.py` L46 输出格式一致

## 目录子文件夹
- `cases/` — 案例/事件数据(下游消费)
- `intelligence/` — 二次加工的情报数据(后续 W2+ 产出)