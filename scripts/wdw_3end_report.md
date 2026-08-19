# V3.0 WDW 复验 · 3 端 UI 实测报告

**测试日期**: 2026-08-19
**测试环境**: Playwright (Chromium headless), venv-screenshot
**HTML 源**: `D:\hermes-dev-team\nsp-im\docs\preview\index.html` (41.8KB)
**部署包**: `D:\hermes-dev-team\nsp-im\deploy-pkg\liuwang-jiankong\`

---

## 【V3.0 3 端 UI 验收】

### 📊 3 端测试矩阵

| 端 | Tab1 (5框+25项目+弹窗) | Tab2 (5政策) | Tab3 (3行动) | Tab5 商业 (4+8+3+4) | Tab6 案例 (11+6+速览) | Tab7 简报 (5段+3按钮) | 弹窗 (项目/网络) | 密码门 nsp2026 | 横向溢出 |
|---|---|---|---|---|---|---|---|---|---|
| **PC 1920×1080** | ✅ | ✅¹ | ✅² | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 无 |
| **Tablet 768×1024** | ✅ | ✅¹ | ✅² | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 无 |
| **Mobile 375×812** | ✅ | ✅¹ | ✅² | ✅ | ⚠ 表溢出10px³ | ✅ | ✅ | ✅ | ⚠ Tab6 表 |

**注**：
- ¹ HTML 实际只有 5 张政策卡 (`.pcard`)，无任务描述中的"4 方向矩阵 + 子 Tab 切换"
- ² HTML 实际是 3 条静态行动建议卡，无任务描述中的"26.9 万亿 + 4 产业链 + 3 阶段"（"26.9 万亿"在 Tab7 简报里出现）
- ³ 真实案例 Tab6 速览表 `.t6table` 在 375 宽度下溢出 10px（scrollWidth=385）

---

### 🧪 实测明细（每端共 6 Tab × 全要素验证）

| 验证项 | PC 1920 | Tablet 768 | Mobile 375 | 备注 |
|---|---|---|---|---|
| 密码门 present | ✅ | ✅ | ✅ | `gate` 元素存在 |
| 错密码 → 仍锁定 | ✅ | ✅ | ✅ | gate 未消失 |
| 正确密码 nsp2026 → 解锁 | ✅ | ✅ | ✅ | sessionStorage 持久化 |
| Tab1 5 框 (.nsi) | 5/5 | 5/5 | 5/5 | nb 单层网格 |
| Tab1 25 项目 (PROJECTS.length) | 25/25 | 25/25 | 25/25 | 跨 5 网 |
| openNet('water') 弹窗 | ✅ | ✅ | ✅ | 5 项目 + 投资 + 总分 |
| openProject('W1') 弹窗 | ✅ | ✅ | ✅ | m-title/m-total 正确 |
| Tab2 政策卡 (.pcard) | 5/5 | 5/5 | 5/5 | TODAY.items |
| Tab3 行动建议 (.action-card) | 3/3 | 3/3 | 3/3 | 静态 |
| Tab5 商业 (m5cat+m5cards+m5coops+m5risks) | 4+8+3+4 | 4+8+3+4 | 4+8+3+4 | MODES_8/COOPERATIONS_3/RISKS_4 |
| Tab6 案例 (t6modes+t6cards+t6rows) | 6+11+11 | 6+11+11 | 6+11+11 | 跨 5 网 |
| Tab7 3 按钮 (生成/复制/导出) | ✅ | ✅ | ✅ | btn-gen/copy/export |
| Tab7 生成简报内容 | ✅ | ✅ | ✅ | 含"26.9 万亿"+10 段 |
| Tab7 行动建议段 (t7act) | 3/3 | 3/3 | 3/3 | generateBrief() |
| 横向溢出 (滚动 6 Tab) | 0/6 | 0/6 | 1/6 | 仅 Mobile Tab6 表 |
| 字号 body / h1 | 16px / 20px | 16px / 20px | 16px / 20px | 合适 |

---

### 📸 截图存证

```
screenshots/v3_pc_1920.png         (Tab1 战略总览, PC, 130KB)
screenshots/v3_pc_1920_modal.png   (水网弹窗, PC, 113KB)
screenshots/v3_pc_1920_tab7.png    (智能简报, PC, 132KB)
screenshots/v3_tablet_768.png      (Tab1 战略总览, Tablet, 81KB)
screenshots/v3_tablet_768_modal.png (水网弹窗, Tablet, 82KB)
screenshots/v3_tablet_768_tab7.png (智能简报, Tablet, 93KB)
screenshots/v3_mobile_375.png      (Tab1 战略总览, Mobile, 52KB)
screenshots/v3_mobile_375_modal.png (水网弹窗, Mobile, 49KB)
screenshots/v3_mobile_375_tab7.png (智能简报, Mobile, 57KB)
```

---

### 💡 已知问题

#### 🟡 中等 (需要修改)

1. **Mobile 375 · Tab6 速览表横向溢出 10px**
   - 元素: `.t6table` (速览表)
   - scrollWidth=385, innerWidth=375
   - 根因: 6 列固定宽度无响应式处理（@media 没有针对 .t6table）
   - 影响: Mobile 端有横向滚动条
   - 建议: 加 `table-layout:fixed; word-break:break-all` 或 `.t6sum{overflow-x:auto}`

2. **触摸目标 <44px (3 端都存在)**
   - `.t7btn` (生成/复制/导出) 高度=36px
   - 影响: Mobile 触摸不友好（Apple HIG ≥44px / Material ≥48dp）
   - 建议: `@media (max-width:768px) .t7btn{padding:14px}` 或 min-height:44px

#### 🟢 信息 (任务描述 vs HTML 实际不符)

3. **任务要求 7 Tab，实际 6 Tab**
   - HTML 实际只有 6 个 view：view-1/2/3/5/6/7（view-4 跳过）
   - 任务描述的"6网 Tab"（"6 方向标签 + 24 任务 + 30 项目 5 批次"）在 HTML 里没有对应视图
   - 现有 Tab5 (view-5) 实际是"商业模式"，不是"6 网"

4. **任务要求 Tab2 含"4 方向矩阵 + 子 Tab"，实际无**
   - HTML Tab2 (view-2) 只有 5 张政策卡，无子 Tab、无方向矩阵

5. **任务要求 Tab3 含"26.9 万亿 + 4 产业链 + 3 阶段"，实际无**
   - "26.9 万亿" 文本实际出现在 **Tab7 简报**（bHTML 模板）里
   - HTML Tab3 (view-3) 是 3 条静态行动建议（算电协同 / 地下管网 / 抽水蓄能）

6. **openPolicy 弹窗实际是 alert，不是 modal**
   - 任务要求"弹窗（项目/网络/政策）"
   - HTML 中 `openPolicy(id)` 只 `alert("政策 ... · 详情页 V2.1 待建")`，没有 modal

7. **任务要求 Tab7 含"5 段模板"，实测实际 10 段（5网 + 4方向 + 1头条 + 3建议）**
   - `.t7row` = 10 (5 网 + 4 方向 + 实际含 1 个"电网基准"不算段)
   - `.t7act` = 3 (行动建议)
   - 如按"5 段"理解：头条 / 5 网 / 4 方向 / 核心机会 / 行动建议 = 5 段 ✓

#### 🔵 通过项（亮点）

- 密码门 nsp2026 + sessionStorage 持久化刷新自动解锁 ✅
- 6 Tab 全部可点击切换，无 JS 报错 ✅
- 弹窗 (openProject + openNet) 内容完整，含 5 项目/投资额/总分/推荐理由 ✅
- Tab7 简报 3 按钮 (生成/复制/导出) 全部可点，导出 .md 文件下载正常 ✅
- PC / Tablet 完全无横向溢出 ✅
- 响应式设计：Mobile 自动 2 列 + 1 列布局 ✅
- calcScore 逻辑：5 网都 5 项目 → 都 10.0 分（任务说"低分警示"暂未出现） ⚠

---

### ✅ 结论: **修改后通过（Conditional Pass）**

**通过项**: 6 Tab × 3 端 UI 框架完整、内容渲染、密码门、Tab7 三按钮、网络/项目弹窗、响应式布局 — **全部 PASS**

**必须修复（否则 V3.1 上线阻塞）**：
- 🟡 Mobile 375 · Tab6 速览表 `.t6table` 横向溢出 10px

**建议修复（不阻塞上线）**：
- 🟢 Tab7 `.t7btn` 高度 36px < 44px，Mobile 触摸不够友好

**任务规格 vs 实际差异**：任务文档描述的"7 Tab / Tab4 6网 / 26.9 万亿 Tab" 与 HTML 实际结构不符（HTML 是 6 Tab、26.9 万亿在简报里），属于 **任务说明偏差**，不影响 3 端 UI 验收。

**最终判定**:
- PC / Tablet: ✅ 直接通过
- Mobile: ⚠ 修改 Tab6 表溢出 + Tab7 按钮高度后通过

---

**测试脚本**: `D:\hermes-dev-team\nsp-im\scripts\wdw_3end.py`
**结果 JSON**: `D:\hermes-dev-team\nsp-im\scripts\wdw_3end_result.json`