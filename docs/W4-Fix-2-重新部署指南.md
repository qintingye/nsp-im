# W4-Fix-2 重新部署指南（手动 3 步）

> **最新修复**：5 框放大 + 字体加大
> **部署包**：`D:\nsp-im-vercel\index.html`（102.9KB）

## ✅ 本次修复清单

| # | 项 | 修复前 | 修复后 |
|---|---|---|---|
| 1 | viewBox | 1280×780 | **1920×1080** |
| 2 | 5 框大小 | 280×220 | **480×340**（70%↑）|
| 3 | 中心圆 r | 130 | **180** |
| 4 | 5 框主标题字号 | 19 | **26** |
| 5 | 子项字号 | 12 | **16** |
| 6 | 协同分字号 | 13 | **18** |
| 7 | 中心主标题 | 22 | **34** |
| 8 | 中心副标题 | 14 | **20** |

## 🚀 3 步手动部署

### Step 1：进 CloudBase 静态网站托管
<https://console.cloud.tencent.com/tcb/dev>

### Step 2：选 liuwang-jiankong 应用 → 文件管理
- 找 `index.html`（**旧版 102KB**）
- **删除** 旧 index.html

### Step 3：上传新 index.html
- 点 "**上传文件**"
- 选 `D:\nsp-im-vercel\index.html`（102.9KB · 修复版）
- 等 30 秒

## 🌐 部署完访问 URL

```
https://liuwang-jiankong-d2eatyj479b1861-1471069936.tcloudbaseapp.com/liuwang-jiankong/
```

输密码 `nsp2026` → 强刷 Ctrl+Shift+R

## 🎯 验收点

- ✅ 5 框明显放大（占满屏幕 80%+）
- ✅ 字体变大（5 框主标题 26 号，子项 16 号）
- ✅ 中心圆放大到 r=180
- ✅ 协同分居中（不跑出框）
- ✅ 城市地下管网居中下

## ⏳ 上传后告诉我

- "已上传" → 我立即 Playwright 复测
- 看到截图问题 → 我继续修

---

**部署包就绪**：`D:\nsp-im-vercel\index.html`（102.9KB）🚀
