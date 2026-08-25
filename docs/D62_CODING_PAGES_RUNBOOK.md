# V3.0 D62 · CODING Pages 自动化部署指南

> 用户核心需求（已确认方案 A）：
> *"我需要自动化更新网站，不需要人工操作那种"*
>
> 架构：`本地 git push → CODING 仓库 → CODING Pages（自动）→ 永久 URL`

---

## 为什么用 CODING Pages

| 优势 | 详情 |
|---|---|
| ✅ 国内访问快 | 腾讯内网（对国内用户友好） |
| ✅ 永久 URL | `pages.code.tencent.com/<user>/<team>/<repo>/` |
| ✅ 零配置 | 自动从 Git 部署，无需写 workflow 文件 |
| ✅ HTTPS | 自动证书 |
| ✅ 免费 | 公开仓库即免费 |

---

## 5 步上手

### Step 1：注册 CODING

**URL**：https://coding.tencent.com/

- 微信扫码注册（支持个人 / 团队）
- 创建团队（选择 **"团队版"**）
- 团队名：`<your-team>`（建议 `nsp-im-team`）

> ⚠️ 个人版也能用 Pages，但团队版更适合多人协作 / 项目隔离。

---

### Step 2：创建项目 + 代码仓库

1. 进入团队 → **创建项目** → 项目名：`nsp-im-v3`
2. 项目设置 → 开启 **"代码托管"**（CODING Git）
3. 创建代码仓库 → 仓库名：`nsp-im-v3`
4. **可见度**：必须选 **公开**（Pages 必需）
5. 记下仓库 URL（形如 `https://e.coding.net/<team>/<user>/nsp-im-v3.git`）

---

### Step 3：推代码到 CODING

**新仓库 URL**（从 Step 2 复制）：

```
https://e.coding.net/<team>/<user>/nsp-im-v3.git
```

**命令**：

```bash
cd D:\hermes-dev-team\nsp-im

# 添加 CODING remote（和 GitHub 并存，互不影响）
git remote add coding https://e.coding.net/<team>/<user>/nsp-im-v3.git

# 推送（保留 GitHub 推送能力不变）
git push coding main
```

> 💡 这只是新增一个 remote，原来的 `git push origin main`（GitHub）继续可用。

**首次推送认证**：
- 用户名：`<your-coding-user>`
- 密码：Personal Token（团队设置 → 访问令牌 → 生成；勾选 `repo:read`、`repo:write`）
- 或者：直接用微信扫码登录 CODING 终端工具

---

### Step 4：开启 CODING Pages

1. 项目首页 → 左侧菜单 **"持续部署"** → **"静态网站"**
2. 选择 **"CODING Pages"**
3. 配置（按以下表格填）：

| 字段 | 值 |
|---|---|
| 构建环境 | 静态网站 |
| 部署来源 | Git |
| 分支 | `main` |
| 输出目录 | `deploy-pkg/liuwang-jiankong` |

4. 点击 **"保存并部署"**

> ⏱️ 首次部署约需 1-2 分钟。

---

### Step 5：访问永久 URL

部署完成后，Pages 会分配一个**永久 URL**（在静态网站页面可见）：

```
https://<team>-<user>-nsp-im-v3-1234.pages.code.tencent.com/
```

**首次访问提示**：
- 浏览器缓存 → `Ctrl + Shift + R` 强刷
- 或打开无痕模式验证

---

## 自动化效果

| 操作 | 自动触发部署？ |
|---|---|
| `git push coding main` | ✅ 是 |
| Webhook 触发（合并 PR） | ✅ 是 |
| 手动触发（控制台按钮） | ✅ 是 |

**核心**：本地修改 → `git push coding main` → 30 秒内永久 URL 内容自动更新 → **无需任何人工操作**。

---

## 永久 URL 不变

**URL 永远不变** —— 每次 `git push` 后 CDN 自动更新内容 —— **完全无需登录后台操作**。

这正是用户需要的：**"自动化更新网站，不需要人工操作"**。

---

## 比 GitHub Pages 优势

| 项 | GitHub Pages | CODING Pages |
|---|---|---|
| 国内访问速度 | ⚠️ 慢（海外 CDN） | ✅ 极快（腾讯内网） |
| 永久 URL | ✅ | ✅ |
| 自动化 push 部署 | ✅ | ✅ |
| Workflow 配置 | 需要 PAT scope / Actions | ✅ 零配置 |
| HTTPS 证书 | ✅ | ✅ |
| 免费 | ✅ | ✅（公开仓库） |

**结论**：国内用户优先选 CODING Pages。

---

## 日常使用速记

```bash
# 修改完代码后：
cd D:\hermes-dev-team\nsp-im

git add .
git commit -m "feat: 你的改动说明"

# 推 GitHub（保留能力）
git push origin main

# 推 CODING（触发 Pages 自动部署）
git push coding main

# 等 30 秒，访问永久 URL 即可看到更新
```

---

## 故障排查

| 问题 | 排查 |
|---|---|
| 推送认证失败 | 检查 Personal Token 是否过期；用 HTTPS 而非 SSH |
| Pages 没自动触发 | 检查仓库可见度是否为"公开"；Pages 配置分支是否为 `main` |
| 访问 404 | 检查输出目录是否为 `deploy-pkg/liuwang-jiankong`；检查 `index.html` 是否在该目录下 |
| 内容没更新 | 浏览器 `Ctrl+Shift+R` 强刷；或访问时加 `?v=<timestamp>` 绕过 CDN 缓存 |

---

## 下一步

- [x] D62 写完整文档（本文件）
- [ ] 用户：注册 CODING（5 分钟）
- [ ] 用户：执行 Step 3-5
- [ ] D63：验收永久 URL + 截图存档

---

*V3.0 D62 · 写于 2026-08-25*