# NSP-IM 内网部署预览 (W1-D4)

## 目录结构

```
docs/preview/
├── index.html         # 主页面（搜索 / 过滤 / 统计 / 政策卡片）
├── manifest.json      # PWA manifest
├── sw.js              # Service Worker（缓存策略：stale-while-revalidate）
├── data/
│   ├── policies.json  # 政策数据快照（与 data/policies.json 同步）
│   └── health.json    # 健康状态快照
└── README.md          # 本文件
```

## 部署步骤

```bash
# 1. 生成最新数据
python -m src.main_fetcher --demo

# 2. 同步到预览目录
cp data/policies.json docs/preview/data/
cp data/health.json   docs/preview/data/

# 3. 起本地预览（任选其一）
cd docs/preview && python -m http.server 8080
# 或: npx serve docs/preview

# 4. 部署前自检
bash scripts/deploy_precheck.sh
```

## 离线 / PWA

`sw.js` 注册成功后:
- 首次访问缓存所有核心资源
- `data/*.json`: stale-while-revalidate（离线可用，后台拉新）
- `index.html` / `sw.js`: network-first（保证更新立即可见）
- `manifest.json` 让浏览器识别为可安装 PWA

## 内网部署注意

- `docs/preview/` 是**纯静态**目录，可直接挂在 nginx / IIS / CDN 后
- 数据通过 `data/policies.json` 加载，由 `src.main_fetcher` 每日 09:00 更新
- Service Worker 仅在 HTTPS / localhost 下生效（内网一般满足）

## 数据来源

- `policies.json`: 发改委 + 水利部 + 工信部 demo 数据，共 12 条
- `health.json`: 抓取健康状态（成功/失败/延迟）

W1-D4 验收: ✅ main_fetcher 集成 / ✅ integrate.py / ✅ deploy_precheck.sh / ✅ pytest 全过