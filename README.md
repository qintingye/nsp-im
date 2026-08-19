# NSP-IM v3.0 · 六网协同情报

> 南方电网「六网协同」（电网 / 水网 / 算力网 / 通信网 / 地下管网 / 物流网）情报平台 v3.0
> 前端预览: `docs/preview/index.html`（单文件 SPA，49.9 KB）

---

## ✨ v3.0 7 Tab 说明

| # | Tab 名称 | 内容核心 | 数据来源 |
|---|---|---|---|
| **1** | **战略总览** | 5 网态势感知 + 6 维度协同评分 | 二七四六协同矩阵 |
| **2** | **每日情报** | 61 条政策实时清单 | `policies.json` v3 |
| **3** | **26.9 万亿** | 4 大核心受益产业链 + 3 阶段投资节奏 | `CERS-DCICB-演讲-核心机会-v8.md` |
| **4** | **协同方向** | 6 大协同方向 + 24 重点任务 + 30 项目 / 5 批次 | `CERS-DCICB-演讲-协同方向-v7.md` |
| **5** | **商业模式** | 8 大成熟模式 + 3 对外合作 + 4 实操风险 | `CERS-DCICB-演讲-商业模式-v9.md` |
| **6** | **真实案例** | 11 个央企电网子公司落地 + 6 大商业化模式 + 速览表 | `CERS-DCICB-演讲-真实案例-v10.md` |
| **7** | **智能简报** | 一键合成 / 复制今日情报简报 | 聚合 Tab1-6 数据 |

---

## 🚀 快速启动

```bash
# 方式一：直接双击
open docs/preview/index.html

# 方式二：本地 HTTP 服务
cd docs/preview && python3 -m http.server 8080
# 浏览器访问 http://localhost:8080
```

**入口密码**：`nsp2026`

---

## 📁 关键文件

- `docs/preview/index.html` — 单文件 SPA（HTML + CSS + JS + 数据内联）
- `docs/CERS-DCICB-演讲-核心机会-v8.md` — Tab3 数据源
- `docs/CERS-DCICB-演讲-协同方向-v7.md` — Tab4 数据源
- `docs/CERS-DCICB-演讲-商业模式-v9.md` — Tab5 数据源
- `docs/CERS-DCICB-演讲-真实案例-v10.md` — Tab6 数据源
- `deploy-pkg/liuwang-jiankong/` — 离线部署包
- `DEPLOY_GUIDE.md` — 部署与验收清单

---

## 🧪 WDW 自验命令

```bash
python3 wdw-v3-test.py        # PC 端 1440 全流程
python3 wdw-v3-d12-mobile.py  # Mobile 375 端 (D12 修复验证)
```

---

## 🛠️ 技术栈

- 纯原生 HTML / CSS / JavaScript（零依赖）
- 单文件可离线运行（支持 PWA 缓存）
- 响应式：PC 1920 / Tablet 768 / Mobile 375 全适配
- 数据内联：可作为静态文件部署到任何 Web 服务器

---

## 📋 v3.0 更新日志

- **D11** ✅ Tab7 智能简报生成（41.8 KB）
- **D12** ✅ Tab3 重构（26.9 万亿）+ Tab4 新增（协同方向）+ Mobile 响应式修复（49.9 KB）