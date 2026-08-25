# D65 · GitHub Actions 配置 Runbook

## 前置条件
- GitHub repo: `qintingye/nsp-im`
- CloudBase 环境: `liwang-jiankong-d2eatyj479b1861`（liwangqingbaozhan 应用）

## Step 1: 配置 GitHub Secrets

访问 https://github.com/qintingye/nsp-im/settings/secrets/actions

点击 **New repository secret** 添加：

### Secret 1: TCB_SECRET_ID
- **Name**: `TCB_SECRET_ID`
- **Value**: `AKIDmjV4ureQIB6wiE9xa17EHJFzWr6A1vc7`

### Secret 2: TCB_SECRET_KEY
- **Name**: `TCB_SECRET_KEY`
- **Value**: `NXUKyPd2JNEsKZcT8apqfIhtoiPtHWY8`

> ⚠️ **注意**：`envId` (`liwang-jiankong-d2eatyj479b1861`) 已硬编码在 workflow yml 里，无需作为 Secret。

## Step 2: 推送代码

```bash
cd D:\hermes-dev-team\nsp-im
git push origin main
```

## Step 3: 查看 workflow 运行

访问 https://github.com/qintingye/nsp-im/actions

- 应该看到 "Sync V3.0 to CloudBase liwangqingbaozhan" workflow 触发
- 检查每个 step 是否成功：
  1. ✅ Checkout
  2. ✅ Setup Node
  3. ✅ Install tcb CLI
  4. ✅ CloudBase Login
  5. ✅ Deploy
  6. ✅ Output URL

## Step 4: 验证部署

访问永久 URL:
```
https://liuwangqingbaozhan-liuwang-jiankong-d2eatyj479b1861.webapps.tcloudbase.com/
```

应该看到 liuwangqingbaozhan 应用首页。

## 故障排查

### Workflow 失败：CloudBase Login 失败
- 检查 Secrets 是否正确配置（注意复制时不要有多余空格）
- 检查 SecretId/SecretKey 是否有效

### Workflow 失败：Deploy 失败
- 检查 `deploy-pkg/liuwang-jiankong/` 目录是否存在
- 检查 `index.html` 文件是否完整

### 访问 URL 404
- 等待 1-2 分钟（CloudBase CDN 缓存）
- 检查 workflow 日志确认 deploy 成功

## 安全提示

- ✅ Secrets 只在 GitHub Actions 中可见，不会泄露
- ✅ 每天定时触发（02:00 UTC）会自动同步最新代码
- ✅ workflow_dispatch 可手动触发紧急部署
