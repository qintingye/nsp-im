# NSP-IM v1.0 · 六网协同情报平台

> **状态**：W1 启动中（2026-08-18）
> **目标**：8 周 MVP → 内部 25 人内测

## 目录结构

```
nsp-im/
├── data/                      # 数据
│   ├── policies.json          # 政策清单（主）
│   ├── intelligence/          # 每日情报（YYYY-MM-DD.json）
│   └── cases/                 # 同类案例（Tab5）
├── src/
│   ├── main_fetcher.py        # 每日抓取主程序
│   ├── fetchers/              # 各源抓取器
│   │   ├── base.py            # 基础类
│   │   └── ndrc.py            # 发改委
│   ├── schemas/               # JSON schemas
│   └── utils/
├── tests/                     # 单元测试
├── .github/workflows/         # CI/CD
│   └── daily-fetch.yml        # 每日 9:00 抓取
├── scripts/                   # 运维脚本
├── docs/                      # 文档
└── logs/                      # 日志
```

## W1 任务

- [ ] Git 仓库 + 目录结构
- [ ] 3 个 JSON schema（policies/intelligence/scenes）
- [ ] 1 个 fetcher 跑通（发改委）
- [ ] 健康探针 + 失败告警
- [ ] GitHub Actions CI 跑通
- [ ] 移动端 UI 改造（Frontend）

## 运行方式

```bash
# 安装依赖
pip install aiohttp beautifulsoup4 lxml requests

# 手动跑一次
cd src
python main_fetcher.py

# 每日自动（GitHub Actions 09:00）
```

## 部署

- **Vercel** 部署前端（HTML/manifest/sw.js）
- **GitHub Actions** 每日 09:00 抓取 → git commit → Vercel 自动重新部署

## 团队

- **PM**: 项目管家
- **Backend**: 抓取 + 数据流
- **Frontend**: PWA 移动端
- **测试**: 25 人内测
