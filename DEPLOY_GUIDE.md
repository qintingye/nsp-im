# NSP-IM v3.0 部署与验收指南

> 本文档为「六网协同情报」v3.0 前端的部署与验收手册
> 对应交付物：`docs/preview/index.html` + `deploy-pkg/liuwang-jiankong/`

---

## 1. 部署方式

### 方式 A：单文件直跑（推荐）

```bash
# 把 docs/preview/index.html 复制到目标机器，双击即可
# 入口密码: nsp2026
```

### 方式 B：本地 HTTP 服务

```bash
cd docs/preview
python3 -m http.server 8080
# 浏览器: http://localhost:8080
```

### 方式 C：离线部署包（流网监控场景）

`deploy-pkg/liuwang-jiankong/` 包含完整可独立运行的离线包：

```bash
# 1. 把整个目录 scp / 拷贝到目标主机
# 2. 在目标主机运行
cd deploy-pkg/liuwang-jiankong/
python3 -m http.server 8080
```

---

## 2. 验收清单（D12 必跑 · 7 Tab 全检）

### 2.1 通用检查

| # | 检查项 | 命令 / 操作 | 期望 |
|---|---|---|---|
| 0 | 文件大小 | `wc -c docs/preview/index.html` | **≤ 50 KB**（当前 49.97 KB） |
| 1 | view 数 | `grep -c 'id="view-' index.html` | **7** |
| 2 | tab-btn 数 | `grep -c 'class="tab-btn' index.html` | **7** |
| 3 | JS 错误 | 浏览器 DevTools Console | **0 errors** |
| 4 | PC 无横向溢出 | DevTools Responsive 1440 viewport | `document.scrollWidth === 1440` |
| 5 | Mobile 无横向溢出 | DevTools Responsive 375 viewport | `document.scrollWidth === 375` |
| 6 | 入口密码 | 浏览器输入 `nsp2026` | 进入主页 |

### 2.2 7 Tab 内容检查

| Tab | 检查项 | 期望 |
|---|---|---|
| **1 战略总览** | 5 网状态卡 + 6 维度协同分 | 数字与颜色匹配二七四六矩阵 |
| **2 每日情报** | 政策卡片渲染 | 5+ 条，日期正确 |
| **3 26.9 万亿** | 标题 / 4 产业链 / 3 阶段 | "💰 26.9 万亿元" + 4 chain-card + 3 phase |
| **4 协同方向** | 6 方向 + 24 任务 + 30 项目 + 5 批次 | 6 dir-card + 7 dim-grid + 5 batch |
| **5 商业模式** | 8 模式 + 3 合作 + 4 风险 | 数字匹配 v9 数据 |
| **6 真实案例** | 11 案例 + 速览表 | 表格容器内可横滑（min-width 560px） |
| **7 智能简报** | 生成按钮 | 点击后简报有内容且可复制 |

### 2.3 自动化 WDW 自检

```bash
# PC 1440
python3 wdw-v3-test.py
# Mobile 375（D12 P0 修复关键）
python3 wdw-v3-d12-mobile.py
```

---

## 3. D12 P0 修复验收（WDW 复验项）

### 修复前问题（WDW 复验发现）

| # | 问题 | 严重度 |
|---|---|---|
| 1 | view-4 DOM **完全缺失** | P0 |
| 2 | Tab3（view-3）是「行动建议」3 卡片，应是「26.9 万亿」 | P0 |
| 3 | Mobile 375 Tab6 速览表横向溢出 10px | P0 |
| 4 | README.md / DEPLOY_GUIDE.md 缺失 | P1 |

### 修复后验证（D12 必跑）

- ✅ **view-4 DOM 存在**：grep `id="view-4"` index.html 命中
- ✅ **Tab3 显示 26.9 万亿**：grep `26.9 万亿` index.html ≥ 3 处（h2 + tab-btn + chain-share 等）
- ✅ **Mobile 375 无溢出**：`M_Tab6_overflow: False` + `M_doc_overflow: False`
- ✅ **README.md + DEPLOY_GUIDE.md 已创建**

---

## 4. 部署后回滚预案

如上线后发现问题：

```bash
cd D:\hermes-dev-team\nsp-im
git log --oneline -5
# 回滚到上一个稳定版本（D11: a1c1759）
git checkout a1c1759 -- docs/preview/index.html
```

---

## 5. 联系人

- 前端 Lead：NSP-IM v3.0 Frontend Lead
- 数据源：CERS DCICB 演讲幻灯片（南方电网）
- 仓库：`D:\hermes-dev-team\nsp-im\`
- 分支：`feat/w3d4-pwa-offline`