# ADR-002 · 数据模型与 JSON Schema

> **状态**：已接受（2026-08-18）｜**类型**：架构决策
> **作者**：PM｜**关联**：ADR-001，src/schemas/*

## 背景
平台聚合 5 类数据源（ndrc/nea/csg/sgcc/bjx），需统一数据契约，保证前端消费与 CI 校验的一致性。

## 决策
定义 3 个 JSON Schema（draft-07），位于 `src/schemas/`：

| Schema | 文件 | 用途 |
|---|---|---|
| policies | `policies.schema.json` | 政策清单主数据（Tab1/2 消费） |
| intelligence | `intelligence.schema.json` | 每日情报摘要（Tab3 消费） |
| scenes | `scenes.schema.json` | 六网协同场景（Tab4/5 消费） |

**契约约定**：
- 字段命名：snake_case（数据层）→ 前端展示层自行映射 camelCase，禁止中文 key
- 必填字段由 `required` 硬约束；`additionalProperties` 允许扩展（防抓取源新增字段导致校验失败）
- `id` 全局唯一：`P-<源>-<日期>-<序号>`（政策）/ `HL-YYYY-MM-DD-NN`（情报）/ `S-<网>-<序号>`（场景）
- `review_status`：pending → approved / rejected（数据合规审核状态机，见 ADR-005）

## 后果
- CI 在 commit 前执行 `jsonschema` 校验，非法数据不允许入库
- BE 后续新增抓取源必须产出符合 schema 的 dict，否则校验失败
- 2026-08-18 发现：intelligence/scenes 两文件为示例实例而非合法 schema，已派 BE 修复（见 kanban 子任务）

## 待办
- [ ] BE 将 intelligence/scenes 重写为合法 draft-07 schema（t_9e9c04ef 子任务）
- [ ] BE 增加 schema 自校验单测（tests/test_schemas.py）
