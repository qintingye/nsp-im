# V3.0 D63 · CNB Pages 自动化部署指南

> 六网协同情报平台 v3.0 永久 URL 自动化部署方案
> 选择 CNB Pages（腾讯云官方主推）：永久 URL + 推送即部署 + 国内极快 + 零配置 + 完全免费

---

## 为什么用 CNB Pages

| 优势 | 详情 |
|---|---|
| ✅ 腾讯云官方主推 | CODING 已退市，CNB 是新一代 |
| ✅ 永久 URL | `cnb.cool/<team>/<user>/nsp-im-v3` |
| ✅ 国内访问快 | 腾讯内网，<1s 响应 |
| ✅ 零配置 | 自动从 Git 部署 |
| ✅ HTTPS | 自动证书 |
| ✅ 免费 | 公开仓库 |

---

## 5 步上手

### Step 1：注册 CNB

URL：https://cnb.cool

- 微信扫码注册
- 创建团队（建议 `nsp-im-team`）
- 用户名：你的 CODING 用户名（**或新的**）

### Step 2：创建仓库

1. 顶部 "新建仓库"
2. 仓库名：`nsp-im-v3`
3. **可见度**：**公开**（Pages 免费条件）

### Step 3：推代码

**新 URL**：
```
https://cnb.cool/<team>/<user>/nsp-im-v3.git
```

**命令**：
```bash
cd D:\hermes-dev-team\nsp-im

# 添加 CNB remote（与 GitHub/CODING 并存）
git remote add cnb https://cnb.cool/<team>/<user>/nsp-im-v3.git

# 推送
git push cnb main
```

### Step 4：创建 `.cnb.yml`（自动化构建）

**文件**：`D:\hermes-dev-team\nsp-im\.cnb.yml`

```yaml
main:
  push:
    stages:
      - name: deploy
        tasks:
          - name: deploy to pages
            script: |
              cnb-pages-deploy
```

**详细配置参考**：https://docs.cnb.cool

### Step 5：开启 Pages

1. 仓库 → Pages 服务
2. 选择 "启用"
3. 配置：
   - 部署来源：当前仓库
   - 输出目录：`deploy-pkg/liuwang-jiankong`
4. 点击 "保存并部署"

---

## 自动化效果

| 操作 | 自动触发 |
|---|---|
| `git push cnb main` | ✅ 自动部署 |
| Webhook 触发 | ✅ 自动部署 |
| 手动触发 | ✅ 可 |

---

## 永久 URL 不变

**URL 永远不变** —— 每次 push 自动更新内容 —— 无需手动操作

---

## 比 GitHub/CODING 优势

| 项 | GitHub | CODING（退市）| CNB |
|---|---|---|---|
| 状态 | ✅ 活跃 | ❌ **已退市** | ✅ **官方主推** |
| 国内速度 | ⚠️ 慢 | - | ✅ **极快** |
| 永久 URL | ✅ | - | ✅ |
| 自动化 | ✅ | - | ✅ |
| 配置文件 | workflow | - | **`.cnb.yml`** |
| 推送限制 | PAT scope | - | ✅ **无限制** |

---

## 速度对比

| 平台 | 国内访问 |
|---|---|
| **GitHub** | ⚠️ 慢（**3-10秒**）|
| **CODING** | 退市 |
| **CNB** | ✅ **极快（<1秒）** |

---

## 推送流程（自动化）

```bash
# 日常更新只需 3 步
cd D:\hermes-dev-team\nsp-im
git add -A
git commit -m "your update message"
git push cnb main    # ← 自动部署到永久 URL
```

---

## 故障排查

| 问题 | 解决方案 |
|---|---|
| 推送失败（认证） | 检查 Git 用户名/密码（推荐用 Personal Access Token） |
| Pages 未自动部署 | 检查 `.cnb.yml` 是否在仓库根目录 |
| 输出目录 404 | 确认路径为 `deploy-pkg/liuwang-jiankong` |
| 仓库私有 | 切换为公开仓库（Pages 免费条件） |

---

## 参考文档

- 官方文档：https://docs.cnb.cool
- Pages 配置：https://docs.cnb.cool/zh/cli/pages.html
- 流水线配置：https://docs.cnb.cool/zh/guide.html

---

**D63 完成。等待用户执行推送。**