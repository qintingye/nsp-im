# NSP-IM v2.0 · CloudBase 部署指南 (W1-D5)

> **状态**: CLI 部署受阻（无登录态，无 APIKey），转 **方案 C 控制台手动上传**。
> **环境**: liuwang-jiankong · **公网 URL**: https://liuwang-jiankong-d2eatyj479b1861-1471069936.tcloudbaseapp.com/liuwang-jiankong/

---

## 🎯 一键方案 · 控制台手动上传（推荐，5 分钟）

### 步骤 1 · 打开静态托管页
浏览器访问：
```
https://console.cloud.tencent.com/tcb/env/overview?envId=liuwang-jiankong
```
→ 左侧菜单 **静态网站托管** → **上传文件**

### 步骤 2 · 上传整个目录
- 点击 **上传文件** 或 **上传文件夹**（建议"上传文件夹"）
- 选择本机路径：`D:\hermes-dev-team\nsp-im\deploy-pkg\liuwang-jiankong\`
- ⚠️ **关键**：上传时选择路径前缀为 **`/liuwang-jiankong/`**（不要填 `/`，会污染根目录）
- 等待上传完成（约 4.6MB 含 fonts/icons）

### 步骤 3 · 验证
浏览器访问：
```
https://liuwang-jiankong-d2eatyj479b1861-1471069936.tcloudbaseapp.com/liuwang-jiankong/
```
预期：
- 标题：`NSP-IM v2.0 · 六网协同情报`（**不是** `NSP-IM 六网协同情报平台 v1.0`）
- 3 个 Tab：战略总览 / 每日情报 / 行动建议
- 战略总览显示 5 个网络卡片 × 25 个项目

### 步骤 4 · （可选）清理 V1 残留
当前部署是 V1（95KB）。V2 上传后 V1 不会自动清。清理方式：
- 静态托管 → **文件管理** → 找到 `/liuwang-jiankong/` 下 V1 的旧文件 → 删除
- ⚠️ 本任务（W1-D5）不强制清理 V1 残留（见约束），可下一步 W1-D6 统一处理

---

## 🔧 方案 A · CLI 自动部署（备选，需要 APIKey）

### 步骤 1 · 取 APIKey
1. 控制台 https://console.cloud.tencent.com/tcb → liuwang-jiankong 环境
2. **环境 → 安全配置 → CloudBase API Key → 新建 API Key**
3. 复制 SecretID 和 SecretKey

### 步骤 2 · 切换到 Node 18+
默认 Node 16 触发 `ReadableStream is not defined`。临时用 Downloads/node 26：
```bash
export PATH="/c/Users/Administrator/Downloads:$PATH"
node --version   # 应显示 v26.7.0
tcb --version    # 3.7.3
```

### 步骤 3 · 登录 + 部署
```bash
tcb login --apiKeyId <SecretID> --apiKey <SecretKey>
tcb hosting deploy D:\hermes-dev-team\nsp-im\docs\preview -e liuwang-jiankong
```
注意：`tcb hosting deploy` 默认上传到 `/`，对应公网 URL `/`。要上传到 `/liuwang-jiankong/` 子路径，用：
```bash
tcb hosting deploy D:\hermes-dev-team\nsp-im\docs\preview -e liuwang-jiankong -r liuwang-jiankong
```

---

## 🧪 验证清单 (WDW)

部署后，访问 `https://liuwang-jiankong-...tcloudbaseapp.com/liuwang-jiankong/`，依次确认：

| 检查项 | 通过条件 |
|--------|---------|
| HTTP 200 | 浏览器打开无 4xx/5xx |
| 3 Tab 切换 | 战略总览/每日情报/行动建议 三个按钮可点，view 区块对应切换 |
| 25 项目可见 | Tab1 战略总览 5 网络卡片合计列出 W1-W5 / C1-C5 / T1-T5 / P1-P5 / L1-L5 |
| 弹窗可点 | Tab1 任意网络卡片 → 显示项目列表 → 点项目 → modal 显示投资/情报来源/4 评分/总分/评价 |
| 3 端响应式 | DevTools 切到 375×667 / 768×1024 / 1280×800 三档，布局不破 |

---

## 📦 已就绪的部署包

位置：`D:\hermes-dev-team\nsp-im\deploy-pkg\liuwang-jiankong\`

```
liuwang-jiankong/
├── index.html         (19846 bytes = 19.38KB, V2 纯净版)
├── data/              (health.json / policies.json / today.json)
├── fonts/             (图标字体)
├── icons/             (图标资源)
├── manifest.json      (PWA)
├── offline.html       (PWA offline)
├── sw.js              (PWA service worker)
└── README.md          (项目说明)
```

ZIP 包（便于上传）：`D:\hermes-dev-team\nsp-im\deploy-pkg\liuwang-jiankong.zip` (4.6MB)

---

## 🔑 V2 访问密码

页面密码：**`nsp2026`** （在 V2 HTML 中嵌入）

---

**W1-D5 状态**: 待用户执行方案 C 上传后 → DONE