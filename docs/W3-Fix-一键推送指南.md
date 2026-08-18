# 一键推送 14-d5 到 GitHub Pages

> **目的**：把本地最新 14-d5 (95KB, 密码 nsp2026) 推送到 GitHub 仓库 qintingye/nsp-im
> 替换当前公网部署的 W1-D4 早期版 (11.6KB)

## 前置检查

```bash
# 1. 确认你有权访问 qintingye/nsp-im 仓库
gh auth status

# 2. 确认本地 HTML 密码
grep "const PWD" "D:\Obsidian-Knowledge\01-Domain\新型电力系统建设\政策框架\六网协同\14-六网协同可视化-d5.html"
# 应输出: const PWD = 'nsp2026';
```

## 一键推送（3 步）

### Step 1：克隆/拉取 GitHub 仓库

```bash
cd D:\
git clone https://github.com/qintingye/nsp-im.git nsp-im-public
cd nsp-im-public
git status
```

### Step 2：复制最新 HTML + PWA 资源

```bash
# 复制最新 14-d5 为 index.html
cp "D:\Obsidian-Knowledge\01-Domain\新型电力系统建设\政策框架\六网协同\14-六网协同可视化-d5.html" \
   "D:\nsp-im-public\index.html"

# 复制 PWA 资源（如有最新 sw.js / manifest.json）
cp "D:\Obsidian-Knowledge\01-Domain\新型电力系统建设\政策框架\六网协同\manifest.json" \
   "D:\nsp-im-public\manifest.json" 2>/dev/null

cp "D:\Obsidian-Knowledge\01-Domain\新型电力系统建设\政策框架\六网协同\sw.js" \
   "D:\nsp-im-public\sw.js" 2>/dev/null
```

### Step 3：提交 + 推送

```bash
cd D:\nsp-im-public
git add -A
git commit -m "fix: 升级 W3-D5 (95KB) · 密码 nsp2026 · 7 Tab · PWA 增强"
git push origin main
# 或 master，看仓库默认分支
```

## 验证

```bash
# 1-2 分钟后访问公网
curl -I https://qintingye.github.io/nsp-im/

# 浏览器实测
# 1. 打开 https://qintingye.github.io/nsp-im/
# 2. 看 title 应该是 "六网协同情报平台"（不再是 "内网部署预览 (W1-D4)"）
# 3. 输密码 nsp2026
# 4. 应该看到 7 Tab + 完整数据
```

## 预期效果

| 项 | 修复前 | 修复后 |
|---|---|---|
| 公网 HTML 大小 | 11.6 KB | **95 KB** |
| 公网页面 title | "内网部署预览 (W1-D4)" | **"六网协同情报平台"** |
| 密码门 JS 验证 | 无（装饰）| **有（`nsp2026`）** |
| Tab 数 | 0 | **7** |
| 数据 | 空 | **61 条政策** |
| PWA | 无 | **加主屏 + 离线** |

## 回滚方案

```bash
# 如果新版本有问题
cd D:\nsp-im-public
git log --oneline -5
git revert HEAD  # 撤销最新提交
git push
```

## 故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| 推送被拒（403）| 无 GitHub 权限 | `gh auth login` 或联系 qintingye |
| 推送后公网不更新 | GitHub Pages 缓存 | 等 5 分钟，强刷 Ctrl+Shift+R |
| 推送后公网 404 | 仓库 Settings → Pages 未启用 | GitHub 仓库 → Settings → Pages → Source = main 分支 / (root) |
| HTML 仍是旧的 | 浏览器缓存 | Ctrl+Shift+R 强刷 |

---

**时间估计**：5-10 分钟（含 GitHub Pages 重新部署等待）

**联系 PM**（如果推送失败）：检查 gh auth status / 仓库权限
