# W3-Fix · 公网密码诊断报告

**日期**：2026-08-18
**诊断人**：NSP-IM 项目负责人（Agent）
**目标 URL**：https://qintingye.github.io/nsp-im/

---

## 一、公网实测（curl + Playwright）

### 1.1 基本信息

| 项目 | 实测值 |
|------|--------|
| HTML title | `NSP-IM 政策雷达 · 内网部署预览 (W1-D4)` |
| 部署大小 | **11.6 KB**（11,592 bytes，HTTP `Content-Length`） |
| Last-Modified | Tue, 18 Aug 2026 02:49:29 GMT |
| 文件内版本号 | `W3-D2 公网 PoC`（注释）+ title 写 `W1-D4` |
| SHA-256 hash | `843a6775fe97e053ff4d72aa4e4d80ab4ecae3fc86c6e1bd452410e845539af6` |

### 1.2 密码门 JS 验证测试

**结论：JS 验证存在且工作正常，不是装饰门。**

实测代码：
```javascript
// 公网文件内的密码门逻辑（IIFE 包裹）
var GATE_HASH = '843a6775fe97e053ff4d72aa4e4d80ab4ecae3fc86c6e1bd452410e845539af6';
var GATE_KEY = 'nspim_gate_ok';

function sha256hex(str) {
  return crypto.subtle.digest('SHA-256', new TextEncoder().encode(str))
    .then(buf => Array.from(new Uint8Array(buf))
      .map(b => b.toString(16).padStart(2, '0')).join(''));
}

function tryEnter() {
  sha256hex(inp.value).then(h => {
    if (h === GATE_HASH) { gate.style.display = 'none'; sessionStorage.setItem(GATE_KEY, '1'); }
    else { err.style.display = 'block'; inp.value = ''; }
  });
}
```

**Playwright 实测结果**：

| 测试输入 | 结果 |
|---------|------|
| `wrong_password_xyz` | ❌ `errDisplay=block`, `errText="密码错误，请重试"`, `session=null` |
| `nsp2026` | ❌ SHA-256 不匹配（`5c5236da...` ≠ `843a6775...`） |
| `nspim2026` / `admin` / `六网协同` 等 20+ 候选 | ❌ 全部不匹配 |

### 1.3 实际部署版本判定

公网部署的 **既不是** W1-D4 早期版（11.6KB），**也不是** 本地 14-d5（95KB）。

| 候选 | 大小 | 密码机制 | 是否公网版本 |
|------|------|---------|-------------|
| 本地 `13-六网协同可视化-d4.html` | 95.7 KB | 明文 `nsp2026`（`if(v === PWD)`） | ❌ |
| 本地 `14-六网协同可视化-d5.html` | 95.6 KB | 明文 `nsp2026`（同上） | ❌ |
| **公网实际部署** | **11.6 KB** | **SHA-256 hash 比对** | ✅ |

公网是 **第三个独立版本**——11.6KB 的轻量 PoC，标题写 "W1-D4" 但源码注释是 "W3-D2 公网 PoC"。这个版本之前在某个本地文件 / 外部脚本中生成过，**没有留在本地六网协同目录下**。

---

## 二、诊断

### 2.1 问题根因

1. **公网部署 ≠ 本地最新**：GitHub Pages 上的版本（11.6KB，SHA-256 验证）不是本地的 d4/d5（95KB，明文 `nsp2026`）。两边代码是分叉的。
2. **密码"丢失"**：公网版本用 SHA-256 hash 存密码，但本地没人记得原密码是什么。已用 ~30 个常见候选（`nsp2026`、`nspim2026`、`admin`、`六网协同` 等）反查 hash，全部不匹配。
3. **本地 d5 密码明文暴露**：如果直接把本地 d5 推上去，密码会以明文 `nsp2026` 写在源码里——**安全等级比当前公网版本（hash 验证）更低**，属于退步。
4. **历史 commit 误导**：git log 里最近 4 个 commit 都在改 `g8JoSB7ZavUiYn → nsp2026`，说明项目内部确实有过别密码、最终定 `nsp2026` 的过程，但公网版本从未同步更新。

### 2.2 用户反馈复盘

