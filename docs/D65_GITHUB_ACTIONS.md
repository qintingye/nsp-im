# V3.0 D65 · GitHub Actions 同步到 CloudBase liwangqingbaozhan

## 永久 URL
https://liuwangqingbaozhan-liuwang-jiankong-d2eatyj479b1861.webapps.tcloudbase.com/

## 架构
```
本地 git push origin main
   ↓
GitHub (qintingye/nsp-im)
   ↓
GitHub Actions (.github/workflows/sync-to-cloudbase.yml)
   ↓
CloudBase liwang-jiankong-d2eatyj479b1861
   ↓
应用 /liwangqingbaozhan
   ↓
永久 URL（公网可访问）
```

## 3 步配置

### 1. 在 GitHub 配 2 个 Secrets
访问 https://github.com/qintingye/nsp-im/settings/secrets/actions → **New repository secret**

| Name | Value |
|---|---|
| `TCB_SECRET_ID` | `${{ secrets.TCB_SECRET_ID }}` |
| `TCB_SECRET_KEY` | `${{ secrets.TCB_SECRET_KEY }}` |

> 注：本 workflow 把 `envId` 直接写死在 yml 里（不再读 Secret），所以只需要 2 个 Secrets。

### 2. push 代码
```bash
git push origin main
```

### 3. 触发 workflow
- **自动**：push main 后触发
- **定时**：每天 02:00 UTC = 10:00 CST 自动跑
- **手动**：GitHub → Actions → "Sync V3.0 to CloudBase" → Run workflow

## 触发条件
- `push` 到 `main` 分支
- 每天 02:00 UTC（10:00 CST）定时
- `workflow_dispatch` 手动触发

## 完整配置指南
- [GitHub Secrets 配置](D65_GITHUB_ACTIONS_RUNBOOK.md)

## 自检
```bash
# commit 已就绪（未 push）
git log --oneline -3
```

【状态】DONE-PREPARED

【下一步】
1. 用户: 配 GitHub Secrets (2 个: TCB_SECRET_ID + TCB_SECRET_KEY)
2. 用户: git push origin main
3. 用户: 看 workflow 跑成功（https://github.com/qintingye/nsp-im/actions）
4. 访问永久 URL 验证: https://liuwangqingbaozhan-liuwang-jiankong-d2eatyj479b1861.webapps.tcloudbase.com/
