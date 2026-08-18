# W3-D3 · Web Push 推送 + VAPID 集成指南

> **目标**：在 NSP-IM 内测阶段, 政策入库时主动推送 Web 通知给所有订阅者 (25 人内测规模).
>
> **范围**：BE 推送服务 + VAPID 密钥管理 + 订阅存储 + OneSignal 备用通道.
>
> **交付时间**: W3-D3 (2026-08-18)

---

## 1. 架构概览

```
┌────────────────────────────────────────────────────────────────────┐
│                  浏览器 (前端 PWA / Web)                            │
│  navigator.serviceWorker.pushManager.subscribe(subscribe(VAPID_PUB)) │
└────────────────┬───────────────────────────────────────────────────┘
                 │ POST /api/subscribe  (PushSubscription JSON)
                 ▼
┌────────────────────────────────────────────────────────────────────┐
│              NSP-IM Push API (stdlib http.server)                    │
│  - GET  /api/vapid-public-key     返回 VAPID 公钥 (前端订阅用)        │
│  - POST /api/subscribe            落盘订阅 (去重)                    │
│  - POST /api/unsubscribe          退订                              │
│  - POST /api/notify               批量推送 (admin token)             │
│  - GET  /api/subscriptions        订阅状态 (admin only, 脱敏)        │
│  - GET  /api/health               健康检查                            │
└────┬───────────────────────────────────────────────────────────┬───┘
     │                                                           │
     │  pywebpush.webpush()                                       │  httpx
     │  (VAPID 签名 + ECE 加密)                                    │
     ▼                                                           ▼
┌──────────────────┐                                    ┌──────────────────┐
│ FCM / Mozilla    │                                    │ OneSignal REST   │
│ Autopush         │                                    │ (海外 SaaS)      │
└──────────────────┘                                    └──────────────────┘
     │                                                           │
     ▼                                                           ▼
┌────────────────────────────────────────────────────────────────────┐
│  浏览器 Service Worker 接收 push 事件 → 显示通知                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心组件

### 2.1 `src/utils/vapid.py` — VAPID 密钥管理

**职责**:
- 生成 P-256 ECDSA 密钥对 (RFC 8292 §2)
- base64url 编码 (无 padding, 与 Web Crypto 兼容)
- 持久化到 `data/.vapid.json` (0o600 权限)
- Lazy load + 进程级缓存 (避免每次启动都 IO)

**关键 API**:
```python
from utils.vapid import get_or_create_vapid_keys

keys = get_or_create_vapid_keys(subject="mailto:dev@example.com")
print(keys.public_key_b64url)   # 给前端订阅用的 applicationServerKey
print(keys.private_key_b64url)  # 服务端签名用, 不外泄
```

**文件格式** (`data/.vapid.json`):
```json
{
  "public_key": "BAdOz5k..._0Q",
  "private_key": "qB4aFv..._0Q",
  "subject": "mailto:dev@example.com"
}
```

⚠️ **生产部署**: 务必设置 `VAPID_SUBJECT` 环境变量 (mailto: 或 https:), 否则推送服务会拒签.

### 2.2 `src/utils/webpush.py` — Web Push 发送封装

**职责**:
- 封装 `pywebpush.webpush()` 一行调用
- 标准化错误分类 (404/410 → SubscriptionExpired, 401/403 → VAPIDConfigError, 429 → RateLimited)
- `send_push()` 单条推送 / `send_push_batch()` 批量

**关键 API**:
```python
from utils.webpush import (
    PushSubscription, PushPayload,
    send_push, send_push_batch,
    SubscriptionExpired, VAPIDConfigError, RateLimited,
)

sub = PushSubscription(
    endpoint="https://fcm.googleapis.com/fcm/send/abc",
    keys_p256dh="...",   # 浏览器公钥
    keys_auth="...",     # 浏览器 auth secret
)
payload = PushPayload(
    title="新政策入库",
    body="国家发改委发布 2026 年新型电力系统建设指导意见",
    url="/policy/123",
    tag="policy-123",
)

ok = send_push(sub, payload)   # True / False / raise
```

**推送失败时的清理策略**:
| HTTP | 类型                | 行为                          |
|------|---------------------|------------------------------|
| 201  | 成功                | return True                  |
| 410  | 订阅失效 (Gone)     | return False + 自动 mark_expired |
| 404  | 端点不存在           | return False + 自动 mark_expired |
| 401  | VAPID 凭证错         | raise VAPIDConfigError (运维介入) |
| 403  | VAPID 凭证错         | raise VAPIDConfigError (运维介入) |
| 429  | 限流                 | raise RateLimited (退避重试)  |
| 5xx  | 推送服务抖动          | raise PushError (通用错误)    |

### 2.3 `src/api/subscriptions.py` — 订阅存储

**职责**:
- 持久化浏览器 `PushSubscription` 到 `data/.subscriptions.json`
- 线程安全 (threading.Lock, 单进程 server 够用)
- 自动清理失效订阅 (404/410 → mark_expired → cleanup_expired)
- 简单去重 (endpoint 作为主键)

**关键 API**:
```python
from api.subscriptions import SubscriptionStore, get_default_store

