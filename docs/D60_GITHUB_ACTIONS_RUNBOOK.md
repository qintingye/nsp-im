# NSP-IM v3.0 · D60 GitHub Actions Runbook

> 目标：让 GitHub Actions 自动把 `feat/w3d4-pwa-offline` 的更新部署到 CloudBase
> 永久 URL：`https://liwangqingbaozhan-liuwang-jiankong-d2eatyj479b1861.webapps.tcloudbase.com/liuwangqingbaozhan/`

---

## 1. 当前已就绪的交付物（D60 commit `2159726`）

| 文件 | 状态 |
|---|---|
| `.github/workflows/sync-to-cloudbase.yml` | ✅ 已创建（10 steps，3 触发器） |
| `scripts/build-deploy-bundle.py` | ✅ 已创建（已通过 `--validate-only` + `--output` 测试） |
| `.gitignore` | ✅ 已更新（忽略 deploy-bundle/, zip, *.bak 等） |
| Git commit `2159726` | ✅ 在 `feat/w3d4-pwa-offline` 分支 |

**本地验证结果**：
- bundle = 4 文件，275.5 KB（与 D59 上传清单完全一致）
- 数据已更新到 D58 (`data/policies.json` 129KB, `data/projects.json` 51KB)

---

## 2. 还需要用户手动完成的 4 步

### 2.1 创建 GitHub 仓库

- 访问 https://github.com/new
- Repository name: `nsp-im-v3`（或自定）
- Visibility: **Public**（推荐，无需付费）或 Private
- **不**勾选 "Initialize with README/.gitignore"（我们本地已经有）
- 点击 "Create repository"

### 2.2 推送代码

在 `D:\hermes-dev-team\nsp-im\` 目录下：

```bash
git remote add origin https://github.com/<your-username>/nsp-im-v3.git
git push -u origin feat/w3d4-pwa-offline
```

> **⚠️ 注意**：D60 commit 在 `feat/w3d4-pwa-offline` 分支，**不是 main**。
> workflow 监听的是 `main` 分支。如果想直接让 workflow 生效，请：

```bash
git checkout main      # 或 git checkout -b main
git merge feat/w3d4-pwa-offline
git push -u origin main
```

或者直接修改 `.github/workflows/sync-to-cloudbase.yml` 把 `branches: [ main ]`
改成 `branches: [ feat/w3d4-pwa-offline, main ]`。

### 2.3 配置 GitHub Secrets

1. **获取 CloudBase API 密钥**：
   - 访问 https://console.cloud.tencent.com/cam/capi
   - 点击 "新建密钥" → 勾选 "云开发 CloudBase" 权限
   - 记下 **SecretId** 和 **SecretKey**（SecretKey 只显示一次！）

2. **配置 GitHub Secrets**：
   - 打开仓库 → `Settings` → `Secrets and variables` → `Actions`
   - 点击 `New repository secret`，依次添加：

| Name | Value |
|---|---|
| `TCB_SECRET_ID` | `<你的 SecretId>` |
| `TCB_SECRET_KEY` | `<你的 SecretKey>` |

### 2.4 首次部署验证

- 打开仓库 → `Actions` tab
- 左侧选 "Sync V3.0 to CloudBase liwangqingbaozhan"
- 右侧 `Run workflow` → Branch: `main` → 点击绿色按钮
- 等待 3-5 分钟（首次会下载依赖 + 装 tcb CLI）
- 看到绿色 ✓ 即部署成功
- 浏览器访问永久 URL 验证 V3.0：
  ```
  https://liwangqingbaozhan-liuwang-jiankong-d2eatyj479b1861.webapps.tcloudbase.com/liuwangqingbaozhan/
  ```

---

## 3. 日常使用

### 自动触发（推荐）

- **每次 push 到 main**：自动部署（~3 分钟）
- **每天 10:00 CST (02:00 UTC) 自动同步**：即使没有代码改动也会跑一次

### 手动触发

- 仓库 → `Actions` → 选 workflow → `Run workflow` → `Run`

### 数据更新流程（项目情报每天变）

数据更新有两种方式：

1. **手动改数据**（本地）：
   ```bash
   # 编辑 data/policies.json / data/projects.json / data/today.json
   git add data/
   git commit -m "data: 更新政策/项目"
   git push
   # → GitHub Actions 自动部署新版
   ```

2. **现有 daily-fetch.yml**：每天 UTC 01:00 (CST 09:00) 自动跑抓取脚本，更新 `data/` 后 commit + push
   - 此 push **也会触发** sync-to-cloudbase.yml
   - 形成"09:00 抓数据 → push → 自动 10:00 部署"的级联

---

## 4. 故障排查

| 现象 | 可能原因 | 解决方法 |
|---|---|---|
| Workflow 报 `tcb login` 失败 | Secrets 没配 / 配错 | 检查 `Settings → Secrets` 两个值 |
| Workflow 报 `hosting deploy` 失败 | SecretId 没 CloudBase 权限 | 重新创建密钥 + 勾选 CloudBase 权限 |
| 部署成功但页面 404 | 路径写错 | 确认 `TCB_HOSTING_PATH = /liuwangqingbaozhan` |
| 数据不更新 | fetch 被缓存 | 浏览器强制刷新 Ctrl+F5 |
| 页面有内容但 policies 是 fallback | data/*.json 没上传 | 看 workflow 日志 `List bundle` 步骤 |
| `validate-only` 步骤失败 | JSON 损坏 | 本地跑 `python scripts/build-deploy-bundle.py --validate-only` 找问题 |

---

## 5. 关键设计决策（与原任务书差异）

| 原任务书 | D60 实际方案 | 原因 |
|---|---|---|
| 用 `replace('/*__TODAY__*/', ...)` 注入数据 | **不替换**，直接 fetch | D36 已经改用 `fetch('./data/policies.json')`，原 HTML 无占位符 |
| bundle 含 `manifest.json` / `sw.js` / `fonts/` | **不打包** | grep 发现 index.html 未引用这些文件，避免 4.5MB 死资源 |
| bundle 含 `health.json` | **不打包** | index.html 未引用 `health.json` |
| Python 单行 `-c` heredoc 嵌入 workflow | **外置 Python 脚本** | 可本地/CI 复用、可单测、报错更清晰 |
| 没用 `concurrency` | **新增** | 防止 cron + push 双重触发产生并发部署 |

实际部署清单（4 文件，275.5 KB）：

```
deploy-bundle/liuwangqingbaozhan/
├── index.html                    100 KB
└── data/
    ├── policies.json             130 KB  (65 条政策 · D58 已修真原文 URL)
    ├── projects.json              51 KB  (32 项目 · D38 real-fetch-v3)
    └── today.json                  1 KB  (5 条今日要闻)
```