用户说"密码不对"——**完全正确**。`nsp2026` 在公网版本里就是错的（SHA-256 对不上）。原任务的"早期版 W1-D4 密码门是装饰"假设也不成立：**公网不是 W1-D4 早期版，是 W3-D2 重写的独立 PoC，且 JS 验证正常工作。**

---

## 三、修复方案

### 方案 A（推荐）：公网版本保持，公布正确密码

**前提**：找回公网版 SHA-256 hash 对应的明文密码。
- 如果原密码已知 → 直接告诉用户
- 如果原密码丢失 → 改 hash（见方案 B-2）

### 方案 B：推本地 14-d5 上公网 + 升级密码保护

如果一定要用本地最新可视化效果：

**B-1. 推本地 d5，但保留 SHA-256 机制**（不让密码明文暴露）
1. 拷贝 `D:\Obsidian-Knowledge\...\14-六网协同可视化-d5.html` → `/d/hermes-dev-team/nsp-im/index.html`
2. 替换 `const PWD = 'nsp2026'` + `if(v === PWD)` → 改用公网版本的 SHA-256 IIFE
3. 用 Python 算新密码的 hash：
   ```bash
   cd /d/hermes-dev-team/nsp-im
   source .venv/bin/activate   # 或 .venv-d5
   python -c "import hashlib; print(hashlib.sha256(b'YOUR_NEW_PASSWORD').hexdigest())"
   ```
4. 把 hash 填进 `GATE_HASH`，并修改 `nsp_pwd` → `nspim_gate_ok` 保持一致
5. git add/commit，让用户手动 push

**B-2. 不知道新密码**：用方案 B-1 流程，但密码选 `nsp2026`，hash 已知 = `5c5236da4fefd43f...`（直接计算填进去）

### 方案 C（最小改动）：仅改公网 hash 对应的密码

只改一行 `GATE_HASH` 的值，让密码继续是 `nsp2026`：
```javascript
var GATE_HASH = '5c5236da4fefd43f...nsp2026的SHA256';  // 替换为 nsp2026 的真实 hash
```
但这需要找到公网版本的源码（本地找不到），只能 push 新 index.html 时顺便改。

---

## 四、推荐执行步骤（用户手动操作）

Agent 不能 `git push` 到 `qintingye/nsp-im`（用户账号）。以下步骤需用户执行：

```bash
# 1. 进入本地 nsp-im 仓库
cd /d/hermes-dev-team/nsp-im

# 2. 决定走哪个方案（推荐方案 B-2）：
#    把本地 d5 部署上去，密码沿用 nsp2026，但用 hash 存储
cp "/d/Obsidian-Knowledge/01-Domain/新型电力系统建设/政策框架/六网协同/14-六网协同可视化-d5.html" ./index.html

# 3. 编辑 index.html，把
#    const PWD = 'nsp2026';  if (v === PWD) { ... }
#    替换成公网版本的 SHA-256 IIFE（见本报告 §1.2）
#    GATE_HASH 填：5c5236da4fefd43f... （nsp2026 的真实 SHA-256，下面命令生成）

python -c "import hashlib; print(hashlib.sha256(b'nsp2026').hexdigest())"
# 输出: 5c5236da4fefd43fb0c80f2a4d7f3a8b...（完整填入 GATE_HASH）

# 4. 提交
git add index.html
git commit -m "fix: 部署本地 d5 可视化，密码门升级为 SHA-256 hash 验证"

# 5. 手动 push（Agent 无权限）
git push origin feat/w3d4-pwa-offline
```

完成后，公网 `https://qintingye.github.io/nsp-im/` 密码 = **`nsp2026`**，可视化效果 = 本地 d5 完整版（95KB）。

---

## 五、待确认事项

- [ ] 公网版本 11.6KB 的**原始密码**是否还能找回？（搜邮件 / git stash / 旧 commit）
- [ ] 用户是否接受"换公网版本"还是"换密码"？
- [ ] GitHub Pages 仓库 `qintingye/nsp-im` 的 default branch 是否仍是 `feat/w3d4-pwa-offline`？

---

**报告人**：Hermes Agent (subagent)
**报告时间**：2026-08-18 13:53 (UTC+8)
**文件**：`docs/W3-Fix-公网密码诊断.md`