store = get_default_store()
store.add(subscription_dict, ua="Mozilla/5.0 ...")   # 新增 or 刷新
store.list_active()                                   # 当前活跃订阅
store.mark_expired(endpoint)                          # 推送 410 后调用
store.cleanup_expired()                               # 物理清理
store.count_active()                                  # 数量 (健康检查用)
```

### 2.4 `src/utils/onesignal.py` — OneSignal 备用通道 (可选)

**适用场景**:
- iOS Safari < 16.4 (Web Push 不可用)
- 国内浏览器自动 fallback
- 邮件/短信多通道

**未配置时**: 自动跳过 (`is_configured()` 返回 False), 不影响主链路.

**配置** (环境变量):
```bash
export ONESIGNAL_APP_ID="your-app-id"
export ONESIGNAL_REST_API_KEY="your-rest-api-key"
```

---

## 3. 启动与运行

### 3.1 本地启动

```bash
# 创建 venv + 安装依赖
python -m venv .venv
.venv/Scripts/python.exe -m pip install pywebpush py-vapid httpx

# 启动 Push API
cd src
python -m api.server --host 127.0.0.1 --port 8081 --admin-token dev-token-123
```

### 3.2 健康检查

```bash
curl http://127.0.0.1:8081/api/health
# {"status":"ok","service":"nspim-push-api","version":"1.0","subscriptions_active":0}
```

### 3.3 获取 VAPID 公钥

```bash
curl http://127.0.0.1:8081/api/vapid-public-key
# {"public_key":"BAdOz5k...","subject":"mailto:dev@example.com"}
```

### 3.4 触发推送 (admin only)

```bash
curl -X POST http://127.0.0.1:8081/api/notify \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: dev-token-123" \
  -d '{"title":"测试推送","body":"这是 W3-D3 集成测试","url":"/policy/123"}'

