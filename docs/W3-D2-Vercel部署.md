# W3-D2 · Vercel 公网部署指南（NSP-IM 政策雷达）

> 目标：把 `docs/preview/`（PWA 静态站）5 分钟内部署到 Vercel 公网域名，供 25 人内测使用。
> 部署材料：仓库根目录 `vercel.json` + `docs/preview/` 全部静态文件（已就绪）。
> **不需要后端，不需要构建。Vercel 仅作为静态 CDN。**

---

## 0. 准备（已就绪 · 0 分钟）

仓库已包含：
- `vercel.json` —— 部署配置（output = `docs/preview`，安全/缓存头）
- `docs/preview/index.html` —— PWA 主页（11.5 KB，含访问密码门禁）
- `docs/preview/manifest.json` + `sw.js` + `icons/` + `fonts/` —— PWA 离线能力
- `docs/preview/data/policies.json` (61 条政策) + `health.json`

**预期 URL 格式**（Vercel 自动分配）：
- 首次部署：`https://nsp-im.vercel.app`（默认按 repo 名）
- 后续每次 git push 自动部署到：`https://nsp-im-<short-hash>-<team>.vercel.app`
- 可绑定自定义域名（如 `nsp.yourdomain.com`）

---

## 1. 步骤 1：注册 Vercel（1 分钟）

1. 访问 https://vercel.com/signup
2. 选择 **"Continue with GitHub"**
3. 用仓库所有者的 GitHub 账号登录（如 nsp-im 组织账号）
4. 选择 Hobby 计划（免费，足够本次内测）
   - Pro 计划才支持 Password Protection；我们用 HTML 层门禁替代（见步骤 5）

---

## 2. 步骤 2：Import 仓库（1 分钟）

1. Vercel Dashboard → 点击 **"Add New… → Project"**
2. 选择 **"Import Git Repository"**
3. 在 GitHub 列表中找到 `nsp-im` 仓库（首次需要授权 Vercel 访问 GitHub）
4. 点击 **"Import"**

---

## 3. 步骤 3：配置 Project（1 分钟）

在 "Configure Project" 页面：

| 字段 | 值 | 说明 |
|------|----|------|
| **Project Name** | `nsp-im` | URL 第一段（可改） |
| **Framework Preset** | `Other` | 静态站 |
| **Root Directory** | `docs/preview` | ⚠️ **关键**，必须改 |
| **Build Command** | 留空 | 静态站无需构建 |
| **Output Directory** | 留空（自动） | vercel.json 已指定 |
| **Install Command** | 留空 | 无 npm 依赖 |

> ⚠️ 如果忘记改 Root Directory，Vercel 会找不到 `index.html` 而部署失败。

**Environment Variables**：无需（静态站，无后端密钥）。

点击 **"Deploy"**。

---

## 4. 步骤 4：等部署 & 拿 URL（1-2 分钟）

- Vercel 自动检测 `vercel.json` → 把 `docs/preview/` 作为静态目录发布
- 第一次部署通常 30-60 秒
- 成功后跳转到部署详情页，顶部显示：
  ```
  ✅ Deployed to https://nsp-im.vercel.app
  ```
- 点击 URL 访问 → 应该看到密码门禁页（输入 `nsp2026`）

**可选**：在 Project Settings → Domains 添加自定义域名。

---

## 5. 步骤 5：访问密码（已内置 · 0 分钟）

### 方式 A：HTML 层门禁（**默认方案 · 已实现**）

`docs/preview/index.html` 已硬编码密码门禁：
- 密码哈希：`843a6775fe97e053ff4d72aa4e4d80ab4ecae3fc86c6e1bd452410e845539af6`（SHA-256）
- 正确密码明文：**`nsp2026`**（v1.0 内测密码）
- 验证后 `sessionStorage.setItem('nspim_gate_ok', '1')`，刷新不重复询问
- 关闭浏览器标签即失效

**优点**：免费（Hobby 计划即可用）
**缺点**：HTML 可见，密码可通过 DevTools 找到 hash（但不能反向）；适合内测阶段

### 方式 B：Vercel Password Protection（可选 · 需 Pro）

Project Settings → Security → **Password Protection**：
- 仅 Pro 计划可用（$20/月）
- 输入用户名 + 密码
- 对整站生效（比 HTML 门禁更前置，CDN 层拦截）
- 适合正式发布

### 方式 C：Cloudflare Access（推荐 · 免费）

如果域名解析在 Cloudflare：
- Cloudflare Zero Trust → Access → 添加应用
- 策略：邮箱白名单（如 `@yourcompany.com`）
- 真正生产环境的方案，但需要先绑定自定义域名

---

## 6. 验证清单（部署后必跑）

- [ ] 访问 URL → 看到密码门禁页
- [ ] 输入 `nsp2026` → 进入主页
- [ ] 看到 61 条政策卡片
- [ ] 打开 DevTools → Application → Manifest，验证 PWA 可安装
- [ ] DevTools → Application → Service Workers，验证 SW 已注册（v3.4.0-w3d4）
- [ ] 离线模式（Network → Offline）→ 刷新 → 应显示 `offline.html`
- [ ] Lighthouse → 跑 Performance / PWA / Accessibility 评分（目标 ≥ 90）

---

## 7. 后续维护

| 场景 | 操作 |
|------|------|
| 修改了 `docs/preview/` 内任何文件 | `git push` → Vercel 自动部署（30 秒） |
| 修改了 `vercel.json` | 同上（注意：headres 改动需要清浏览器缓存才能看到效果） |
| 回滚到上一个版本 | Vercel Dashboard → Deployments → 点 ⋯ → "Promote to Production" |
| 看访问日志 | Vercel Dashboard → Project → Logs（实时） |
| 25 人反馈收集 | 见 `docs/W3-D1-真抓报告.md` |

---

## 8. 预计 URL 与访问密码（一句话总结）

```
URL 格式：https://nsp-im.vercel.app
访问密码：nsp2026（v1.0 内测）
内测人数：25 人
预计上线时间：5 分钟（含域名解析则 10 分钟）
```

---

## 附：为什么不真跑 `vercel deploy`

`vercel deploy` / `vercel --prod` 需要：
1. 交互式登录（`vercel login` → 浏览器跳转 OAuth）
2. 或 CI 环境里需要 `VERCEL_TOKEN`（个人 token，不应在文档/代码中提交）

本任务范围：**只准备部署材料 + 文档**（vercel.json 已就位，部署指南已写就）。
真实部署由项目负责人在本地终端执行：
```bash
cd D:\hermes-dev-team\nsp-im
npm i -g vercel       # 首次
vercel login          # 浏览器 GitHub 授权
vercel                # 测试部署（preview URL）
vercel --prod         # 生产部署（绑定 nsp-im.vercel.app）
```

或更简单：直接走 Dashboard Import 流程（步骤 1-4），无需本地 CLI。