# 响应
# {"ok":true,"sent":3,"expired":0,"error":0,"dry_run":false}
```

加 `"dry_run": true` 仅统计订阅数, 不真发推送 (适合发布前的烟测).

---

## 4. 前端集成 (PWA Service Worker)

### 4.1 注册 Service Worker

```javascript
// 在主页面加载完成后
if ('serviceWorker' in navigator && 'PushManager' in window) {
  navigator.serviceWorker.register('/sw.js')
    .then(reg => console.log('SW registered:', reg.scope));
}
```

### 4.2 订阅推送

```javascript
async function subscribeToPush() {
  // 1. 从 BE 获取 VAPID 公钥
  const { public_key } = await fetch('/api/vapid-public-key').then(r => r.json());

  // 2. 请求通知权限
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    throw new Error('用户拒绝通知权限');
  }

  // 3. 订阅
  const reg = await navigator.serviceWorker.ready;
  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(public_key),
  });

  // 4. 发到 BE 落盘
  const resp = await fetch('/api/subscribe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subscription),
  });
  return resp.json();
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}
```

### 4.3 Service Worker 接收推送 (`/sw.js`)

```javascript
self.addEventListener('push', event => {
  let payload = { title: 'NSP-IM', body: '新通知' };
  if (event.data) {
    try { payload = event.data.json(); }
    catch (e) { payload.body = event.data.text(); }
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: payload.icon || '/icons/icon-192.png',
      badge: payload.badge || '/icons/badge-72.png',
      tag: payload.tag,
      data: { url: payload.url || '/' },
      requireInteraction: payload.requireInteraction || false,
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(clients.openWindow(url));
});
```

---

## 5. 安全考量

### 5.1 VAPID Subject

VAPID 签名要求 `sub` 字段是 mailto: 或 https: URL. 生产环境必须设置成**可联系到的**地址:
```bash
export VAPID_SUBJECT="mailto:ops@your-domain.com"
# 或
export VAPID_SUBJECT="https://your-domain.com/contact"
```

否则浏览器端推送服务 (Mozilla/Google) 会拒签.

### 5.2 私钥保护

- 文件权限: `data/.vapid.json` umask 0o600
- **绝不**把私钥提交到 git (`.gitignore` 应包含 `data/.vapid.json` `data/.subscriptions.json`)
- 部署到生产时通过环境变量或 secrets manager 注入, 而非直接拷贝文件

### 5.3 Admin Token

`/api/notify` 和 `/api/subscriptions` 需要 `X-Admin-Token` 头, 与 `ADMIN_TOKEN` 环境变量比对.

未配置 `ADMIN_TOKEN` 时, 仅信任 localhost (`127.0.0.1` / `::1`) 调用管理接口.

### 5.4 CORS

默认**不**放 CORS (同源 only). 需要跨域时设置:
```bash
export ALLOW_ORIGIN="https://your-pwa-domain.com"
```

### 5.5 输入校验

- `/api/subscribe` 强制 `endpoint` 必须 `https://` 开头 (Web Push 规范)
- 请求体上限 16 KiB (远大于 PushSubscription)
- 订阅存储字段白名单 (status/fail_count 由 server 控制, 不接受客户端输入)

---

## 6. 部署到 Vercel

`src/api/server.py` 是 stdlib http.server, **不适合** Vercel Serverless (无长连接).
内测阶段建议部署到:

| 选项 | 适用场景 | 配置 |
|------|---------|------|
| Vercel Serverless | 仅做 webhook 入口, 推送走异步队列 | 改用 `/api/notify` POST 入口 |
| Fly.io / Render | 内测 25 人长连接 | 直接跑 `python -m api.server` |
| 本地 (systemd) | 内网小团队 | 监听 127.0.0.1:8081, 反代 |

W3-D4 (PWA 离线) 将补充前端 SW + manifest.json.

---

## 7. 故障排查

### 7.1 推送 401 / 403

VAPID 凭证错. 检查:
```bash
# 1. 私钥文件存在且有效
cat data/.vapid.json | python -c "import json,sys; d=json.load(sys.stdin); print('OK' if 'private_key' in d else 'BROKEN')"

# 2. VAPID_SUBJECT 是否设置
echo $VAPID_SUBJECT

# 3. Subject 必须是 mailto: / https: 开头
```

### 7.2 推送 410 Gone

订阅过期 (浏览器卸载/隐私模式/换设备). `send_push` 已自动 `mark_expired`, 24h 后 `cleanup_expired` 清理.

### 7.3 推送 429 限流

```python
from utils.webpush import RateLimited
import time

for attempt in range(3):
    try:
        send_push(sub, payload)
        break
    except RateLimited:
        time.sleep(2 ** attempt)   # 指数退避
```

### 7.4 数据文件损坏

```bash
# 备份并重置
cp data/.subscriptions.json data/.subscriptions.json.bak
echo '{"version":"1.0","subscriptions":[]}' > data/.subscriptions.json
```

下次启动 `load_vapid_keys` / `SubscriptionStore._read` 检测到损坏会优雅降级.

---

## 8. 测试覆盖

```
$ python -m pytest tests/test_w3d3_push.py -v

TestVAPIDKeys           (5 tests)   生成 / 持久化 / 往返 / 损坏降级 / 缓存
TestPushPayload         (4 tests)   载荷 JSON 形状 / 字段裁剪 / 中文支持
TestSubscriptionStore  (11 tests)  add / dedup / 失效清理 / 线程安全 / 校验
TestSendPushMocked      (5 tests)   成功 / 410 / 401 / 429 / 批量分类
TestOneSignalConfig     (4 tests)   环境检测 / 配置缺失 / 形状
─────────────────────────────────
29 passed
```

覆盖的关键不变量:
- VAPID 密钥字节长度符合 RFC 8292 (公钥 65 字节, 私钥 32 字节)
- `PushPayload.to_json()` 严格截断 (title ≤ 64, body ≤ 200)
- 订阅 `endpoint` 去重, 状态机正确 (active ↔ expired)
- 推送错误分类正确 (HTTP 状态码 → 异常类型)
- 多线程并发安全 (8 线程 × 5 次 add, 最终 40 条全部保留)

---

## 9. 后续优化 (W3-D5+)

- [ ] 接入 Prometheus 指标 (推送成功率 / 延迟 / 限流次数)
- [ ] Webhook 自动清理: 用户退订浏览器通知时, `/api/unsubscribe` 已实现, 前端 Service Worker `pushsubscriptionchange` 事件自动调用
- [ ] OneSignal 通道: 接入 fallback 链 (VAPID 失败 → OneSignal)
- [ ] 推送偏好: 用户按"政策类型"订阅 (NSPC/NEA/BJX/CSG/SGCC 单选或多选)
- [ ] 推送到达率统计 (FCM/Mozilla 自带 `report-error` header)

---

**作者**: NSP-IM Backend Team · **版本**: 1.0 · **最后更新**: 2026-08-18